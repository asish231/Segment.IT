"""Document structure: rules, rows, and per-row fields.

Measured on a real enrollment form before being written: 9 horizontal rules, zero
vertical rules, zero page-wide column gutters, but clean per-row ink gaps. So the
structure that actually exists in this document class is "rows, each holding one or
more fields", not a row x column grid. Grid handling is here too, but only engages
when vertical rules are genuinely present.

Nothing here needs a model.
"""
import cv2
import numpy as np


def find_rules(binary, min_h_frac=0.25, min_v_frac=0.10):
    """Printed rules, by keeping only runs long enough to survive a directional opening.

    Returns (horizontal, vertical) as lists of (position, extent) in pixels.
    """
    h, w = binary.shape[:2]
    hk = cv2.getStructuringElement(cv2.MORPH_RECT, (max(20, w // 12), 1))
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(20, h // 12)))

    horiz = cv2.morphologyEx(binary, cv2.MORPH_OPEN, hk)
    vert = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vk)

    def collect(mask, axis_stat, extent_stat, min_extent):
        n, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        out = []
        for i in range(1, n):
            extent = stats[i, extent_stat]
            if extent >= min_extent:
                out.append((int(stats[i, axis_stat]), int(extent)))
        return sorted(out)

    h_rules = collect(horiz, cv2.CC_STAT_TOP, cv2.CC_STAT_WIDTH, w * min_h_frac)
    v_rules = collect(vert, cv2.CC_STAT_LEFT, cv2.CC_STAT_HEIGHT, h * min_v_frac)
    return h_rules, v_rules


def classify(h_rules, v_rules, interior_gutters):
    """Which of the three things people call a "table" is this page?"""
    if len(v_rules) >= 2 and len(h_rules) >= 2:
        return "grid"          # ruled table: intersect rules for cells
    if len(h_rules) >= 2:
        return "ruled_rows"    # form: rules give rows, gaps give fields
    if interior_gutters >= 1:
        return "columnar"      # borderless but aligned
    return "plain"             # ordinary running text


def page_gutters(binary, min_frac=0.03, rel=0.12):
    """Sustained vertical whitespace running the full page height.

    Present only when rows genuinely share column positions. On a form whose rows each
    place their fields differently, one row's ink fills another's gap and nothing
    survives here - which is the measured reason such pages are not columnar.
    """
    h, w = binary.shape[:2]
    col = (binary > 0).sum(axis=0).astype(np.float32)
    k = max(3, int(w * 0.01) | 1)
    sm = cv2.GaussianBlur(col.reshape(-1, 1), (1, k), 0).ravel()
    if sm.max() <= 0:
        return []
    cut = sm.max() * rel

    gutters, run = [], None
    for x, v in enumerate(sm):
        if v < cut:
            run = x if run is None else run
        else:
            if run is not None and x - run > w * min_frac:
                gutters.append((run, x))
            run = None
    if run is not None and w - run > w * min_frac:
        gutters.append((run, w))
    return [(a, b) for a, b in gutters if a > w * 0.08 and b < w * 0.92]


def split_fields(crop, min_gap_frac=0.05, margin_frac=0.05):
    """Split one line crop into fields at sustained internal whitespace.

    Crops arrive masked to a white background, so a field boundary is simply a run of
    columns with no ink. Returns [(x0, x1), ...] in crop coordinates.
    """
    if crop is None or crop.size == 0:
        return []
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    ink = (gray < 200).sum(axis=0)
    w = len(ink)
    if w < 10:
        return [(0, w)]

    min_gap = max(6, int(w * min_gap_frac))
    gaps, run = [], None
    for x, v in enumerate(ink):
        if v == 0:
            run = x if run is None else run
        else:
            if run is not None and x - run >= min_gap:
                gaps.append((run, x))
            run = None

    inner = [(a, b) for a, b in gaps if a > w * margin_frac and b < w * (1 - margin_frac)]
    if not inner:
        return [(0, w)]

    fields, cursor = [], 0
    for a, b in inner:
        if a > cursor:
            fields.append((cursor, a))
        cursor = b
    if cursor < w:
        fields.append((cursor, w))
    return [(a, b) for a, b in fields if b - a > w * 0.02]


def assign_rows(lines, h_rules, pitch):
    """Group detected lines into rows delimited by horizontal rules.

    Lines between the same pair of rules share a row index. With no rules, every line
    is its own row, which is the correct degenerate case for running text.
    """
    if not h_rules:
        return {i: i for i in range(len(lines))}
    edges = [y for y, _ in h_rules]
    assignment = {}
    for i, y_centre in enumerate(lines):
        row = sum(1 for e in edges if e < y_centre)
        assignment[i] = row
    return assignment
