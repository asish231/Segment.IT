"""Table and Cell Extraction Engine for Ruled & Semi-Ruled Land Records.

Extracts table boundaries, isolates individual cell coordinates (x, y, w, h),
clusters cells into row/column matrices, identifies header vs data rows,
and associates data cells with column labels to prevent horizontal text smearing.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("linecut.table_extractor")


def detect_tables(
    img_bgr: np.ndarray,
    scale: int = 25,
    min_w_frac: float = 0.30,
    min_h_frac: float = 0.04,
    max_w_frac: float = 0.98,
    max_h_frac: float = 0.95,
) -> Tuple[List[Dict[str, Any]], np.ndarray, np.ndarray, np.ndarray]:
    """Detect table boundary boxes within a document image.

    Filters out outer full-page borders while capturing distinct tabular regions.
    Returns:
        (tables, table_grid_mask, h_lines, v_lines)
    """
    H, W = img_bgr.shape[:2]
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY) if img_bgr.ndim == 3 else img_bgr

    # Adaptive thresholding to handle illumination gradients and faint ink
    bw = cv2.adaptiveThreshold(
        ~gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 15, -2
    )

    # Directional morphological kernels to isolate horizontal and vertical rules
    h_kernel_len = max(20, W // scale)
    v_kernel_len = max(20, H // scale)

    hk = cv2.getStructuringElement(cv2.MORPH_RECT, (h_kernel_len, 1))
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_kernel_len))

    h_lines = cv2.morphologyEx(bw, cv2.MORPH_OPEN, hk)
    v_lines = cv2.morphologyEx(bw, cv2.MORPH_OPEN, vk)

    # Combine horizontal and vertical line masks
    grid_raw = h_lines | v_lines
    # Close small gaps in printed/scanned grid lines
    close_k = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    table_grid = cv2.morphologyEx(grid_raw, cv2.MORPH_CLOSE, close_k)

    # Find candidate table contours using contour tree hierarchy
    contours, hierarchy = cv2.findContours(
        table_grid, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
    )

    candidates = []
    for i, c in enumerate(contours):
        x, y, w, h = cv2.boundingRect(c)

        # Exclude outer full-page boundary boxes or vertical page-margin lines
        if (w >= int(W * max_w_frac) and h >= int(H * max_h_frac)) or h >= int(H * 0.85):
            continue

        # Minimum dimensions to qualify as a candidate table block
        if w >= int(W * min_w_frac) and h >= int(H * min_h_frac):
            sub_h = h_lines[y : y + h, x : x + w]
            sub_v = v_lines[y : y + h, x : x + w]
            h_density = (sub_h > 0).sum()
            v_density = (sub_v > 0).sum()

            # Must contain genuine horizontal and vertical rules
            if h_density >= w * 1.2 and v_density >= h * 0.8:
                candidates.append([x, y, w, h])

    # Filter out outer boxes that enclose inner tables
    # (e.g. A whole-page frame enclosing two distinct tables)
    valid_tables = []
    for box in candidates:
        bx, by, bw_box, bh_box = box
        # Check how many other candidates are enclosed by this box
        enclosed_count = sum(
            1 for ox, oy, ow, oh in candidates
            if ox > bx + 10 and oy > by + 10 and (ox + ow) < (bx + bw_box - 10) and (oy + oh) < (by + bh_box - 10)
        )
        if enclosed_count == 0:
            valid_tables.append(box)

    # De-duplicate near-identical overlapping boxes
    filtered = []
    for box in sorted(valid_tables, key=lambda b: b[2] * b[3]):
        bx, by, bw_box, bh_box = box
        is_dup = False
        for fx, fy, fw, fh in filtered:
            overlap_x0 = max(bx, fx)
            overlap_y0 = max(by, fy)
            overlap_x1 = min(bx + bw_box, fx + fw)
            overlap_y1 = min(by + bh_box, fy + fh)
            if overlap_x1 > overlap_x0 and overlap_y1 > overlap_y0:
                overlap_area = (overlap_x1 - overlap_x0) * (overlap_y1 - overlap_y0)
                box_area = bw_box * bh_box
                if overlap_area / max(box_area, 1) > 0.75:
                    is_dup = True
                    break
        if not is_dup:
            filtered.append(box)

    # Sort tables top-to-bottom
    filtered.sort(key=lambda b: b[1])

    tables = []
    for idx, (x, y, w, h) in enumerate(filtered, 1):
        tables.append({
            "table_id": idx,
            "bbox": [int(x), int(y), int(w), int(h)],
            "roi_x": int(x),
            "roi_y": int(y),
            "roi_w": int(w),
            "roi_h": int(h),
        })

    return tables, table_grid, h_lines, v_lines


def extract_table_cells(
    table_grid: np.ndarray,
    table_bbox: List[int],
    min_cell_w: int = 20,
    min_cell_h: int = 12,
    margin_trim: int = 2,
) -> List[Dict[str, Any]]:
    """Extract individual cell bounding boxes inside a table boundary.

    Uses morphological grid inversion to detect interior cell 'holes'.
    """
    tx, ty, tw, th = table_bbox
    grid_roi = table_grid[ty : ty + th, tx : tx + tw]

    # Invert grid: rule lines become 0, cell interiors become 255
    cells_mask = cv2.bitwise_not(grid_roi)

    # Connected components / contour analysis to find enclosed cell interiors
    contours, _ = cv2.findContours(
        cells_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
    )

    cells = []
    for c in contours:
        cx, cy, cw, ch = cv2.boundingRect(c)

        # Ignore tiny speckles or page-wide full table bounding contour
        if cw >= min_cell_w and ch >= min_cell_h:
            # Full table contour spans BOTH full width and full height
            if not (cw >= tw - 4 and ch >= th - 4):
                # For small/tight cells, use trim=1 to preserve character ascenders/descenders
                trim = 1 if (ch < 32 or cw < 32) else margin_trim
                adj_x = cx + trim
                adj_y = cy + trim
                adj_w = max(4, cw - 2 * trim)
                adj_h = max(4, ch - 2 * trim)

                is_merged = bool(cw > tw * 0.65)

                cells.append({
                    "rel_bbox": [int(adj_x), int(adj_y), int(adj_w), int(adj_h)],
                    "abs_bbox": [
                        int(tx + adj_x),
                        int(ty + adj_y),
                        int(adj_w),
                        int(adj_h),
                    ],
                    "center_x": float(tx + adj_x + adj_w / 2.0),
                    "center_y": float(ty + adj_y + adj_h / 2.0),
                    "is_merged": is_merged,
                })

    # Filter out any composite enclosing container cell that strictly envelops other cells
    non_container_cells = []
    for i, c1 in enumerate(cells):
        x1, y1, w1, h1 = c1["rel_bbox"]
        contains_other = False
        for j, c2 in enumerate(cells):
            if i == j:
                continue
            x2, y2, w2, h2 = c2["rel_bbox"]
            if x2 >= x1 - 2 and y2 >= y1 - 2 and (x2 + w2) <= (x1 + w1 + 2) and (y2 + h2) <= (y1 + h1 + 2):
                contains_other = True
                break
        if not contains_other:
            non_container_cells.append(c1)

    return non_container_cells


def cluster_cells_into_grid(
    cells: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Cluster raw cell boxes into a 2D matrix [row_idx, col_idx].

    Determines header row (Row 0) vs data rows, and binds data cells
    to their respective column headers.
    """
    if not cells:
        return []

    # Sort cells top-to-bottom primarily
    cells_sorted = sorted(cells, key=lambda c: c["rel_bbox"][1])

    # Dynamic row clustering: group cells that have overlapping vertical spans
    rows: List[List[Dict[str, Any]]] = []
    current_row: List[Dict[str, Any]] = []
    curr_y_min = -1
    curr_y_max = -1

    for c in cells_sorted:
        _, y, _, h = c["rel_bbox"]
        c_y_mid = y + h / 2.0

        if not current_row:
            current_row.append(c)
            curr_y_min = y
            curr_y_max = y + h
        else:
            overlap_h = min(curr_y_max, y + h) - max(curr_y_min, y)
            row_height = curr_y_max - curr_y_min
            if overlap_h > 0.35 * min(h, row_height) or abs(c_y_mid - (curr_y_min + curr_y_max) / 2.0) < 18:
                current_row.append(c)
                curr_y_min = min(curr_y_min, y)
                curr_y_max = max(curr_y_max, y + h)
            else:
                rows.append(current_row)
                current_row = [c]
                curr_y_min = y
                curr_y_max = y + h

    if current_row:
        rows.append(current_row)

    # Sort each row horizontally left-to-right
    structured_cells: List[Dict[str, Any]] = []
    for r_idx, row_cells in enumerate(rows):
        row_cells.sort(key=lambda c: c["rel_bbox"][0])
        for c_idx, cell in enumerate(row_cells):
            cell["row_idx"] = r_idx
            cell["col_idx"] = c_idx
            cell["is_header"] = (r_idx == 0)
            structured_cells.append(cell)

    return structured_cells


def extract_all_tables(img_bgr: np.ndarray) -> List[Dict[str, Any]]:
    """End-to-end table and cell extraction for a document image.

    Returns list of tables, each containing its matrix of structured cells.
    """
    tables_meta, table_grid, _, _ = detect_tables(img_bgr)
    results = []

    for t in tables_meta:
        raw_cells = extract_table_cells(table_grid, t["bbox"])
        grid_cells = cluster_cells_into_grid(raw_cells)

        # Only retain valid tables with 2 or more cells
        if len(grid_cells) < 2:
            continue

        max_row = max((c["row_idx"] for c in grid_cells), default=-1) + 1
        max_col = max((c["col_idx"] for c in grid_cells), default=-1) + 1

        results.append({
            "table_id": len(results) + 1,
            "bbox": t["bbox"],
            "rows_count": max_row,
            "cols_count": max_col,
            "cells_count": len(grid_cells),
            "cells": grid_cells,
        })

    return results
