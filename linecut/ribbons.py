"""Per-ribbon instance segmentation.

The baseline network paints a "highlighter" bar over every text line. This treats each
bar as an independent instance rather than collapsing the page to one global angle:
each ribbon carries its own orientation and its own curve, so mixed angles, curved
form-overflow lines and residual perspective all survive.

Rectification samples perpendicular to a ribbon's own centreline, which straightens
rotation and curvature in a single remap.
"""
import cv2
import numpy as np
from scipy import ndimage


def extract(prob, stroke=3.0, thresh=0.45, min_area=None, bridge_px=None):
    """Threshold the highlighter map into one labelled component per text line.

    The bridge kernel closes word-sized gaps along a line without joining neighbouring
    lines, so it is scaled by line pitch rather than stroke width.
    """
    mask = (prob > thresh).astype(np.uint8)
    bridge = int(max(5, bridge_px if bridge_px else stroke * 4)) | 1
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(cv2.MORPH_RECT, (bridge, 1)))
    if min_area is None:
        min_area = max(40, int(stroke * stroke * 12))

    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    keep = np.zeros(count, np.int32)
    next_id = 0
    for i in range(1, count):
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            next_id += 1
            keep[i] = next_id
    return keep[labels], next_id


def spine(mask_pts, stroke=3.0, smooth=True):
    """Ordered centreline through one ribbon, following its curve.

    Points are projected onto the ribbon's principal axis, binned along it, and the
    perpendicular mean of each bin gives a point on the spine.
    """
    if len(mask_pts) < 8:
        return None
    pts = mask_pts.astype(np.float32)
    centre = pts.mean(axis=0)
    centred = pts - centre
    _, _, vt = np.linalg.svd(centred, full_matrices=False)
    axis, perp = vt[0], vt[1]
    # Fix the traversal direction, otherwise half the spines run right-to-left and
    # their rectified crops come out mirrored.
    if axis[0] < 0 or (abs(axis[0]) < 1e-6 and axis[1] < 0):
        axis, perp = -axis, -perp

    along = centred @ axis
    across = centred @ perp
    span = float(along.max() - along.min())
    if span < stroke * 3:
        return None

    bins = int(np.clip(span / max(stroke * 3, 4), 3, 400))
    edges = np.linspace(along.min(), along.max(), bins + 1)
    slot = np.clip(np.digitize(along, edges) - 1, 0, bins - 1)

    spine_pts = []
    for b in range(bins):
        sel = slot == b
        if sel.sum() < 2:
            continue
        spine_pts.append(centre + axis * along[sel].mean() + perp * across[sel].mean())
    if len(spine_pts) < 2:
        return None

    out = np.array(spine_pts, np.float32)
    if smooth and len(out) >= 5:
        k = min(len(out) // 2 * 2 + 1, 9)
        out[:, 0] = cv2.GaussianBlur(out[:, 0].reshape(-1, 1), (1, k), 0).ravel()
        out[:, 1] = cv2.GaussianBlur(out[:, 1].reshape(-1, 1), (1, k), 0).ravel()
    return out


def assign(ink, ribbon_labels, max_distance):
    """Give every ink pixel the id of the ribbon whose core is nearest to it."""
    empty = ribbon_labels == 0
    dist, (iy, ix) = ndimage.distance_transform_edt(empty, return_indices=True)
    owner = ribbon_labels[iy, ix]
    owner[(ink == 0) | (dist > max_distance)] = 0
    return owner


def rectify(img, path, height, mask=None):
    """Unroll a line by sampling perpendicular to its spine.

    Straightens tilt and curvature together: the output row axis is the spine's normal,
    the output column axis is arc length along the spine.
    """
    steps = np.diff(path, axis=0)
    seg = np.hypot(steps[:, 0], steps[:, 1])
    arc = np.concatenate([[0.0], np.cumsum(seg)])
    total = float(arc[-1])
    if total < 4:
        return None, None

    n = max(8, int(round(total)))
    sample = np.linspace(0, total, n)
    px = np.interp(sample, arc, path[:, 0])
    py = np.interp(sample, arc, path[:, 1])

    tx, ty = np.gradient(px), np.gradient(py)
    norm = np.hypot(tx, ty)
    norm[norm == 0] = 1.0
    tx, ty = tx / norm, ty / norm
    nx, ny = -ty, tx  # unit normal

    h = int(max(6, height))
    offset = (np.arange(h) - (h - 1) / 2.0).astype(np.float32)
    map_x = (px[None, :] + nx[None, :] * offset[:, None]).astype(np.float32)
    map_y = (py[None, :] + ny[None, :] * offset[:, None]).astype(np.float32)

    strip = cv2.remap(img, map_x, map_y, cv2.INTER_CUBIC,
                      borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
    strip_mask = None
    if mask is not None:
        strip_mask = cv2.remap(mask.astype(np.uint8) * 255, map_x, map_y, cv2.INTER_NEAREST,
                               borderMode=cv2.BORDER_CONSTANT, borderValue=0) > 0
    return strip, strip_mask


def trim(strip, strip_mask, pad=3):
    """Crop a rectified strip to the rows and columns that actually carry owned ink."""
    if strip_mask is None or not strip_mask.any():
        return strip
    rows = np.where(strip_mask.any(axis=1))[0]
    cols = np.where(strip_mask.any(axis=0))[0]
    y0, y1 = max(int(rows[0]) - pad, 0), min(int(rows[-1]) + pad + 1, strip.shape[0])
    x0, x1 = max(int(cols[0]) - pad, 0), min(int(cols[-1]) + pad + 1, strip.shape[1])
    return strip[y0:y1, x0:x1]


def _tangent(path, at_end, window=4):
    """Local direction at one end of a spine."""
    k = min(window, len(path) - 1)
    return (path[-1] - path[-1 - k]) if at_end else (path[k] - path[0])


def ink_support(ink, p0, p1, half):
    """Fraction of the gap between two spine ends that still has ink under it.

    A highlighter stroke across folded paper stays one stroke; where the probability
    map breaks, the writing itself is still there. This measures that evidence.
    """
    span = float(np.hypot(*(p1 - p0)))
    steps = int(max(2, span))
    ts = np.linspace(0.0, 1.0, steps)
    pts = p0[None, :] * (1 - ts[:, None]) + p1[None, :] * ts[:, None]
    h, w = ink.shape[:2]
    hits = 0
    band = int(max(1, half))
    for x, y in pts:
        xi = int(round(x))
        if not (0 <= xi < w):
            continue
        y0, y1 = int(max(y - band, 0)), int(min(y + band + 1, h))
        if y1 > y0 and ink[y0:y1, xi].any():
            hits += 1
    return hits / steps


def _mean_slope(path):
    """Robust average slope over the whole fragment, not just its tip."""
    dx = float(path[-1, 0] - path[0, 0])
    if abs(dx) < 1e-6:
        return 0.0
    return float(path[-1, 1] - path[0, 1]) / dx


def merge_fragments(spines, ink, pitch, max_gap=3.0, max_offset=0.30,
                    max_angle=10.0, min_support=0.35):
    """Join spine fragments that continue the same stroke - never two different lines.

    Two gates, both required: (1) end-to-end continuation, where a later fragment picks
    up close to where an earlier one was heading, checked in both directions so a join
    can't be justified by one side's tangent alone; (2) short-stub absorption, where a
    small piece (a matra, a broken word) sits inside a much longer line's span - never
    two comparably-sized fragments, which is what joining two real lines looks like.
    """
    n = len(spines)
    if n < 2:
        return list(spines)

    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    def span(s):
        return float(s[-1, 0] - s[0, 0])

    order = sorted(range(n), key=lambda i: spines[i][0][0])
    for ii, i in enumerate(order):
        end_i = spines[i][-1]
        ti = _tangent(spines[i], True)
        if abs(ti[0]) < 1e-6:
            continue
        slope_i = ti[1] / ti[0]
        ang_i = np.degrees(np.arctan2(ti[1], ti[0]))

        best, best_gap = None, None
        for j in order[ii + 1:]:
            start_j = spines[j][0]
            dx = float(start_j[0] - end_i[0])
            if dx <= 0 or dx > pitch * max_gap:
                continue

            predicted_j = end_i[1] + slope_i * dx
            if abs(float(start_j[1]) - predicted_j) > pitch * max_offset:
                continue

            tj = _tangent(spines[j], False)
            if abs(tj[0]) < 1e-6:
                continue
            slope_j = tj[1] / tj[0]
            # symmetric check: extrapolating backward from j must land near i's end too,
            # so a join can't pass just because one side's tangent happened to point right
            predicted_i = float(start_j[1]) - slope_j * dx
            if abs(predicted_i - float(end_i[1])) > pitch * max_offset:
                continue

            ang_j = np.degrees(np.arctan2(tj[1], tj[0]))
            if abs(((ang_j - ang_i + 90) % 180) - 90) > max_angle:
                continue
            if ink_support(ink, end_i, start_j, pitch * 0.45) < min_support:
                continue
            if best_gap is None or dx < best_gap:
                best, best_gap = j, dx
        if best is not None:
            union(i, best)

    # Second pass: absorb a short stub into the line it overlaps - a matra or a broken
    # word fragment. Only ever the shorter into the longer, and only when short: two
    # comparably-sized fragments overlapping is two real lines close together, which
    # must not be merged even if their y-offset looks small on a tight-leading page.
    for i in range(n):
        for j in range(n):
            if i == j or find(i) == find(j):
                continue
            a, b = spines[i], spines[j]
            span_a, span_b = span(a), span(b)
            if span_a <= 0 or span_b <= 0:
                continue
            shorter_is_a = span_a <= span_b
            short, long_ = (a, b) if shorter_is_a else (b, a)
            span_short, span_long = (span_a, span_b) if shorter_is_a else (span_b, span_a)
            # a stub is meaningfully smaller than what it is joining, not a peer line
            if span_short > span_long * 0.55:
                continue

            lo = max(short[0][0], long_[0][0])
            hi = min(short[-1][0], long_[-1][0])
            if hi <= lo or (hi - lo) < span_short * 0.7:
                continue

            xs = np.linspace(lo, hi, 12)
            y_short = np.interp(xs, short[:, 0], short[:, 1])
            y_long = np.interp(xs, long_[:, 0], long_[:, 1])
            if float(np.abs(y_short - y_long).mean()) > pitch * 0.30:
                continue

            slope_short, slope_long = _mean_slope(short), _mean_slope(long_)
            ang_short = np.degrees(np.arctan(slope_short))
            ang_long = np.degrees(np.arctan(slope_long))
            if abs(ang_short - ang_long) > max_angle:
                continue

            union(i, j)

    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    merged = []
    for members in groups.values():
        members.sort(key=lambda i: spines[i][0][0])
        merged.append(np.vstack([spines[i] for i in members]).astype(np.float32))
    merged.sort(key=lambda s: s[:, 1].mean())
    return merged


def is_non_text_region(crop, mask=None, sat_thresh=140):
    """Rejects a flat, highly saturated region - a printed watermark, a colour stamp,
    a logo - which is not handwriting on paper.

    Manuscript paper and ink are desaturated; a printed colour mark is not. Measured on
    a real stock-photo watermark bar (saturation 220) versus real handwritten text rows
    (saturation ~60-65) on the same page - clean separation, not a guess.

    Checks only the owned-ink pixels: a masked crop pads the rest with white, which
    would otherwise dilute the mean toward zero and hide the very thing being checked.
    """
    if crop is None or crop.size == 0 or crop.ndim != 3:
        return False
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    if mask is not None and mask.any():
        sat = sat[mask]
    return bool(sat.mean() > sat_thresh)


def outline(path, height):
    """Closed polygon around a ribbon: spine offset by +/- half height along its normals."""
    steps = np.diff(path, axis=0)
    tx, ty = np.gradient(path[:, 0]), np.gradient(path[:, 1])
    norm = np.hypot(tx, ty)
    norm[norm == 0] = 1.0
    nx, ny = -ty / norm, tx / norm
    half = height / 2.0
    top = np.stack([path[:, 0] + nx * half, path[:, 1] + ny * half], axis=1)
    bot = np.stack([path[:, 0] - nx * half, path[:, 1] - ny * half], axis=1)
    return np.vstack([top, bot[::-1]])


def angle_of(path):
    """Ribbon orientation in degrees, normalised to (-90, 90]."""
    dx = float(path[-1, 0] - path[0, 0])
    dy = float(path[-1, 1] - path[0, 1])
    deg = float(np.degrees(np.arctan2(dy, dx)))
    while deg <= -90:
        deg += 180
    while deg > 90:
        deg -= 180
    return deg


def curvature_of(path):
    """Peak deviation from the straight chord, in pixels. Zero for a straight line."""
    if len(path) < 3:
        return 0.0
    a, b = path[0], path[-1]
    ab = b - a
    length = float(np.hypot(*ab))
    if length < 1e-6:
        return 0.0
    normal = np.array([-ab[1], ab[0]], np.float32) / length
    return float(np.abs((path - a) @ normal).max())
