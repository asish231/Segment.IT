"""Stages 0-1: scale normalisation and global orientation."""
from dataclasses import dataclass

import cv2
import numpy as np

TARGET_STROKE = 3.0


def _odd(v):
    v = int(v)
    return v + 1 if v % 2 == 0 else v


def estimate_background(gray, radius):
    """Low-frequency page illumination, via median blur on a downscaled copy."""
    step = max(1, radius // 8)
    small = cv2.resize(gray, None, fx=1 / step, fy=1 / step, interpolation=cv2.INTER_AREA)
    k = _odd(max(3, min(radius // step, 51)))
    bg = cv2.medianBlur(small, k)
    return cv2.resize(bg, (gray.shape[1], gray.shape[0]), interpolation=cv2.INTER_LINEAR)


def binarize(gray, radius=None):
    """Ink map and binary mask, with the page's own illumination divided out."""
    if radius is None:
        radius = max(15, min(gray.shape) // 15)
    bg = estimate_background(gray, radius)
    ink = cv2.subtract(bg, gray)
    _, binary = cv2.threshold(ink, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    binary = cv2.medianBlur(binary, 3)
    return binary, ink


def stroke_width(binary):
    """Modal pen width in pixels, from ridge values of the distance transform."""
    dist = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
    local_max = cv2.dilate(dist, np.ones((3, 3), np.uint8))
    ridge = (dist > 0.5) & (dist >= local_max - 1e-6)
    vals = dist[ridge]
    if vals.size < 20:
        return 2.0
    return float(2.0 * np.median(vals))


def measure_scale(gray):
    """Two-pass: rough binary to read the pen width, then a background radius that suits it."""
    rough, _ = binarize(gray)
    sw = stroke_width(rough)
    binary, ink = binarize(gray, radius=max(15, int(sw * 12)))
    sw = stroke_width(binary)
    return binary, ink, sw


def normalise(img, sw, target=TARGET_STROKE, clamp=(0.35, 4.0)):
    """Resample so one pen stroke is `target` pixels wide, making every later constant scale-free."""
    factor = float(np.clip(target / max(sw, 0.5), *clamp))
    if abs(factor - 1.0) < 0.05:
        return img, 1.0
    out = cv2.resize(img, None, fx=factor, fy=factor,
                     interpolation=cv2.INTER_AREA if factor < 1 else cv2.INTER_CUBIC)
    return out, factor


def rot_mat(shape, angle):
    """Rotation matrix plus the expanded canvas that keeps every corner inside."""
    h, w = shape[:2]
    cx, cy = w / 2, h / 2
    M = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)
    cos, sin = abs(M[0, 0]), abs(M[0, 1])
    nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)
    M[0, 2] += nw / 2 - cx
    M[1, 2] += nh / 2 - cy
    return M, (nw, nh)


def rotate(img, angle, flags=cv2.INTER_NEAREST, border=0):
    M, size = rot_mat(img.shape, angle)
    return cv2.warpAffine(img, M, size, flags=flags, borderValue=border)


@dataclass
class Orientation:
    angle: float
    margin: float


def find_orientation(binary, coarse_step=1.0, fine_step=0.2):
    """Sweep the full 180 deg; the text angle is where the row profile has maximum variance.

    Variance, not roughness: strokes are rough at every angle, but only at the true
    angle does the page resolve into dense bands separated by empty gaps.
    """
    small = cv2.resize(binary, None, fx=0.4, fy=0.4, interpolation=cv2.INTER_NEAREST)

    def score(angle):
        prof = rotate(small, angle).sum(axis=1).astype(np.float64)
        total = prof.sum()
        if total == 0:
            return 0.0
        return float((prof / total).var())

    coarse = np.arange(-90, 90, coarse_step)
    scores = np.array([score(a) for a in coarse])
    best_coarse = float(coarse[scores.argmax()])

    fine = np.arange(best_coarse - 2, best_coarse + 2 + 1e-9, fine_step)
    fine_scores = np.array([score(a) for a in fine])
    angle = float(fine[fine_scores.argmax()])

    # how decisively did it beat the best rival more than 10 deg away?
    far = np.abs(((coarse - best_coarse + 90) % 180) - 90) > 10
    margin = float(scores.max() / scores[far].max()) if far.any() and scores[far].max() > 0 else float("inf")
    return Orientation(angle=angle, margin=margin)
