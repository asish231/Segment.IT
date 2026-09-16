#!/usr/bin/env python
"""HTTP API: upload a land record page, get a digitized document + structured schema back.

    uvicorn api:app --host 0.0.0.0 --port 8000

Auth: most endpoints require `Authorization: Bearer <access_token>` (from /auth/login)
or an API key (`bh_...`, from /auth/api-keys). /health, /auth/register and /auth/login
are open.
"""
import base64
import json
import os
import shutil
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import cv2
import numpy as np
from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import auth
from db import get_db, init_db
from models import ApiKey, AuditLog, Job, User

from linecut import (
    dual_ocr,
    land_records,
    llm_refiner,
    segment_page,
    segment_page_instances,
    stamp_extractor,
    table_extractor,
    validation,
)


@asynccontextmanager
async def lifespan(app: "FastAPI"):
    init_db()
    _bootstrap_admin()
    yield


app = FastAPI(
    title="BhoomiAI",
    description="Digitizes and validates land records: OCR + table/stamp extraction + DoLR/DILRMP schema.",
    version="3.0",
    lifespan=lifespan,
)

CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JOBS = Path(os.environ.get("JOBS_DIR", "data/jobs"))
JOBS.mkdir(parents=True, exist_ok=True)

MAX_BYTES = 40 * 1024 * 1024
LOW_CONFIDENCE_THRESHOLD = 0.75


def _bootstrap_admin() -> None:
    """Create a first admin user from env so a fresh deploy isn't locked out."""
    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PASSWORD")
    if not email or not password:
        return
    db = next(get_db())
    try:
        if db.query(User).filter(User.email == email).first():
            return
        if db.query(User).count() > 0:
            return
        db.add(User(email=email, name="Administrator", hashed_password=auth.hash_password(password), role="admin"))
        db.commit()
    finally:
        db.close()


def _audit(db: Session, *, job_id: Optional[str], user_id: Optional[str], action: str, detail: Optional[dict] = None) -> None:
    try:
        db.add(AuditLog(job_id=job_id, user_id=user_id, action=action, detail=detail or {}))
        db.commit()
    except Exception:
        db.rollback()


def _user_out(u: User) -> dict:
    return {
        "id": u.id, "email": u.email, "name": u.name, "role": u.role,
        "state": u.state, "district": u.district, "created_at": u.created_at.isoformat(),
    }


# ============================================================================
# Auth
# ============================================================================

class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    name: str = ""
    state: str = ""
    district: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ApiKeyCreateRequest(BaseModel):
    name: str = "default"


@app.post("/auth/register")
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(409, "an account with this email already exists")
    is_first_user = db.query(User).count() == 0
    user = User(
        email=body.email,
        name=body.name or body.email.split("@")[0],
        hashed_password=auth.hash_password(body.password),
        role="admin" if is_first_user else "operator",
        state=body.state,
        district=body.district,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    _audit(db, job_id=None, user_id=user.id, action="user.registered")
    return {
        "access_token": auth.make_access_token(user.id),
        "refresh_token": auth.make_refresh_token(user.id),
        "user": _user_out(user),
    }


@app.post("/auth/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not auth.verify_password(body.password, user.hashed_password):
        raise HTTPException(401, "invalid email or password")
    if not user.is_active:
        raise HTTPException(403, "account disabled")
    _audit(db, job_id=None, user_id=user.id, action="user.login")
    return {
        "access_token": auth.make_access_token(user.id),
        "refresh_token": auth.make_refresh_token(user.id),
        "user": _user_out(user),
    }


@app.post("/auth/refresh")
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    payload = auth.decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(401, "not a refresh token")
    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user or not user.is_active:
        raise HTTPException(401, "user inactive")
    return {"access_token": auth.make_access_token(user.id)}


@app.get("/auth/me")
def me(user: User = Depends(auth.get_current_user)):
    return _user_out(user)


@app.post("/auth/api-keys")
def create_api_key(body: ApiKeyCreateRequest, user: User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    full_key, prefix, hashed = auth.generate_api_key()
    key = ApiKey(user_id=user.id, name=body.name, prefix=prefix, hashed_key=hashed)
    db.add(key)
    db.commit()
    _audit(db, job_id=None, user_id=user.id, action="api_key.created", detail={"prefix": prefix})
    return {"id": key.id, "name": key.name, "prefix": prefix, "key": full_key, "created_at": key.created_at.isoformat()}


@app.get("/auth/api-keys")
def list_api_keys(user: User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    keys = db.query(ApiKey).filter(ApiKey.user_id == user.id).order_by(ApiKey.created_at.desc()).all()
    return [
        {
            "id": k.id, "name": k.name, "prefix": k.prefix,
            "created_at": k.created_at.isoformat(),
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
            "revoked": k.revoked_at is not None,
        }
        for k in keys
    ]


@app.delete("/auth/api-keys/{key_id}")
def revoke_api_key(key_id: str, user: User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    key = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.user_id == user.id).first()
    if not key:
        raise HTTPException(404, "no such API key")
    key.revoked_at = datetime.now(timezone.utc)
    db.commit()
    _audit(db, job_id=None, user_id=user.id, action="api_key.revoked", detail={"prefix": key.prefix})
    return {"revoked": key_id}


# ============================================================================
# Health
# ============================================================================

@app.get("/health")
def health():
    return {"status": "ok", "jobs_dir": str(JOBS)}


# ============================================================================
# Segment: the core OCR + table/stamp + LLM + land-record pipeline
# ============================================================================

@app.post("/segment")
async def segment(
    image: UploadFile = File(..., description="Page image (png/jpg/tif)"),
    device: Literal["cpu", "mps"] = Form("cpu"),
    mode: Literal["instances", "global"] = Form("instances",
        description="instances: per-line angle and curve (default). global: one page angle."),
    threshold: float = Form(0.30, description="Max seam cost to accept a cut (global mode)"),
    dewarp: bool = Form(True, description="Straighten each line before cropping (global mode)"),
    rotate: float = Form(0.0, description="Extra rotation in degrees, added to the detected angle"),
    extract_tables: bool = Form(True, description="Detect tables, extract 2D cells, and compile land record schema"),
    ocr: bool = Form(True, description="Scan lines with parallel Dual-OCR (PaddleOCR + TrOCR)"),
    ocr_lang: str = Form("en", description="Target OCR language (en, devanagari, hi, etc.)"),
    llm_refine: bool = Form(True, description="Refine OCR lines and format document with Mercury-2.5 reasoning LLM"),
    include_images: bool = Form(True, description="Inline base64 PNG per line"),
    include_raw: bool = Form(False, description="Also inline the unmasked strip per line"),
    keep: bool = Form(True, description="Keep crops and documents on disk for /jobs fetches"),
    doc_type: str = Form("auto"),
    state: str = Form(""),
    district: str = Form(""),
    tehsil: str = Form(""),
    user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    raw = await image.read()
    if not raw:
        raise HTTPException(400, "empty upload")
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, f"image larger than {MAX_BYTES // (1024*1024)}MB")

    decoded = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if decoded is None:
        raise HTTPException(415, "could not decode image")

    job_id = uuid.uuid4().hex
    out_dir = JOBS / job_id
    doc_title = Path(image.filename or "Document").stem

    # Tier 0: Table & Stamp Detection (mask out tables and non-text stamps from line cutter)
    detected_tables = []
    detected_stamps = []
    segment_src = decoded
    if extract_tables and decoded is not None:
        try:
            detected_tables = table_extractor.extract_all_tables(decoded)
            detected_stamps = stamp_extractor.detect_stamps(decoded, detected_tables=detected_tables)
            if detected_stamps:
                stamp_extractor.extract_and_save_stamps(detected_stamps, decoded, out_dir)

            if detected_tables or detected_stamps:
                segment_src = decoded.copy()
                for t in detected_tables:
                    tx, ty, tw, th = t["bbox"]
                    cv2.rectangle(segment_src, (tx, ty), (tx + tw, ty + th), (255, 255, 255), -1)
                for s in detected_stamps:
                    sx, sy, sw, sh = s["bbox"]
                    cv2.rectangle(segment_src, (sx, sy), (sx + sw, sy + sh), (255, 255, 255), -1)
        except Exception:
            detected_tables = []
            detected_stamps = []

    try:
        if mode == "instances":
            manifest = segment_page_instances(
                image.filename or "upload", out_dir, device=device, src=segment_src,
            )
        else:
            manifest = segment_page(
                image.filename or "upload", out_dir,
                device=device, dewarp=dewarp, threshold=threshold,
                rotate_extra=rotate, src=segment_src,
            )
    except Exception as exc:
        shutil.rmtree(out_dir, ignore_errors=True)
        raise HTTPException(500, f"segmentation failed: {exc}") from exc

    manifest["job_id"] = job_id
    manifest["source"] = image.filename

    try:
        cv2.imwrite(str(out_dir / "source.png"), decoded)
    except Exception:
        pass

    # Execute Parallel Dual-OCR if requested
    if ocr and manifest.get("lines"):
        try:
            scanned = dual_ocr.scan_manifest_lines_parallel(manifest["lines"], out_dir, lang=ocr_lang)
            for line_entry, ocr_result in zip(manifest["lines"], scanned):
                line_entry["text"] = ocr_result.get("final_text", "")
                line_entry["confidence_ocr"] = ocr_result.get("confidence", 0.0)
                line_entry["dual_ocr"] = {
                    "paddle": ocr_result.get("paddle", {}),
                    "trocr": ocr_result.get("trocr", {}),
                    "status": ocr_result.get("status", "unknown"),
                    "similarity": ocr_result.get("similarity"),
                    "corrections": ocr_result.get("corrections_applied", []),
                }

            # Execute LLM Intelligence Refinement (Mercury-2.5) if enabled
            md_text = ""
            if llm_refine:
                try:
                    manifest["lines"], md_text, llm_err = llm_refiner.refine_lines_with_llm(
                        manifest["lines"], doc_title=doc_title, layout=manifest.get("layout", "plain"), lang=ocr_lang
                    )
                    manifest["llm_refinement"] = {
                        "model": "mercury-2.5",
                        "status": "success" if not llm_err else "failed",
                        "error": llm_err,
                    }
                except Exception as l_exc:
                    manifest["llm_refinement"] = {"model": "mercury-2.5", "status": "failed", "error": str(l_exc)}

            # Generate Document Outputs
            if not md_text:
                md_text = dual_ocr.export_markdown(manifest["lines"], title=doc_title)
            txt_text = dual_ocr.export_text(manifest["lines"])
            docx_path = out_dir / "document.docx"
            dual_ocr.export_docx(manifest["lines"], docx_path, title=doc_title)

            # Persist textual files
            (out_dir / "document.md").write_text(md_text, encoding="utf-8")
            (out_dir / "document.txt").write_text(txt_text, encoding="utf-8")

            manifest["markdown"] = md_text
            manifest["document_text"] = txt_text
            manifest["documents"] = {
                "markdown": f"/jobs/{job_id}/document.md",
                "docx": f"/jobs/{job_id}/document.docx",
                "text": f"/jobs/{job_id}/document.txt",
                "latent": f"/jobs/{job_id}/latent.json",
            }
        except Exception as ocr_exc:
            manifest["ocr_error"] = str(ocr_exc)

    # Execute Table & Cell Extraction + Land Record Compilation (MoRD / DoLR PS 26018)
    if extract_tables and decoded is not None:
        try:
            if not detected_tables:
                detected_tables = table_extractor.extract_all_tables(decoded)
            if detected_tables:
                if ocr:
                    detected_tables = dual_ocr.scan_table_cells_parallel(
                        detected_tables, decoded, lang=ocr_lang
                    )

                l_rec = land_records.build_structured_land_record(
                    detected_tables, manifest.get("lines", [])
                )

                # Mercury-2.5 LLM refinement + one-shot "is this a land record" classification
                classification = dict(llm_refiner.DEFAULT_CLASSIFICATION)
                if llm_refine and ocr:
                    try:
                        all_tables_md = "\n\n".join(
                            t.get("markdown", "") for t in detected_tables if t.get("markdown")
                        )
                        refined_rec, refined_md_tbl, classification, _ = llm_refiner.refine_land_record_with_llm(
                            l_rec, all_tables_md, doc_title=doc_title,
                        )
                        if refined_rec:
                            l_rec = refined_rec
                    except Exception:
                        pass
                l_rec.setdefault("classification", classification)

                # Re-export unified document (prose + stamps + tables interleaved in true reading order)
                if ocr:
                    docx_path = out_dir / "document.docx"
                    md_text = dual_ocr.export_markdown(manifest.get("lines", []), tables=detected_tables, stamps=detected_stamps, title=doc_title)
                    txt_text = dual_ocr.export_text(manifest.get("lines", []), tables=detected_tables, stamps=detected_stamps)
                    dual_ocr.export_docx(manifest.get("lines", []), docx_path, tables=detected_tables, stamps=detected_stamps, title=doc_title)
                    (out_dir / "document.md").write_text(md_text, encoding="utf-8")
                    (out_dir / "document.txt").write_text(txt_text, encoding="utf-8")
                    manifest["markdown"] = md_text
                    manifest["document_text"] = txt_text

                    dual_ocr.reassemble_page_with_tables(
                        manifest.get("lines", []), detected_tables, decoded, out_dir / "page_reassembled.png", stamps=detected_stamps, job_dir=out_dir
                    )

                (out_dir / "land_record.json").write_text(
                    json.dumps(l_rec, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                manifest["tables"] = detected_tables
                manifest["stamps"] = detected_stamps
                manifest["land_record"] = l_rec
                manifest["validation"] = l_rec.get("validation", {})
                if "documents" not in manifest:
                    manifest["documents"] = {}
                manifest["documents"]["land_record"] = f"/jobs/{job_id}/land_record.json"
        except Exception as tbl_exc:
            manifest["table_error"] = str(tbl_exc)

    # Persist the editable job state (lines + tables + stamps + title) so PATCH
    # endpoints can regenerate document.md/.txt/.docx after a human correction.
    try:
        (out_dir / "job_state.json").write_text(
            json.dumps({
                "doc_title": doc_title,
                "lines": manifest.get("lines", []),
                "tables": manifest.get("tables", []),
                "stamps": manifest.get("stamps", []),
            }, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    except Exception:
        pass

    if include_images:
        for line in manifest["lines"]:
            crop_path = out_dir / line["file"]
            if crop_path.is_file():
                line["png_base64"] = base64.b64encode(crop_path.read_bytes()).decode()

    if include_raw:
        for line in manifest["lines"]:
            raw_rel = line.get("file_raw")
            if raw_rel and (out_dir / raw_rel).is_file():
                line["png_base64_raw"] = base64.b64encode((out_dir / raw_rel).read_bytes()).decode()

    for line in manifest["lines"]:
        line["url"] = f"/jobs/{job_id}/lines/{line['index']}"
        if line.get("file_raw"):
            line["url_raw"] = f"/jobs/{job_id}/lines/{line['index']}?variant=raw"

    # Save latent representation
    latent_path = out_dir / "latent.json"
    latent_data = {
        "job_id": job_id,
        "source": image.filename,
        "lines_found": manifest.get("lines_found", 0),
        "deskew_deg": manifest.get("deskew_deg"),
        "layout": manifest.get("layout"),
        "source_size": manifest.get("source_size"),
        "tables": manifest.get("tables", []),
        "stamps": manifest.get("stamps", []),
        "lines": manifest["lines"],
    }
    latent_path.write_text(json.dumps(latent_data, indent=2, default=str), encoding="utf-8")
    manifest["raw_latent"] = latent_data

    # Persist the job row in Postgres/SQLite so it survives refreshes and feeds the dashboard.
    try:
        confidences = [l.get("confidence_ocr", 0.0) for l in manifest.get("lines", []) if l.get("text")]
        avg_conf = round(sum(confidences) / len(confidences), 4) if confidences else 0.0
        low_conf_count = sum(1 for c in confidences if c < LOW_CONFIDENCE_THRESHOLD)
        val = manifest.get("validation", {}) or {}
        review_required = bool(val.get("review_required")) or low_conf_count > 0
        status = "failed" if manifest.get("ocr_error") and not manifest.get("markdown") else (
            "needs_review" if review_required else "complete"
        )
        job_row = Job(
            id=job_id,
            owner_id=user.id,
            source_filename=image.filename or "upload",
            lang=ocr_lang,
            doc_type=doc_type,
            state=state, district=district, tehsil=tehsil,
            status=status,
            lines_found=manifest.get("lines_found", 0),
            tables_found=len(manifest.get("tables", [])),
            stamps_found=len(manifest.get("stamps", [])),
            avg_confidence=avg_conf,
            low_confidence_count=low_conf_count,
            validation_passed=bool(val.get("validation_passed")),
            review_required=review_required,
            processing_seconds=float(manifest.get("seconds") or 0.0),
            error=manifest.get("ocr_error") or manifest.get("table_error") or "",
            land_record=manifest.get("land_record", {}) or {},
            validation=val,
            is_land_record=(manifest.get("land_record") or {}).get("classification", {}).get("is_land_record"),
            classification_confidence=float((manifest.get("land_record") or {}).get("classification", {}).get("confidence") or 0.0),
            classification_reasoning=str((manifest.get("land_record") or {}).get("classification", {}).get("reasoning") or ""),
        )
        db.add(job_row)
        db.commit()
        _audit(db, job_id=job_id, user_id=user.id, action="job.created", detail={"filename": image.filename})
        manifest["job_status"] = status
    except Exception as db_exc:
        manifest["job_db_error"] = str(db_exc)

    if not keep:
        shutil.rmtree(out_dir, ignore_errors=True)
        for line in manifest["lines"]:
            line.pop("url", None)

    return JSONResponse(manifest)


# ============================================================================
# Job file downloads (unauthenticated: job_id is an opaque 32-hex capability)
# ============================================================================

def _job_id_or_400(job_id: str) -> None:
    if not job_id.isalnum():
        raise HTTPException(400, "bad job id")


@app.get("/jobs/{job_id}/document.md")
def get_document_markdown(job_id: str):
    _job_id_or_400(job_id)
    path = JOBS / job_id / "document.md"
    if not path.is_file():
        raise HTTPException(404, "markdown document not found")
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown")


@app.get("/jobs/{job_id}/document.docx")
def get_document_docx(job_id: str):
    _job_id_or_400(job_id)
    path = JOBS / job_id / "document.docx"
    if not path.is_file():
        raise HTTPException(404, "docx document not found")
    return FileResponse(path, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename="document.docx")


@app.get("/jobs/{job_id}/document.txt")
def get_document_text(job_id: str):
    _job_id_or_400(job_id)
    path = JOBS / job_id / "document.txt"
    if not path.is_file():
        raise HTTPException(404, "text document not found")
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/plain")


@app.get("/jobs/{job_id}/latent.json")
def get_document_latent(job_id: str):
    _job_id_or_400(job_id)
    path = JOBS / job_id / "latent.json"
    if not path.is_file():
        raise HTTPException(404, "latent representation not found")
    return FileResponse(path, media_type="application/json")


@app.get("/jobs/{job_id}/land_record.json")
def get_document_land_record(job_id: str):
    _job_id_or_400(job_id)
    path = JOBS / job_id / "land_record.json"
    if not path.is_file():
        raise HTTPException(404, "land record document not found")
    return FileResponse(path, media_type="application/json")


@app.get("/jobs/{job_id}/source.png")
def get_source_image(job_id: str):
    """The original uploaded page, before any masking or segmentation."""
    _job_id_or_400(job_id)
    path = JOBS / job_id / "source.png"
    if not path.is_file():
        raise HTTPException(404, "source image not found")
    return FileResponse(path, media_type="image/png")


@app.get("/jobs/{job_id}/page_reassembled.png")
def get_reassembled_image(job_id: str):
    """The digitized page: prose lines, tables, and stamps composited in reading order."""
    _job_id_or_400(job_id)
    path = JOBS / job_id / "page_reassembled.png"
    if not path.is_file():
        raise HTTPException(404, "reassembled page not found")
    return FileResponse(path, media_type="image/png")


@app.get("/jobs/{job_id}/lines/{index}")
def get_line(job_id: str, index: int, variant: Literal["clean", "raw"] = "clean"):
    _job_id_or_400(job_id)
    folder = "lines_raw" if variant == "raw" else "lines"
    path = JOBS / job_id / folder / f"line_{index:04d}.png"
    if not path.is_file():
        raise HTTPException(404, "no such line")
    return FileResponse(path, media_type="image/png")


@app.delete("/jobs/{job_id}")
def drop_job(job_id: str, user: User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    _job_id_or_400(job_id)
    row = db.query(Job).filter(Job.id == job_id).first()
    if row and row.owner_id and row.owner_id != user.id and user.role not in ("admin", "supervisor"):
        raise HTTPException(403, "not your job")
    target = JOBS / job_id
    if not target.is_dir() and not row:
        raise HTTPException(404, "no such job")
    shutil.rmtree(target, ignore_errors=True)
    if row:
        db.delete(row)
        db.commit()
    _audit(db, job_id=job_id, user_id=user.id, action="job.deleted")
    return {"deleted": job_id}


# ============================================================================
# v1: jobs, dashboard stats, review workflow, and human-in-the-loop editing
# ============================================================================

def _job_out(row: Job) -> dict:
    return {
        "id": row.id,
        "owner_id": row.owner_id,
        "source_filename": row.source_filename,
        "lang": row.lang,
        "doc_type": row.doc_type,
        "state": row.state, "district": row.district, "tehsil": row.tehsil,
        "status": row.status,
        "lines_found": row.lines_found,
        "tables_found": row.tables_found,
        "stamps_found": row.stamps_found,
        "avg_confidence": row.avg_confidence,
        "low_confidence_count": row.low_confidence_count,
        "corrections_count": row.corrections_count,
        "validation_passed": row.validation_passed,
        "review_required": row.review_required,
        "is_land_record": row.is_land_record,
        "classification_confidence": row.classification_confidence,
        "classification_reasoning": row.classification_reasoning,
        "processing_seconds": row.processing_seconds,
        "error": row.error,
        "verified_by_id": row.verified_by_id,
        "verified_at": row.verified_at.isoformat() if row.verified_at else None,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "documents": {
            "markdown": f"/jobs/{row.id}/document.md",
            "docx": f"/jobs/{row.id}/document.docx",
            "text": f"/jobs/{row.id}/document.txt",
            "latent": f"/jobs/{row.id}/latent.json",
            "land_record": f"/jobs/{row.id}/land_record.json",
            "source_image": f"/jobs/{row.id}/source.png",
            "reassembled_image": f"/jobs/{row.id}/page_reassembled.png",
        },
    }


@app.get("/v1/jobs")
def list_jobs(
    status: Optional[str] = None,
    state: Optional[str] = None,
    district: Optional[str] = None,
    mine: bool = False,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Job)
    if mine or user.role not in ("admin", "supervisor"):
        q = q.filter(Job.owner_id == user.id)
    if status:
        q = q.filter(Job.status == status)
    if state:
        q = q.filter(Job.state == state)
    if district:
        q = q.filter(Job.district == district)
    total = q.count()
    rows = q.order_by(Job.created_at.desc()).offset(offset).limit(min(limit, 200)).all()
    return {"total": total, "jobs": [_job_out(r) for r in rows]}


@app.get("/v1/jobs/{job_id}")
def get_job(job_id: str, user: User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    row = db.query(Job).filter(Job.id == job_id).first()
    if not row:
        raise HTTPException(404, "no such job")
    out = _job_out(row)
    out["land_record"] = row.land_record
    out["validation"] = row.validation

    latent_path = JOBS / job_id / "latent.json"
    if latent_path.is_file():
        try:
            out["latent"] = json.loads(latent_path.read_text(encoding="utf-8"))
        except Exception:
            out["latent"] = None

    md_path = JOBS / job_id / "document.md"
    if md_path.is_file():
        out["markdown"] = md_path.read_text(encoding="utf-8")

    return out


@app.get("/v1/stats")
def stats(user: User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    q = db.query(Job)
    if user.role not in ("admin", "supervisor"):
        q = q.filter(Job.owner_id == user.id)
    rows = q.all()

    total = len(rows)
    by_status: Dict[str, int] = {}
    by_state: Dict[str, int] = {}
    by_district: Dict[str, int] = {}
    confidences = []
    for r in rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1
        if r.state:
            by_state[r.state] = by_state.get(r.state, 0) + 1
        if r.district:
            by_district[r.district] = by_district.get(r.district, 0) + 1
        if r.avg_confidence:
            confidences.append(r.avg_confidence)

    return {
        "total_documents": total,
        "by_status": by_status,
        "pending_review": by_status.get("needs_review", 0),
        "verified": by_status.get("verified", 0),
        "rejected": by_status.get("rejected", 0),
        "failed": by_status.get("failed", 0),
        "avg_extraction_confidence": round(sum(confidences) / len(confidences), 4) if confidences else 0.0,
        "state_wise": by_state,
        "district_wise": by_district,
    }


@app.get("/v1/audit")
def audit_log(limit: int = 100, user: User = Depends(auth.require_role("admin", "supervisor")), db: Session = Depends(get_db)):
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(min(limit, 500)).all()
    return [
        {
            "id": a.id, "job_id": a.job_id, "user_id": a.user_id,
            "action": a.action, "detail": a.detail, "created_at": a.created_at.isoformat(),
        }
        for a in rows
    ]


class LineEditRequest(BaseModel):
    text: str


def _load_job_state(job_id: str) -> dict:
    path = JOBS / job_id / "job_state.json"
    if not path.is_file():
        raise HTTPException(409, "this job has no editable state (re-run OCR to enable editing)")
    return json.loads(path.read_text(encoding="utf-8"))


def _regenerate_documents(job_id: str, state: dict) -> None:
    out_dir = JOBS / job_id
    lines = state.get("lines", [])
    tables = state.get("tables", [])
    stamps = state.get("stamps", [])
    title = state.get("doc_title", "Document")
    md_text = dual_ocr.export_markdown(lines, tables=tables, stamps=stamps, title=title)
    txt_text = dual_ocr.export_text(lines, tables=tables, stamps=stamps)
    dual_ocr.export_docx(lines, out_dir / "document.docx", tables=tables, stamps=stamps, title=title)
    (out_dir / "document.md").write_text(md_text, encoding="utf-8")
    (out_dir / "document.txt").write_text(txt_text, encoding="utf-8")
    (out_dir / "job_state.json").write_text(json.dumps(state, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


@app.patch("/jobs/{job_id}/lines/{index}")
def edit_line(
    job_id: str, index: int, body: LineEditRequest,
    user: User = Depends(auth.require_role("operator", "supervisor")),
    db: Session = Depends(get_db),
):
    _job_id_or_400(job_id)
    state = _load_job_state(job_id)
    match = next((l for l in state.get("lines", []) if l.get("index") == index), None)
    if not match:
        raise HTTPException(404, "no such line")

    old_text = match.get("text", "")
    match["text"] = body.text
    match["confidence_ocr"] = 1.0
    match["human_corrected"] = True
    _regenerate_documents(job_id, state)

    row = db.query(Job).filter(Job.id == job_id).first()
    if row:
        row.corrections_count += 1
        if row.status == "needs_review" and row.low_confidence_count > 0:
            row.low_confidence_count = max(0, row.low_confidence_count - 1)
        db.commit()

    _audit(db, job_id=job_id, user_id=user.id, action="line.edited",
           detail={"index": index, "old_text": old_text, "new_text": body.text})
    return {"index": index, "text": body.text}


@app.patch("/jobs/{job_id}/land-record")
def edit_land_record(
    job_id: str, body: Dict[str, Any],
    user: User = Depends(auth.require_role("operator", "supervisor")),
    db: Session = Depends(get_db),
):
    _job_id_or_400(job_id)
    out_dir = JOBS / job_id
    path = out_dir / "land_record.json"
    if not path.is_file():
        raise HTTPException(404, "no land record for this job")

    recomputed = validation.run_full_validation(body)
    body["validation"] = recomputed
    path.write_text(json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8")

    row = db.query(Job).filter(Job.id == job_id).first()
    if row:
        row.land_record = body
        row.validation = recomputed
        row.validation_passed = bool(recomputed.get("validation_passed"))
        row.review_required = bool(recomputed.get("review_required"))
        row.corrections_count += 1
        if row.status == "needs_review" and not row.review_required:
            row.status = "complete"
        db.commit()

    _audit(db, job_id=job_id, user_id=user.id, action="land_record.edited")
    return {"land_record": body, "validation": recomputed}


class RejectRequest(BaseModel):
    reason: str = ""


@app.post("/v1/jobs/{job_id}/verify")
def verify_job(job_id: str, user: User = Depends(auth.require_role("supervisor")), db: Session = Depends(get_db)):
    row = db.query(Job).filter(Job.id == job_id).first()
    if not row:
        raise HTTPException(404, "no such job")
    row.status = "verified"
    row.verified_by_id = user.id
    row.verified_at = datetime.now(timezone.utc)
    db.commit()
    _audit(db, job_id=job_id, user_id=user.id, action="job.verified")
    return _job_out(row)


@app.post("/v1/jobs/{job_id}/reject")
def reject_job(job_id: str, body: RejectRequest, user: User = Depends(auth.require_role("supervisor")), db: Session = Depends(get_db)):
    row = db.query(Job).filter(Job.id == job_id).first()
    if not row:
        raise HTTPException(404, "no such job")
    row.status = "rejected"
    row.verified_by_id = user.id
    row.verified_at = datetime.now(timezone.utc)
    db.commit()
    _audit(db, job_id=job_id, user_id=user.id, action="job.rejected", detail={"reason": body.reason})
    return _job_out(row)
