"""Tier 0 Non-Text & Stamp Area Extractor.

Detects large, ornate, non-text graphic regions (such as revenue stamp medallions,
coat of arms, guilloche security patterns, court fee stamps, wax/ink seals).

These regions have distinct high isotropic edge density (3x-4x higher than prose
or tables) and large contiguous areas.

Masking them out in Tier 0 prevents the seam carver / line detector from slicing
through emblems and prevents OCR decoders from hallucinating over engravings.
"""

from typing import List, Dict, Any, Optional
import numpy as np
import cv2
from pathlib import Path


def detect_stamps(
    src_bgr: np.ndarray,
    detected_tables: Optional[List[Dict[str, Any]]] = None,
    min_density: float = 0.20,
    min_height_px: int = 25,
) -> List[Dict[str, Any]]:
    """Detect non-text stamp medallions, crests, and guilloche security regions.

    Parameters
    ----------
    src_bgr : np.ndarray
        Source BGR document image.
    detected_tables : Optional[List[Dict[str, Any]]]
        Already detected tables to exclude from edge density calculations.
    min_density : float
        Minimum edge pixel density to qualify as an ornate engraved region (default 0.20).
    min_height_px : int
        Minimum height in pixels to qualify as a non-text block (default 25).

    Returns
    -------
    List[Dict[str, Any]]
        List of detected stamp/medallion objects with bounding boxes and metadata.
    """
    if src_bgr is None or src_bgr.size == 0:
        return []

    H, W = src_bgr.shape[:2]
    gray = cv2.cvtColor(src_bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)

    # Exclude table regions from edge density measurement
    if detected_tables:
        for t in detected_tables:
            tx, ty, tw, th = t.get("bbox", [0, 0, 0, 0])
            if tw > 0 and th > 0:
                y0, y1 = max(0, ty), min(H, ty + th)
                x0, x1 = max(0, tx), min(W, tx + tw)
                edges[y0:y1, x0:x1] = 0

    # 1. Compute horizontal edge density projection across rows
    row_densities = np.mean(edges > 0, axis=1)

    # Smooth with moving average window
    win_size = min(25, max(5, H // 25))
    kernel = np.ones(win_size) / win_size
    smoothed = np.convolve(row_densities, kernel, mode="same")

    # 2. Identify vertical bands where smoothed edge density >= min_density
    in_stamp = False
    start_y = 0
    stamp_bands = []
    for y, d in enumerate(smoothed):
        if d >= min_density and not in_stamp:
            in_stamp = True
            start_y = y
        elif d < (min_density - 0.02) and in_stamp:
            in_stamp = False
            if (y - start_y) >= min_height_px:
                stamp_bands.append((start_y, y))
    if in_stamp and (H - start_y) >= min_height_px:
        stamp_bands.append((start_y, H))

    stamps = []
    for i, (sy, ey) in enumerate(stamp_bands):
        # Within the vertical band, determine horizontal extent
        band_edges = edges[sy:ey, :]
        col_densities = np.mean(band_edges > 0, axis=0)
        cols_active = np.where(col_densities > 0.04)[0]
        if len(cols_active) > 0:
            x0 = max(0, int(cols_active[0]))
            x1 = min(W, int(cols_active[-1] + 1))
            w = x1 - x0
            h = ey - sy

            # Filter: A valid stamp medallion must span a substantial width (>= 25% page width)
            if w >= int(W * 0.25) and h >= min_height_px:
                density = float(np.sum(edges[sy:ey, x0:x1] > 0) / (w * h))
                stamps.append({
                    "stamp_id": i + 1,
                    "bbox": [x0, sy, w, h],
                    "type": "revenue_stamp_medallion",
                    "edge_density": round(density, 4),
                })

    return stamps


def extract_and_save_stamps(
    stamps: List[Dict[str, Any]],
    src_bgr: np.ndarray,
    out_dir: Path,
) -> List[Dict[str, Any]]:
    """Save cropped stamp images and attach file references."""
    if not stamps or src_bgr is None:
        return stamps

    stamps_dir = out_dir / "stamps"
    stamps_dir.mkdir(parents=True, exist_ok=True)
    H, W = src_bgr.shape[:2]

    for s in stamps:
        x, y, w, h = s["bbox"]
        x0 = max(0, min(W - 1, x))
        y0 = max(0, min(H - 1, y))
        x1 = max(x0 + 1, min(W, x0 + w))
        y1 = max(y0 + 1, min(H, y0 + h))
        crop = src_bgr[y0:y1, x0:x1]
        fname = f"stamp_{s['stamp_id']:02d}.png"
        fpath = stamps_dir / fname
        cv2.imwrite(str(fpath), crop)
        s["file"] = str(fpath.relative_to(out_dir))
        s["file_abs"] = str(fpath)

    return stamps
