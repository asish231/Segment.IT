"""Stages 4-5: pixel ownership, dewarping, cropping.

Ownership is decided per connected component where a component clearly belongs to one
band, and per pixel where it genuinely straddles a seam. That keeps a descender whole
when it belongs to one line, and splits it along the seam when two lines share ink.
"""
from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class Line:
    index: int
    bbox: tuple
    polygon: list = field(default_factory=list)
    seam_cost: float = 0.0
    height_ratio: float = 1.0
    ink_pixels: int = 0
    dewarped: bool = False


def assign_ownership(binary, labels, dominance=0.8):
    """Owner band per ink pixel; -1 where there is no ink."""
    mask = (binary > 0).astype(np.uint8)
    n, comp, _, _ = cv2.connectedComponentsWithStats(mask, 8)
    bands = int(labels.max()) + 1

    key = comp.astype(np.int64) * bands + labels
    counts = np.bincount(key.ravel(), minlength=n * bands).reshape(n, bands)
    counts[0] = 0

    dominant = counts.argmax(axis=1)
    totals = counts.sum(axis=1)
    share = counts[np.arange(n), dominant] / np.maximum(totals, 1)
    whole = share >= dominance

    owner = np.where(whole[comp], dominant[comp], labels)
    owner[mask == 0] = -1
    return owner


def _column_centre(mask_band, weights=None):
    """Ink centre of gravity per column, NaN where the column is empty."""
    m = mask_band.astype(np.float32)
    if weights is not None:
        m = m * weights
    rows = np.arange(m.shape[0], dtype=np.float32).reshape(-1, 1)
    total = m.sum(axis=0)
    centre = (m * rows).sum(axis=0) / np.where(total > 0, total, np.nan)
    return centre, total


def dewarp(crop, mask, stroke=3.0, min_amplitude=1.5):
    """Flatten a wavy line by shifting each column so its ink centre runs level."""
    centre, total = _column_centre(mask)
    valid = np.isfinite(centre) & (total > stroke)
    if valid.sum() < max(12, crop.shape[1] * 0.2):
        return crop, mask, False

    xs = np.arange(crop.shape[1], dtype=np.float32)
    filled = np.interp(xs, xs[valid], centre[valid])
    k = max(3, int(crop.shape[1] * 0.12) | 1)
    smooth = cv2.GaussianBlur(filled.reshape(-1, 1), (1, k), 0).ravel()

    shift = smooth.mean() - smooth
    if np.abs(shift).max() < min_amplitude:
        return crop, mask, False

    h, w = crop.shape[:2]
    map_x = np.tile(xs, (h, 1)).astype(np.float32)
    map_y = (np.arange(h, dtype=np.float32).reshape(-1, 1) - shift.reshape(1, -1)).astype(np.float32)

    warped = cv2.remap(crop, map_x, map_y, cv2.INTER_CUBIC,
                       borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
    warped_mask = cv2.remap(mask.astype(np.uint8) * 255, map_x, map_y, cv2.INTER_NEAREST,
                            borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    return warped, warped_mask > 0, True


def extract(bgr, owner, index, stroke=3.0, pad=None, do_dewarp=True):
    """Mask everything this line does not own, crop tight, optionally straighten."""
    mask = owner == index
    if not mask.any():
        return None, None

    ys, xs = np.nonzero(mask)
    pad = int(pad if pad is not None else stroke * 3)
    y0, y1 = max(int(ys.min()) - pad, 0), min(int(ys.max()) + pad + 1, bgr.shape[0])
    x0, x1 = max(int(xs.min()) - pad, 0), min(int(xs.max()) + pad + 1, bgr.shape[1])

    sub = bgr[y0:y1, x0:x1]
    sub_mask = mask[y0:y1, x0:x1].astype(np.uint8)

    # grow slightly so the anti-aliased halo around each stroke comes with it
    grow = max(3, int(stroke) | 1)
    soft = cv2.dilate(sub_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (grow, grow)))

    white = np.full_like(sub, 255)
    crop = np.where(soft[:, :, None] > 0, sub, white)

    warped = False
    if do_dewarp:
        crop, soft_bool, warped = dewarp(crop, sub_mask > 0, stroke)
        if warped:
            crop = np.where(np.asarray(soft_bool)[:, :, None] > 0, crop, 255).astype(np.uint8)

    return crop, (x0, y0, x1 - x0, y1 - y0), warped


def polygon_on_source(bbox, inv_affine, scale_factor):
    """Line box mapped back through the deskew and the scale normalisation."""
    x, y, w, h = bbox
    pts = np.array([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], np.float32)
    back = (inv_affine @ np.hstack([pts, np.ones((4, 1), np.float32)]).T).T
    back = back / scale_factor
    return [[round(float(px), 1), round(float(py), 1)] for px, py in back]


def is_graphical_rule(crop, stroke=3.0):
    """Detects solid horizontal printed rules and table borders vs real text lines."""
    if crop is None or crop.size == 0:
        return False
    h, w = crop.shape[:2]
    if w < 20 or h < 2:
        return False
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    _, bin_inv = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
    if not (bin_inv > 0).any():
        return False
    n, labels, stats, _ = cv2.connectedComponentsWithStats(bin_inv, 8)
    if n <= 1:
        return False
    max_cw = max((stats[i, cv2.CC_STAT_WIDTH] for i in range(1, n)), default=0)
    ys, xs = np.nonzero(bin_inv)
    ink_h = int(ys.max() - ys.min() + 1)
    ink_w = int(xs.max() - xs.min() + 1)
    aspect = ink_w / max(1, ink_h)
    # A continuous rule stroke spanning >40% of crop width, very high aspect ratio, and few components
    return bool(max_cw > w * 0.40 and ink_h < max(35, stroke * 10) and aspect > 10.0 and (n - 1) <= 6)

