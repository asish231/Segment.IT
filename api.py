#!/usr/bin/env python
"""HTTP API: POST an image, get its text lines back in reading order.

    uvicorn api:app --host 0.0.0.0 --port 8000

    curl -F image=@page.png http://localhost:8000/segment > out.json

Lines come back as a list already sorted top-to-bottom of the deskewed page, each
with a 1-based `index`. Iterate the list as-is to process the page in order.
"""
import base64
import json
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Literal, Optional

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from linecut import (
    dual_ocr,
    land_records,
    llm_refiner,
    segment_page,
    segment_page_instances,
    table_extractor,
    validation,
)

app = FastAPI(
    title="linecut",
    description="Segments document images into ordered lines and converts them to digital documents using parallel Dual-OCR and Mercury-2.5 LLM refinement.",
    version="2.1",
)

JOBS = Path(tempfile.gettempdir()) / "linecut-jobs"
JOBS.mkdir(parents=True, exist_ok=True)

MAX_BYTES = 40 * 1024 * 1024


@app.get("/health")
def health():
    return {"status": "ok", "jobs_dir": str(JOBS)}


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

    # Tier 0: Table-First Detection (mask out tables from line cutter so it only strips prose)
    detected_tables = []
    segment_src = decoded
    if extract_tables and decoded is not None:
        try:
            detected_tables = table_extractor.extract_all_tables(decoded)
            if detected_tables:
                segment_src = decoded.copy()
                for t in detected_tables:
                    tx, ty, tw, th = t["bbox"]
                    cv2.rectangle(segment_src, (tx, ty), (tx + tw, ty + th), (255, 255, 255), -1)
        except Exception:
            detected_tables = []

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

            doc_title = Path(image.filename or "Document").stem

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

                # Mercury-2.5 LLM refinement for land record if enabled
                if llm_refine and ocr:
                    try:
                        all_tables_md = "\n\n".join(
                            t.get("markdown", "") for t in detected_tables if t.get("markdown")
                        )
                        refined_rec, refined_md_tbl, _ = llm_refiner.refine_land_record_with_llm(
                            l_rec,
                            all_tables_md,
                            doc_title=Path(image.filename or "Document").stem,
                        )
                        if refined_rec:
                            l_rec = refined_rec
                    except Exception:
                        pass

                # Re-export unified document (prose + tables interleaved in true reading order)
                if ocr:
                    doc_title = Path(image.filename or "Document").stem
                    docx_path = out_dir / "document.docx"
                    md_text = dual_ocr.export_markdown(manifest.get("lines", []), tables=detected_tables, title=doc_title)
                    txt_text = dual_ocr.export_text(manifest.get("lines", []), tables=detected_tables)
                    dual_ocr.export_docx(manifest.get("lines", []), docx_path, tables=detected_tables, title=doc_title)
                    (out_dir / "document.md").write_text(md_text, encoding="utf-8")
                    (out_dir / "document.txt").write_text(txt_text, encoding="utf-8")
                    manifest["markdown"] = md_text
                    manifest["document_text"] = txt_text

                (out_dir / "land_record.json").write_text(
                    json.dumps(l_rec, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                manifest["tables"] = detected_tables
                manifest["land_record"] = l_rec
                manifest["validation"] = l_rec.get("validation", {})
                if "documents" not in manifest:
                    manifest["documents"] = {}
                manifest["documents"]["land_record"] = f"/jobs/{job_id}/land_record.json"
        except Exception as tbl_exc:
            manifest["table_error"] = str(tbl_exc)

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
        "lines": manifest["lines"],
    }
    latent_path.write_text(json.dumps(latent_data, indent=2), encoding="utf-8")
    manifest["raw_latent"] = latent_data

    if not keep:
        shutil.rmtree(out_dir, ignore_errors=True)
        for line in manifest["lines"]:
            line.pop("url", None)

    return JSONResponse(manifest)


@app.get("/jobs/{job_id}/document.md")
def get_document_markdown(job_id: str):
    """Download the reconstructed document in Markdown (.md) format."""
    if not job_id.isalnum():
        raise HTTPException(400, "bad job id")
    path = JOBS / job_id / "document.md"
    if not path.is_file():
        raise HTTPException(404, "markdown document not found")
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown")


@app.get("/jobs/{job_id}/document.docx")
def get_document_docx(job_id: str):
    """Download the reconstructed document in Word (.docx) format."""
    if not job_id.isalnum():
        raise HTTPException(400, "bad job id")
    path = JOBS / job_id / "document.docx"
    if not path.is_file():
        raise HTTPException(404, "docx document not found")
    return FileResponse(path, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename="document.docx")


@app.get("/jobs/{job_id}/document.txt")
def get_document_text(job_id: str):
    """Download the reconstructed document in Plain Text (.txt) format."""
    if not job_id.isalnum():
        raise HTTPException(400, "bad job id")
    path = JOBS / job_id / "document.txt"
    if not path.is_file():
        raise HTTPException(404, "text document not found")
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/plain")


@app.get("/jobs/{job_id}/latent.json")
def get_document_latent(job_id: str):
    """Fetch the full raw latent JSON state of the document."""
    if not job_id.isalnum():
        raise HTTPException(400, "bad job id")
    path = JOBS / job_id / "latent.json"
    if not path.is_file():
        raise HTTPException(404, "latent representation not found")
    return FileResponse(path, media_type="application/json")


@app.get("/jobs/{job_id}/land_record.json")
def get_document_land_record(job_id: str):
    """Download the verified structured land record in DoLR/DILRMP JSON format."""
    if not job_id.isalnum():
        raise HTTPException(400, "bad job id")
    path = JOBS / job_id / "land_record.json"
    if not path.is_file():
        raise HTTPException(404, "land record document not found")
    return FileResponse(path, media_type="application/json")


@app.get("/jobs/{job_id}/lines/{index}")
def get_line(job_id: str, index: int, variant: Literal["clean", "raw"] = "clean"):
    """Fetch one line crop by its reading-order index.

    variant=clean removes neighbouring lines' ink; variant=raw is the untouched strip.
    """
    if not job_id.isalnum():
        raise HTTPException(400, "bad job id")
    folder = "lines_raw" if variant == "raw" else "lines"
    path = JOBS / job_id / folder / f"line_{index:04d}.png"
    if not path.is_file():
        raise HTTPException(404, "no such line")
    return FileResponse(path, media_type="image/png")


@app.delete("/jobs/{job_id}")
def drop_job(job_id: str):
    if not job_id.isalnum():
        raise HTTPException(400, "bad job id")
    target = JOBS / job_id
    if not target.is_dir():
        raise HTTPException(404, "no such job")
    shutil.rmtree(target, ignore_errors=True)
    return {"deleted": job_id}

