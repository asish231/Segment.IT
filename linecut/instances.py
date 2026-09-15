"""Instance-mode segmentation: one text line per ribbon, each with its own geometry.

Differs from pipeline.py in what happens after the energy map. The global pipeline
collapses the page to one angle and cuts horizontal seams. This treats every ribbon as
an independent instance, so a page may carry lines at different angles, curved lines,
and residual perspective without a global parallel-lines assumption.

A rough deskew still runs first, because the baseline network does not fire on strongly
rotated text (measured: coverage collapses ~160x at 47 degrees).
"""
import json
import time
from pathlib import Path

import cv2
import numpy as np

from . import bands, core, energy, ribbons, seams, structure


def segment_page_instances(path, out_dir, device="cpu", thresh=0.45, src=None,
                           debug=False, merge=True, method="bands", refine=True):
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

    # -- stage 1: rough deskew so the network can see the text ---------------
    orient = core.find_orientation(binary)
    deskewed = core.rotate(scaled, orient.angle, flags=cv2.INTER_LINEAR, border=(255, 255, 255))
    binary_d = core.rotate(binary, orient.angle)
    affine, _ = core.rot_mat(scaled.shape, orient.angle)
    inverse = cv2.invertAffineTransform(affine)

    # -- stage 2: highlighter map --------------------------------------------
    _, prob = energy.build(deskewed, binary_d, stroke=stroke, device=device)
    if prob is None:
        raise RuntimeError("instance mode needs the learned baseline map; it was unavailable")

    # -- stage 3: ribbons as instances ---------------------------------------
    pitch = seams.pitch_from_baselines(prob, min_sep=max(4.0, stroke * 4)) or (stroke * 8)
    pitch = float(np.clip(pitch, stroke * 4, deskewed.shape[0] / 3))

    if method == "bands":
        # coarse centerlines from the whole-page profile first, then a spine fit
        # per band - a stray matra outside the band cannot pull the wrong line's
        # centroid, because the search region excludes it by construction.
        spines = bands.extract_banded(prob, binary_d, pitch, stroke=stroke, refine=refine)
        owner = bands.assign_by_nearest_spine(binary_d, spines, binary_d.shape)
        count = len(spines)
    else:
        labels, count = ribbons.extract(prob, stroke=stroke, thresh=thresh,
                                        bridge_px=pitch * 0.9)
        raw_spines = []
        for rid in range(1, count + 1):
            pts = np.column_stack(np.nonzero(labels == rid)[::-1])  # x, y
            sp = ribbons.spine(pts, stroke=stroke)
            if sp is not None:
                raw_spines.append(sp)
        spines = ribbons.merge_fragments(raw_spines, binary_d, pitch) if merge else raw_spines

        spine_map = np.zeros(binary_d.shape, np.int32)
        for i, sp in enumerate(spines, 1):
            cv2.polylines(spine_map, [sp.astype(np.int32)], False, int(i),
                          thickness=max(1, int(stroke)))
        owner = ribbons.assign(binary_d, spine_map, max_distance=pitch * 0.85)

    out_dir = Path(out_dir)
    crops_dir = out_dir / "lines"
    crops_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "lines_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    found = []
    for rid, path_pts in enumerate(spines, 1):
        owned = owner == rid
        if owned.sum() < max(30, stroke * stroke * 6):
            continue

        strip, strip_mask = ribbons.rectify(deskewed, path_pts, height=pitch * 1.8,
                                            mask=owned)
        if strip is None:
            continue
        if ribbons.is_non_text_region(strip, mask=strip_mask):
            continue

        # Suppress only ink belonging to a NEIGHBOURING line. Masking to this line's own
        # binary ink instead would throw away every pixel the threshold missed - measured
        # at 41% of real dark pixels on a photographed page - which is what shredded
        # strokes into speckle. The binary mask decides geometry; the photo stays intact.
        others = (owner > 0) & (owner != rid)
        if others.any():
            halo = max(3, int(stroke * 2) | 1)
            others = cv2.dilate(others.astype(np.uint8),
                                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (halo, halo))) > 0
            _, others_strip = ribbons.rectify(deskewed, path_pts, height=pitch * 1.8,
                                              mask=others)
        else:
            others_strip = None

        crop = strip.copy()
        if others_strip is not None:
            crop[others_strip] = 255
        crop = ribbons.trim(crop, strip_mask, pad=int(max(3, stroke * 2)))
        if crop.size == 0:
            continue

        found.append({
            "spine": path_pts,
            "crop": crop,
            "raw": ribbons.trim(strip.copy(), strip_mask, pad=int(max(3, stroke * 2))),
            "ink": int(owned.sum()),
            "angle": ribbons.angle_of(path_pts),
            "curvature": ribbons.curvature_of(path_pts),
            "centre": [float(path_pts[:, 0].mean()), float(path_pts[:, 1].mean())],
        })

    # reading order: top to bottom, then left to right within a line band
    found.sort(key=lambda f: (round(f["centre"][1] / max(pitch * 0.6, 1)), f["centre"][0]))

    # -- stage 6: page structure (rules, rows, per-row fields) ----------------
    h_rules, v_rules = structure.find_rules(binary_d)
    gutters = structure.page_gutters(binary_d)
    layout = structure.classify(h_rules, v_rules, len(gutters))
    rows = structure.assign_rows([f["centre"][1] for f in found], h_rules, pitch)

    records = []
    for i, item in enumerate(found, 1):
        name = f"line_{i:04d}.png"
        cv2.imwrite(str(crops_dir / name), item["crop"])
        if item.get("raw") is not None and item["raw"].size:
            cv2.imwrite(str(raw_dir / name), item["raw"])
        fields = structure.split_fields(item["crop"])
        sp = item["spine"]
        poly = ribbons.outline(sp, pitch * 1.2)
        back = (inverse @ np.hstack([poly, np.ones((len(poly), 1), np.float32)]).T).T / factor
        spine_back = (inverse @ np.hstack([sp, np.ones((len(sp), 1), np.float32)]).T).T / factor
        records.append({
            "index": i,
            "file": f"lines/{name}",
            "file_raw": f"lines_raw/{name}",
            "angle_deg": round(item["angle"], 2),
            "curvature_px": round(item["curvature"], 2),
            "ink_pixels": item["ink"],
            "row": int(rows.get(i - 1, i - 1)),
            "fields": [{"x0": int(a), "x1": int(b)} for a, b in fields],
            "size": [int(item["crop"].shape[1]), int(item["crop"].shape[0])],
            "spine_on_source": [[round(float(x), 1), round(float(y), 1)] for x, y in spine_back],
            "spine_deskewed": [[round(float(x), 1), round(float(y), 1)] for x, y in sp],
            "polygon_on_source": [[round(float(x), 1), round(float(y), 1)] for x, y in back],
            "confidence": {
                "curved": bool(item["curvature"] > stroke * 2),
                "off_axis_deg": round(abs(item["angle"]), 2),
                "review": bool(item["curvature"] > pitch * 0.5 or item["ink"] < stroke * stroke * 12),
            },
        })

    manifest = {
        "mode": "instances",
        "method": method,
        "source": str(path),
        "source_size": [int(src.shape[1]), int(src.shape[0])],
        "stroke_width_px": round(float(stroke), 2),
        "scale_factor": round(float(factor), 4),
        "deskew_deg": round(float(orient.angle), 2),
        "deskew_margin": round(float(orient.margin), 3) if np.isfinite(orient.margin) else None,
        "line_pitch_px": round(pitch, 1),
        "layout": layout,
        "rules_horizontal": len(h_rules),
        "rules_vertical": len(v_rules),
        "column_gutters": len(gutters),
        "rows": (max(rows.values()) + 1) if rows else 0,
        "ribbons_detected": count,
        "ribbons_after_merge": len(spines),
        "lines_found": len(records),
        "lines_curved": sum(1 for r in records if r["confidence"]["curved"]),
        "lines_flagged": sum(1 for r in records if r["confidence"]["review"]),
        "angle_spread_deg": round(float(np.ptp([r["angle_deg"] for r in records])), 2) if records else 0.0,
        "flip_unresolved": True,
        "flip_note": ("If downstream recognition finds the page inverted, rotate each "
                      "crop 180 degrees AND reverse the line order - index 1 is then "
                      "the last line, not the first."),
        "reading_order": "top-to-bottom by spine centre, then left-to-right",
        "seconds": round(time.time() - started, 2),
        "lines": records,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # Stack every line back into one page. Two uses: it is a cleaned, deskewed,
    # background-free version of the document, and it doubles as a verification view -
    # if a line is missing, duplicated or mangled, reading the stack top to bottom
    # shows it immediately in a way a per-line list does not.
    if found:
        gap = max(4, int(pitch * 0.12))
        width = max(f["crop"].shape[1] for f in found)
        tiles = []
        for f in found:
            c = f["crop"]
            tiles.append(cv2.copyMakeBorder(c, 0, gap, 0, width - c.shape[1],
                                            cv2.BORDER_CONSTANT, value=(255, 255, 255)))
        cv2.imwrite(str(out_dir / "page_reassembled.png"), np.vstack(tiles))

    if debug:
        _debug(out_dir, deskewed, prob, owner, found, pitch)
    return manifest


def _debug(out_dir, deskewed, prob, owner, found, pitch):
    d = Path(out_dir) / "debug"
    d.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(d / "highlighter.png"), (np.clip(prob, 0, 1) * 255).astype(np.uint8))

    rng = np.random.default_rng(3)
    palette = rng.integers(60, 255, (int(owner.max()) + 2, 3)).astype(np.uint8)
    tint = np.zeros((*owner.shape, 3), np.uint8)
    valid = owner >= 0
    tint[valid] = palette[owner[valid]]
    cv2.imwrite(str(d / "ownership.png"), tint)

    vis = deskewed.copy()
    for i, item in enumerate(found, 1):
        sp = item["spine"].astype(np.int32)
        cv2.polylines(vis, [sp], False, (0, 90, 255), 2)
        poly = ribbons.outline(item["spine"], pitch * 1.2).astype(np.int32)
        cv2.polylines(vis, [poly], True, (0, 200, 0), 1)
        cv2.putText(vis, str(i), tuple(sp[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
    cv2.imwrite(str(d / "instances.png"), vis)
