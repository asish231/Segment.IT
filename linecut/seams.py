"""Stage 3: recursive seam splitting.

A cut is not a straight row. It enters at the left edge, leaves at the right, and may
step one pixel up or down per column, so it travels around descenders instead of
through them. Dynamic programming finds the globally cheapest such path in one pass.
"""
import cv2
import numpy as np


def carve_seam(cost):
    """Cheapest left-to-right path through `cost`. Returns (row per column, mean cost)."""
    h, w = cost.shape
    if h < 3 or w < 2:
        return np.zeros(w, np.int32), float(cost.mean())

    acc = cost.astype(np.float64).copy()
    back = np.zeros((h, w), np.int8)

    for x in range(1, w):
        prev = acc[:, x - 1]
        up = np.empty_like(prev)
        up[0] = np.inf
        up[1:] = prev[:-1]
        down = np.empty_like(prev)
        down[-1] = np.inf
        down[:-1] = prev[1:]
        options = np.stack([up, prev, down])
        choice = np.argmin(options, axis=0)
        acc[:, x] += options[choice, np.arange(h)]
        back[:, x] = choice

    y = int(np.argmin(acc[:, -1]))
    total = float(acc[y, -1])
    path = np.empty(w, np.int32)
    path[-1] = y
    for x in range(w - 1, 0, -1):
        y = int(np.clip(y + int(back[y, x]) - 1, 0, h - 1))
        path[x - 1] = y
    return path, total / w


def _peaks(signal, min_sep, rel_height=0.25):
    """Local maxima above a fraction of the peak, thinned to a minimum separation."""
    if signal.max() <= 0:
        return np.array([], np.int32)
    k = max(3, int(min_sep) | 1)
    smooth = cv2.GaussianBlur(signal.reshape(-1, 1).astype(np.float32), (1, k), 0).ravel()
    cut = smooth.max() * rel_height
    idx = np.where((smooth[1:-1] >= smooth[:-2]) & (smooth[1:-1] > smooth[2:]) &
                   (smooth[1:-1] > cut))[0] + 1
    keep = []
    for i in idx:
        if not keep or i - keep[-1] >= min_sep:
            keep.append(int(i))
        elif smooth[i] > smooth[keep[-1]]:
            keep[-1] = int(i)
    return np.array(keep, np.int32)


def pitch_from_baselines(prob, min_sep):
    """Line spacing from the learned map: one ridge per text line, so count the ridges."""
    profile = prob.sum(axis=1)
    peaks = _peaks(profile, min_sep=max(3, int(min_sep)))
    if peaks.size < 2:
        return None
    return float(np.median(np.diff(peaks)))


def line_pitch(profile, min_lag=4):
    """Fallback spacing from autocorrelation, skipping the main lobe before peak-picking."""
    p = profile.astype(np.float64)
    p = p - p.mean()
    if not np.any(p):
        return float(max(len(profile) // 10, min_lag))
    ac = np.correlate(p, p, mode="full")[len(p) - 1:]
    if ac[0] > 0:
        ac = ac / ac[0]

    i = 1
    while i < len(ac) - 1 and ac[i] < ac[i - 1]:
        i += 1
    start = max(i, min_lag)
    hi = max(start + 2, len(ac) // 2)
    window = ac[start:hi]
    if window.size == 0:
        return float(max(len(profile) // 10, min_lag))
    return float(start + int(np.argmax(window)))


def _candidate_rows(prof, pitch, limit=8):
    """Local minima of the smoothed profile, cheapest first."""
    k = max(3, int(pitch * 0.25) | 1)
    smooth = cv2.GaussianBlur(prof.reshape(-1, 1).astype(np.float32), (1, k), 0).ravel()
    idx = np.where((smooth[1:-1] <= smooth[:-2]) & (smooth[1:-1] <= smooth[2:]))[0] + 1
    if idx.size == 0:
        idx = np.array([int(np.argmin(smooth))])
    return idx[np.argsort(smooth[idx])][:limit]


def find_seams(cost, pitch, threshold=0.30, max_depth=14):
    """Recursively split the page, returning one seam path per accepted cut."""
    h, w = cost.shape
    seams = []
    min_half = max(3.0, pitch * 0.45)

    def recurse(y0, y1, depth):
        height = y1 - y0
        if depth >= max_depth or height < pitch * 1.6:
            return

        prof = cost[y0:y1].mean(axis=1)
        margin = int(max(2, min_half))
        if height - 2 * margin < 3:
            return

        best = None
        for rel in _candidate_rows(prof, pitch):
            yc = y0 + int(rel)
            if yc - y0 < min_half or y1 - yc < min_half:
                continue
            half = max(2, int(pitch * 0.4))
            top, bot = max(y0, yc - half), min(y1, yc + half + 1)
            if bot - top < 3:
                continue
            path, mean_cost = carve_seam(cost[top:bot, :])
            path = path + top
            if path.min() - y0 < min_half or y1 - path.max() < min_half:
                continue
            if best is None or mean_cost < best[1]:
                best = (path, mean_cost)

        if best is None or best[1] > threshold:
            return

        path, mean_cost = best
        seams.append((path, mean_cost))
        mid = int(path.mean())
        recurse(y0, mid, depth + 1)
        recurse(mid, y1, depth + 1)

    recurse(0, h, 0)
    seams.sort(key=lambda s: s[0].mean())
    return seams


def label_map(seams, shape):
    """Band index per pixel: 0 above the first seam, 1 between first and second, ..."""
    h, w = shape
    labels = np.zeros((h, w), np.int32)
    rows = np.arange(h).reshape(-1, 1)
    for path, _ in seams:
        labels += (rows > path.reshape(1, -1)).astype(np.int32)
    return labels
