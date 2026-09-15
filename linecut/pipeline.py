"""Orchestration: image in, per-line crops and a manifest out."""
import json
import time
from pathlib import Path

import cv2
import numpy as np

from . import core, energy, lines, orient_net, seams


def segment_page(path, out_dir, device="cpu", dewarp=True, threshold=0.30, debug=False,
                 rotate_extra=0.0, src=None, auto_flip=False, filter_rules=True):
    if src is None:
        src = cv2.imread(str(path))
    if src is None:
        raise ValueError(f"cannot read image: {path}")
    started = time.time()

    # -- stage 0: scale ------------------------------------------------------
    gray = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)
    binary, _, stroke = core.measure_scale(gray)
    scaled, factor = core.normalise(src, stroke)
    if factor != 1.0:
        gray = cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)
        binary, _, stroke = core.measure_scale(gray)
    else:
        scaled = src

    # -- stage 1: orientation ------------------------------------------------
    orient = core.find_orientation(binary)
    angle = orient.angle + rotate_extra
    deskewed = core.rotate(scaled, angle, flags=cv2.INTER_LINEAR, border=(255, 255, 255))
    binary_d = core.rotate(binary, angle)
    affine, _ = core.rot_mat(scaled.shape, angle)
    inverse = cv2.invertAffineTransform(affine)

    # -- stage 2: energy -----------------------------------------------------
    cost, prob = energy.build(deskewed, binary_d, stroke=stroke, device=device)

    # -- stage 3: recursive seams --------------------------------------------
    floor = max(4.0, stroke * 4)
    pitch = seams.pitch_from_baselines(prob, min_sep=floor) if prob is not None else None
    if pitch is None:
        profile = (binary_d > 0).sum(axis=1).astype(np.float64)
        pitch = seams.line_pitch(profile, min_lag=int(floor))
    pitch = float(np.clip(pitch, floor, deskewed.shape[0] / 3))
    found = seams.find_seams(cost, pitch, threshold=threshold)
    labels = seams.label_map(found, cost.shape)

    # -- stage 4: ownership and crops ----------------------------------------
    owner = lines.assign_ownership(binary_d, labels)
    out_dir = Path(out_dir)
    crops_dir = out_dir / "lines"
    crops_dir.mkdir(parents=True, exist_ok=True)

    candidate_items = []
    rules_filtered = 0
    min_ink = max(30, int(stroke * stroke * 6))
    for band in range(int(labels.max()) + 1):
        ink = int((owner == band).sum())
        if ink < min_ink:
            continue
        crop, bbox, warped = lines.extract(deskewed, owner, band, stroke=stroke, do_dewarp=dewarp)
        if crop is None or crop.size == 0:
            continue
        if filter_rules and lines.is_graphical_rule(crop, stroke=stroke):
            rules_filtered += 1
            continue
        above = found[band - 1][1] if band > 0 else 0.0
        below = found[band][1] if band < len(found) else 0.0
        candidate_items.append((crop, bbox, warped, ink, max(above, below)))

    # Automatic 180-degree upside-down detection
    flip_prob = None
    flip_unresolved = True
    if auto_flip and orient_net.WEIGHTS.is_file() and len(candidate_items) >= 2:
        try:
            flip_prob, _ = orient_net.flip_probability([item[0] for item in candidate_items], device=device)
            if flip_prob > 0.65:
                # Page is upside down: re-run with 180 deg rotation
                return segment_page(
                    path, out_dir, device=device, dewarp=dewarp, threshold=threshold,
                    debug=debug, rotate_extra=rotate_extra + 180.0, src=src,
                    auto_flip=False, filter_rules=filter_rules,
                )
            flip_unresolved = False
        except Exception:
            pass

    records, kept = [], 0
    for crop, bbox, warped, ink, seam_cost in candidate_items:
        kept += 1
        name = f"line_{kept:04d}.png"
        cv2.imwrite(str(crops_dir / name), crop)
        records.append({
            "index": kept,
            "file": f"lines/{name}",
            "polygon_on_source": lines.polygon_on_source(bbox, inverse, factor),
            "bbox_deskewed": [int(v) for v in bbox],
            "ink_pixels": ink,
            "dewarped": bool(warped),
            "confidence": {
                "seam_cost": round(float(seam_cost), 4),
                "height_ratio": round(float(bbox[3] / pitch), 3) if pitch else None,
            },
        })

    # confidence flags: a line is suspect if a cut was expensive or the band is off-pitch
    for r in records:
        hr = r["confidence"]["height_ratio"] or 1.0
        r["confidence"]["review"] = bool(
            r["confidence"]["seam_cost"] > threshold * 0.8 or hr > 1.7 or hr < 0.45
        )

    manifest = {
        "source": str(path),
        "source_size": [int(src.shape[1]), int(src.shape[0])],
        "stroke_width_px": round(float(stroke), 2),
        "scale_factor": round(float(factor), 4),
        "angle_deg": round(float(angle), 2),
        "angle_detected_deg": round(float(orient.angle), 2),
        "rotate_extra_deg": float(rotate_extra),
        "angle_margin": round(float(orient.margin), 3) if np.isfinite(orient.margin) else None,
        "angle_uncertain": bool(np.isfinite(orient.margin) and orient.margin < 1.5),
        "reading_order": "top-to-bottom of the deskewed page",
        "flip_probability": round(float(flip_prob), 4) if flip_prob is not None else None,
        "flip_unresolved": flip_unresolved,
        "rules_filtered": rules_filtered,
        "line_pitch_px": round(float(pitch), 1),
        "energy": "learned+ink" if prob is not None else "ink-only",
        "seams": len(found),
        "lines_found": len(records),
        "lines_flagged": sum(1 for r in records if r["confidence"]["review"]),
        "seconds": round(time.time() - started, 2),
        "lines": records,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    if debug:
        _write_debug(out_dir, deskewed, cost, found, owner, prob)

    return manifest


def _write_debug(out_dir, deskewed, cost, found, owner, prob):
    d = Path(out_dir) / "debug"
    d.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(d / "energy.png"), (np.clip(cost, 0, 1) * 255).astype(np.uint8))
    if prob is not None:
        cv2.imwrite(str(d / "baseline_prob.png"), (np.clip(prob, 0, 1) * 255).astype(np.uint8))

    vis = deskewed.copy()
    for path, c in found:
        colour = (0, 0, 255) if c > 0.2 else (0, 190, 0)
        pts = np.stack([np.arange(len(path)), path], axis=1).astype(np.int32)
        cv2.polylines(vis, [pts], False, colour, 2)
    cv2.imwrite(str(d / "seams.png"), vis)

    bands = int(owner.max()) + 1
    rng = np.random.default_rng(7)
    palette = rng.integers(70, 255, (max(bands, 1), 3)).astype(np.uint8)
    tint = np.zeros_like(deskewed)
    valid = owner >= 0
    tint[valid] = palette[owner[valid]]
    cv2.imwrite(str(d / "ownership.png"), tint)
