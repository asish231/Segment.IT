"""Band-constrained line extraction, adapted from SeamFormer (Vadlamudi et al., ICDAR
2023) - https://ihdia.iiit.ac.in/seamformer/.

The ribbon approach (ribbons.py) discovers lines bottom-up from connected components of
the thresholded highlighter map, then has to stitch fragments back together - fragile,
and a wrong stitch fuses two real lines (measured and fixed once already, but the failure
mode recurs under different parameters).

This inverts the order, following SeamFormer's core idea: get a robust coarse line count
and position FIRST (from the page-wide profile, which does not fragment), then build each
line's precise spine using only the ink inside a band around that coarse position. A stray
matra a few pixels from the wrong line cannot be pulled into it - the search region
excludes it by construction, not by a heuristic gate applied after the fact.
"""
import cv2
import numpy as np


def find_centerlines(prob, pitch, min_prominence=0.15):
    """Coarse y-position of every text line, from peaks of the page-wide ink profile.

    This is the 'scribble' equivalent: robust because it looks at the whole page at
    once rather than at fragile per-component geometry.
    """
    profile = prob.sum(axis=1)
    if profile.max() <= 0:
        return []
    k = max(3, int(pitch * 0.3) | 1)
    smooth = cv2.GaussianBlur(profile.reshape(-1, 1).astype(np.float32), (1, k), 0).ravel()

    cut = smooth.max() * min_prominence
    idx = np.where((smooth[1:-1] >= smooth[:-2]) & (smooth[1:-1] > smooth[2:]) &
                   (smooth[1:-1] > cut))[0] + 1
    if idx.size == 0:
        return []

    min_sep = max(3, int(pitch * 0.5))
    kept = []
    for i in sorted(idx, key=lambda i: -smooth[i]):
        if all(abs(int(i) - k) >= min_sep for k in kept):
            kept.append(int(i))
    return sorted(kept)


def recover_missed_centerlines(prob, centers, pitch, min_frac=0.35, min_local_strength=0.06):
    """Find lines the page-wide peak search missed because they are fainter than the
    page's dominant lines.

    find_centerlines compares every peak against the page's single strongest line, so a
    genuinely present but lighter-pressure line loses to that global threshold. Checked
    locally - within just its own gap, against that gap's own local maximum - the same
    peak is often unambiguous. Located directly in the energy, not guessed: this is the
    gap-width signature, checked and confirmed against real local peak evidence before
    ever being acted on.
    """
    if len(centers) < 2:
        return centers
    profile = prob.sum(axis=1)
    if profile.max() <= 0:
        return centers
    k = max(3, int(pitch * 0.3) | 1)

    def best_local_peak(lo, hi):
        if hi - lo < 6:
            return None
        local = profile[lo:hi]
        if local.max() < profile.max() * min_local_strength:
            return None
        sm = cv2.GaussianBlur(local.reshape(-1, 1).astype(np.float32), (1, k), 0).ravel()
        cut = sm.max() * 0.35
        idx = np.where((sm[1:-1] >= sm[:-2]) & (sm[1:-1] > sm[2:]) & (sm[1:-1] > cut))[0] + 1
        if idx.size == 0:
            return None
        return lo + int(idx[np.argmax(sm[idx])])

    # only ever search BETWEEN confidently-detected lines, never past the first or last -
    # margin text (a watermark, a stray mark) lives out there and must not be reachable
    recovered = []
    for a, b in zip(centers, centers[1:]):
        lo, hi = a + int(pitch * min_frac), b - int(pitch * min_frac)
        pk = best_local_peak(lo, hi)
        if pk is None:
            continue
        recovered.append(pk)
        # a very wide gap may hide a second missed line on the far side of the first
        if (b - a) > pitch * 2.0:
            pk2 = best_local_peak(pk + int(pitch * min_frac), hi)
            if pk2 is not None and (pk2 - pk) > pitch * min_frac:
                recovered.append(pk2)

    return sorted(set(centers) | set(recovered))


def _peaks_1d(profile, pitch, rel=0.30):
    """Peaks of a single profile, scored against its own maximum."""
    if profile.max() <= 0:
        return []
    k = max(3, int(pitch * 0.3) | 1)
    sm = cv2.GaussianBlur(profile.reshape(-1, 1).astype(np.float32), (1, k), 0).ravel()
    cut = sm.max() * rel
    idx = np.where((sm[1:-1] >= sm[:-2]) & (sm[1:-1] > sm[2:]) & (sm[1:-1] > cut))[0] + 1
    min_sep = max(3, int(pitch * 0.5))
    kept = []
    for i in sorted(idx, key=lambda i: -sm[i]):
        if all(abs(int(i) - j) >= min_sep for j in kept):
            kept.append(int(i))
    return sorted(kept)


def spine_in_band(prob, ink, y_center, half_height, stroke=3.0):
    """Weighted-centroid spine using only energy inside [y_center-half, y_center+half].

    Confining the source data to a band is what SeamFormer's region mask does: a matra
    belonging to the line above cannot pull this line's centroid toward it if it falls
    outside the band entirely.
    """
    h, w = prob.shape
    y0, y1 = max(0, int(y_center - half_height)), min(h, int(y_center + half_height) + 1)
    if y1 - y0 < 3:
        return None

    band = prob[y0:y1, :].astype(np.float32)
    band_ink = ink[y0:y1, :].astype(np.float32)
    weight = band * 0.7 + (band_ink / 255.0 if band_ink.max() > 1 else band_ink) * 0.3

    cols_with_signal = np.where(weight.sum(axis=0) > weight.max() * 0.05)[0]
    if cols_with_signal.size < max(8, w * 0.05):
        return None
    x0, x1 = int(cols_with_signal.min()), int(cols_with_signal.max())

    rows = np.arange(y0, y1, dtype=np.float32).reshape(-1, 1)
    xs, ys = [], []
    last_y = float(y_center)
    for x in range(x0, x1 + 1):
        col = weight[:, x]
        total = col.sum()
        if total < weight.max() * 0.02:
            xs.append(x)
            ys.append(last_y)  # hold through a gap rather than snapping to band edge
            continue
        y = float((col * rows[:, 0]).sum() / total)
        xs.append(x)
        ys.append(y)
        last_y = y

    if len(xs) < 8:
        return None
    path = np.stack([np.array(xs, np.float32), np.array(ys, np.float32)], axis=1)
    k = min(len(path) // 2 * 2 + 1, max(5, int(stroke * 3) | 1))
    if k >= 3:
        path[:, 1] = cv2.GaussianBlur(path[:, 1].reshape(-1, 1), (1, k), 0).ravel()
    return path


def local_kinks(spine, pitch, jump_frac=0.35, window=5):
    """x-positions where a spine turns sharply - the signature of a band that is
    secretly straddling two real lines (their ink pulls the centroid alternately)
    rather than following one.

    Returns spine array indices, not raw x-coordinates, so callers can slice the path.
    """
    if len(spine) < window * 3:
        return []
    y = spine[:, 1]
    smooth = cv2.GaussianBlur(y.reshape(-1, 1), (1, window), 0).ravel()
    d1 = np.gradient(smooth)
    d2 = np.abs(np.gradient(d1))
    thresh = pitch * jump_frac / max(window, 1)
    idx = np.where(d2 > thresh)[0]
    # collapse a run of flagged points to its single sharpest point
    out = []
    for i in idx:
        if not out or i - out[-1] > window:
            out.append(int(i))
        elif d2[i] > d2[out[-1]]:
            out[-1] = int(i)
    return out


def resolve_split(prob, spine, idx, pitch, min_sep_frac=0.6):
    """At one flagged point, check whether two real lines are actually present there.

    Sums the energy in a narrow LOCAL column strip (not the whole page, so a nearby
    line doesn't contaminate the check) and looks for two resolvable peaks straddling
    the spine's own y at that point. Only acts on confirmed local evidence - this is
    what keeps it from reacting to ordinary handwriting waviness, which shows a kink
    with no second peak underneath it.
    """
    x = int(spine[idx, 0])
    y_here = float(spine[idx, 1])
    half_w = max(4, int(pitch * 0.6))
    x0, x1 = max(0, x - half_w), min(prob.shape[1], x + half_w + 1)
    y0, y1 = max(0, int(y_here - pitch * 1.5)), min(prob.shape[0], int(y_here + pitch * 1.5) + 1)
    if x1 - x0 < 4 or y1 - y0 < 6:
        return None

    strip = prob[y0:y1, x0:x1].sum(axis=1)
    peaks = find_centerlines(strip.reshape(-1, 1).repeat(2, axis=1), pitch,
                             min_prominence=0.2)
    if len(peaks) < 2:
        return None
    peaks = [p + y0 for p in peaks]

    # the two peaks must actually straddle where this spine currently sits, and be
    # far enough apart to be two lines rather than one line's own thickness
    below = [p for p in peaks if p < y_here]
    above = [p for p in peaks if p > y_here]
    if not below or not above:
        return None
    top, bot = max(below), min(above)
    if (bot - top) < pitch * min_sep_frac:
        return None
    return top, bot


def extract_banded(prob, ink, pitch, stroke=3.0, band_frac=0.55, refine=True):
    """Band-constrained extraction, then a locate-and-verify refinement pass.

    A spine flagged as kinked is only ever split when a local, narrow re-check of the
    energy confirms two real peaks straddling it - not on the kink signal alone, which
    also fires on legitimate handwriting waviness.
    """
    centers = find_centerlines(prob, pitch)
    centers = recover_missed_centerlines(prob, centers, pitch)
    half = pitch * band_frac
    spines = []
    for yc in centers:
        sp = spine_in_band(prob, ink, yc, half, stroke=stroke)
        if sp is not None:
            spines.append(sp)
    spines.sort(key=lambda s: s[:, 1].mean())

    if not refine:
        return spines

    refined = []
    recovered = 0
    for sp in spines:
        cuts = local_kinks(sp, pitch)
        confirmed = []
        for idx in cuts:
            res = resolve_split(prob, sp, idx, pitch)
            if res is not None:
                confirmed.append((idx, res))
        if not confirmed:
            refined.append(sp)
            continue

        # rebuild this spine as two: refit within each confirmed line's own band,
        # restricted to this spine's original x-span so we don't re-discover lines
        # the page-wide pass already found correctly elsewhere
        idx0 = confirmed[0][0]
        top, bot = confirmed[0][1]
        x0, x1 = float(sp[0, 0]), float(sp[-1, 0])
        for yc, lo, hi in ((top, x0, x1), (bot, x0, x1)):
            local_ink = ink.copy()
            local_ink[:, :int(lo)] = 0
            local_ink[:, int(hi) + 1:] = 0
            local_prob = prob.copy()
            local_prob[:, :int(lo)] = 0
            local_prob[:, int(hi) + 1:] = 0
            new_sp = spine_in_band(local_prob, local_ink, yc, pitch * band_frac, stroke=stroke)
            if new_sp is not None:
                refined.append(new_sp)
        recovered += 1

    refined.sort(key=lambda s: s[:, 1].mean())
    return refined


def assign_by_nearest_spine(ink, spines, shape):
    """Every ink pixel belongs to whichever spine's y-value (at that column) is closest.

    A diacritic between two lines still resolves correctly here: it is compared to each
    spine's actual interpolated position, not to a fixed band boundary.
    """
    h, w = shape
    if not spines:
        return np.full((h, w), -1, np.int32)

    curves = np.full((len(spines), w), np.nan, np.float32)
    for i, sp in enumerate(spines):
        x0, x1 = int(sp[0, 0]), int(sp[-1, 0])
        xs = np.arange(max(x0, 0), min(x1, w - 1) + 1)
        if xs.size:
            curves[i, xs] = np.interp(xs, sp[:, 0], sp[:, 1])
        # extend flat beyond each spine's own span so off-span ink still finds a home
        if x0 > 0:
            curves[i, :x0] = curves[i, x0] if x0 < w else np.nan
        if x1 < w - 1:
            curves[i, x1 + 1:] = curves[i, x1] if x1 >= 0 else np.nan

    rows = np.arange(h, dtype=np.float32).reshape(-1, 1, 1)
    dist = np.abs(rows - curves[np.newaxis, :, :])  # h x n_spines x w
    owner = np.where(np.isnan(dist), np.inf, dist).argmin(axis=1).astype(np.int32)

    # 1-indexed to match ribbons.assign's convention (0 is reserved, -1 is "no ink")
    mask = ink > 0
    result = np.full((h, w), -1, np.int32)
    result[mask] = owner[mask] + 1
    return result
