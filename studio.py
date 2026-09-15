#!/usr/bin/env python
"""Annotation studio: correct pre-filled baselines instead of drawing them.

    uvicorn studio:app --port 8100      # then open http://localhost:8100

Set LINECUT_DATA to point at a directory of page images (default: datasets/raw).
Annotations are stored as JSON next to the dataset and exported to PAGE-XML, the
format kraken trains from.
"""
import hashlib
import io
import json
import os
from pathlib import Path
from xml.sax.saxutils import escape

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from pydantic import BaseModel

from linecut import core

DATA_ROOT = Path(os.environ.get("LINECUT_DATA", "datasets/raw")).resolve()
ANNO_ROOT = Path(os.environ.get("LINECUT_ANNOTATIONS", "datasets/annotations")).resolve()
EXPORT_ROOT = Path(os.environ.get("LINECUT_EXPORT", "datasets/pagexml")).resolve()
UI = Path(__file__).parent / "studio_ui" / "index.html"

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
DISPLAY_MAX = 1500

ANNO_ROOT.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="linecut studio")


def resolve(rel: str) -> Path:
    """Resolve a dataset-relative path, refusing anything outside the root."""
    target = (DATA_ROOT / rel).resolve()
    if not str(target).startswith(str(DATA_ROOT)) or not target.is_file():
        raise HTTPException(404, "no such page")
    return target


def anno_path(rel: str) -> Path:
    digest = hashlib.sha1(rel.encode()).hexdigest()[:16]
    return ANNO_ROOT / f"{digest}.json"


def list_pages():
    pages = []
    for path in sorted(DATA_ROOT.rglob("*")):
        if path.suffix.lower() not in IMAGE_EXT or not path.is_file():
            continue
        rel = str(path.relative_to(DATA_ROOT))
        saved = anno_path(rel)
        state = {"lines": 0, "done": False}
        if saved.is_file():
            try:
                data = json.loads(saved.read_text())
                state = {"lines": len(data.get("baselines", [])), "done": bool(data.get("done"))}
            except Exception:
                pass
        pages.append({"path": rel, "group": rel.split(os.sep)[0] if os.sep in rel else "", **state})
    return pages


@app.get("/", response_class=HTMLResponse)
def index():
    if not UI.is_file():
        raise HTTPException(500, "studio_ui/index.html missing")
    return HTMLResponse(UI.read_text())


@app.get("/api/pages")
def pages():
    items = list_pages()
    return {
        "root": str(DATA_ROOT),
        "total": len(items),
        "annotated": sum(1 for p in items if p["lines"]),
        "done": sum(1 for p in items if p["done"]),
        "pages": items,
    }


@app.get("/api/image")
def image(path: str = Query(...)):
    src = resolve(path)
    img = cv2.imread(str(src), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(415, "cannot decode image")
    h, w = img.shape[:2]
    scale = min(1.0, DISPLAY_MAX / max(h, w))
    if scale < 1.0:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    if not ok:
        raise HTTPException(500, "encode failed")
    return Response(
        content=buf.tobytes(),
        media_type="image/jpeg",
        headers={"X-Source-Width": str(w), "X-Source-Height": str(h),
                 "X-Display-Scale": f"{scale:.6f}"},
    )


@app.get("/api/meta")
def meta(path: str = Query(...)):
    src = resolve(path)
    img = cv2.imread(str(src), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(415, "cannot decode image")
    h, w = img.shape[:2]
    return {"path": path, "width": w, "height": h,
            "display_scale": min(1.0, DISPLAY_MAX / max(h, w))}


@app.post("/api/prefill")
def prefill(path: str = Query(...), device: str = Query("cpu")):
    """Run detection and return baselines in SOURCE pixel coordinates."""
    src = resolve(path)
    img = cv2.imread(str(src), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(415, "cannot decode image")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    binary, _, _ = core.measure_scale(gray)
    orient = core.find_orientation(binary)

    deskewed = core.rotate(img, orient.angle, flags=cv2.INTER_LINEAR, border=(255, 255, 255))
    affine, _ = core.rot_mat(img.shape, orient.angle)
    inverse = cv2.invertAffineTransform(affine)

    try:
        from importlib import resources
        from PIL import Image
        import kraken.blla as blla
        from kraken.lib import vgsl

        global _SEG_MODEL
        try:
            model = _SEG_MODEL
        except NameError:
            model = None
        if model is None:
            model = vgsl.TorchVGSLModel.load_model(
                resources.files("kraken").joinpath("blla.mlmodel"))
            globals()["_SEG_MODEL"] = model

        pil = Image.fromarray(cv2.cvtColor(deskewed, cv2.COLOR_BGR2RGB))
        seg = blla.segment(pil, model=model, device=device)
    except Exception as exc:
        raise HTTPException(500, f"detection failed: {exc}") from exc

    baselines = []
    for line in seg.lines:
        if not line.baseline or len(line.baseline) < 2:
            continue
        pts = np.array(line.baseline, np.float32)
        back = (inverse @ np.hstack([pts, np.ones((len(pts), 1), np.float32)]).T).T
        baselines.append([[round(float(x), 1), round(float(y), 1)] for x, y in back])

    baselines.sort(key=lambda b: sum(p[1] for p in b) / len(b))
    return {"path": path, "angle": round(float(orient.angle), 2),
            "margin": round(float(orient.margin), 3) if np.isfinite(orient.margin) else None,
            "baselines": baselines}


class Annotation(BaseModel):
    path: str
    baselines: list[list[list[float]]]
    done: bool = False
    note: str = ""


@app.get("/api/annotation")
def get_annotation(path: str = Query(...)):
    saved = anno_path(path)
    if not saved.is_file():
        return {"path": path, "baselines": [], "done": False, "note": ""}
    return JSONResponse(json.loads(saved.read_text()))


@app.post("/api/annotation")
def put_annotation(anno: Annotation):
    resolve(anno.path)
    payload = anno.model_dump()
    anno_path(anno.path).write_text(json.dumps(payload, indent=1))
    return {"saved": anno.path, "lines": len(anno.baselines), "done": anno.done}


@app.delete("/api/annotation")
def clear_annotation(path: str = Query(...)):
    saved = anno_path(path)
    if saved.is_file():
        saved.unlink()
    return {"cleared": path}


def page_xml(rel, width, height, baselines):
    lines = []
    for i, bl in enumerate(baselines, 1):
        coords = " ".join(f"{int(round(x))},{int(round(y))}" for x, y in bl)
        ys = [y for _, y in bl]
        xs = [x for x, _ in bl]
        pad = max(8, int((max(ys) - min(ys)) * 0.5) + 12)
        poly = (f"{int(min(xs))},{int(min(ys))-pad} {int(max(xs))},{int(min(ys))-pad} "
                f"{int(max(xs))},{int(max(ys))+pad} {int(min(xs))},{int(max(ys))+pad}")
        lines.append(
            f'      <TextLine id="line_{i}">\n'
            f'        <Coords points="{poly}"/>\n'
            f'        <Baseline points="{coords}"/>\n'
            f'      </TextLine>'
        )
    body = "\n".join(lines)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<PcGts xmlns="http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15">
  <Metadata>
    <Creator>linecut studio</Creator>
  </Metadata>
  <Page imageFilename="{escape(rel)}" imageWidth="{width}" imageHeight="{height}">
    <TextRegion id="region_1">
      <Coords points="0,0 {width},0 {width},{height} 0,{height}"/>
{body}
    </TextRegion>
  </Page>
</PcGts>
"""


@app.post("/api/export")
def export(only_done: bool = Query(True)):
    """Write PAGE-XML for every annotated page, alongside a copy of the image path list."""
    EXPORT_ROOT.mkdir(parents=True, exist_ok=True)
    written, skipped = [], 0
    for page in list_pages():
        if not page["lines"] or (only_done and not page["done"]):
            skipped += 1
            continue
        rel = page["path"]
        data = json.loads(anno_path(rel).read_text())
        src = resolve(rel)
        img = cv2.imread(str(src), cv2.IMREAD_COLOR)
        if img is None:
            skipped += 1
            continue
        h, w = img.shape[:2]
        out = EXPORT_ROOT / (Path(rel).with_suffix(".xml").name)
        out.write_text(page_xml(rel, w, h, data["baselines"]))
        written.append({"image": str(src), "xml": str(out), "lines": len(data["baselines"])})

    manifest = EXPORT_ROOT / "index.json"
    manifest.write_text(json.dumps({"pages": written}, indent=1))
    return {"exported": len(written), "skipped": skipped, "dir": str(EXPORT_ROOT),
            "manifest": str(manifest)}
