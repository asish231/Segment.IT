#!/usr/bin/env python
"""HTTP API: POST an image, get its text lines back in reading order.

    uvicorn api:app --host 0.0.0.0 --port 8000

    curl -F image=@page.png http://localhost:8000/segment > out.json

Lines come back as a list already sorted top-to-bottom of the deskewed page, each
with a 1-based `index`. Iterate the list as-is to process the page in order.
"""
import base64
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Literal, Optional

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from linecut import segment_page

app = FastAPI(
    title="linecut",
    description="Segments document images into ordered, indexed text-line crops.",
    version="1.0",
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
    threshold: float = Form(0.30, description="Max seam cost to accept a cut"),
    dewarp: bool = Form(True, description="Straighten each line before cropping"),
    rotate: float = Form(0.0, description="Extra rotation in degrees, added to the detected angle"),
    include_images: bool = Form(True, description="Inline base64 PNG per line"),
    keep: bool = Form(True, description="Keep crops on disk for /jobs fetches"),
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
    try:
        manifest = segment_page(
            image.filename or "upload", out_dir,
            device=device, dewarp=dewarp, threshold=threshold,
            rotate_extra=rotate, src=decoded,
        )
    except Exception as exc:
        shutil.rmtree(out_dir, ignore_errors=True)
        raise HTTPException(500, f"segmentation failed: {exc}") from exc

    manifest["job_id"] = job_id
    manifest["source"] = image.filename

    if include_images:
        for line in manifest["lines"]:
            data = (out_dir / line["file"]).read_bytes()
            line["png_base64"] = base64.b64encode(data).decode()

    for line in manifest["lines"]:
        line["url"] = f"/jobs/{job_id}/lines/{line['index']}"

    if not keep:
        shutil.rmtree(out_dir, ignore_errors=True)
        for line in manifest["lines"]:
            line.pop("url", None)

    return JSONResponse(manifest)


@app.get("/jobs/{job_id}/lines/{index}")
def get_line(job_id: str, index: int):
    """Fetch one line crop by its reading-order index."""
    if not job_id.isalnum():
        raise HTTPException(400, "bad job id")
    path = JOBS / job_id / "lines" / f"line_{index:04d}.png"
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
