"""Parallel Dual-OCR Engine and Document Reconstructor.

Scans segmented line crops concurrently using PaddleOCR and TrOCR,
reconciles discrepancies, applies context corrections, and exports
the reconstructed document into Markdown (.md), Word (.docx), and latent JSON.
"""
import concurrent.futures
import difflib
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

import threading

logger = logging.getLogger("linecut.dual_ocr")

# Lazy global model singletons
_PADDLE_MODELS: Dict[str, Any] = {}
_TROCR_MODEL = None
_TROCR_PROCESSOR = None
_TROCR_TOKENIZER = None
_MODEL_LOCK = threading.Lock()
_INFERENCE_LOCK = threading.Lock()


def get_paddle_ocr(lang: str = "en"):
    """Lazy-load and cache the PaddleOCR engine per language in a thread-safe manner."""
    global _PADDLE_MODELS
    norm_lang = lang.lower().strip()
    if norm_lang in ("hindi", "devanagari"):
        norm_lang = "hi"
    with _MODEL_LOCK:
        if norm_lang not in _PADDLE_MODELS:
            from paddleocr import PaddleOCR
            # Suppress orientation/unwarping in Paddle since LineCut already handles deskew & rectification
            _PADDLE_MODELS[norm_lang] = PaddleOCR(
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                lang=norm_lang,
            )
        return _PADDLE_MODELS[norm_lang]


def get_trocr(model_name: str = "microsoft/trocr-small-handwritten"):
    """Lazy-load and cache the TrOCR model, tokenizer, and processor."""
    global _TROCR_MODEL, _TROCR_PROCESSOR, _TROCR_TOKENIZER
    if _TROCR_MODEL is None:
        import torch
        from transformers import AutoImageProcessor, VisionEncoderDecoderModel, XLMRobertaTokenizer

        _TROCR_TOKENIZER = XLMRobertaTokenizer.from_pretrained(model_name)
        _TROCR_PROCESSOR = AutoImageProcessor.from_pretrained(model_name)
        model = VisionEncoderDecoderModel.from_pretrained(model_name)
        model.eval()
        _TROCR_MODEL = model
    return _TROCR_MODEL, _TROCR_PROCESSOR, _TROCR_TOKENIZER


def _scan_wide_paddle(paddle, crop_bgr: np.ndarray, max_chunk_w: int = 420, overlap: int = 60) -> Tuple[List[str], List[float]]:
    """Scan very wide crops by sliding across horizontal whitespace gaps to avoid CTC sequence truncation."""
    H, W = crop_bgr.shape[:2]
    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    ink_cols = (gray < 220).sum(axis=0)

    x = 0
    all_texts = []
    all_scores = []
    while x < W:
        x_end = min(W, x + max_chunk_w)
        if x_end < W:
            search_window = ink_cols[max(0, x_end - overlap) : x_end]
            if len(search_window) > 0:
                best_split = max(0, x_end - overlap) + int(np.argmin(search_window))
                if best_split > x + 100:
                    x_end = best_split
        chunk = crop_bgr[:, x:x_end]
        padded = cv2.copyMakeBorder(chunk, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        with _INFERENCE_LOCK:
            res = paddle.predict(padded)
        if res and hasattr(res[0], "get"):
            c_texts = res[0].get("rec_texts", [])
            c_scores = res[0].get("rec_scores", [])
            all_texts.extend(c_texts)
            all_scores.extend(c_scores)
        if x_end >= W:
            break
        x = x_end
    return all_texts, all_scores


def run_paddle_on_crop(crop_bgr: np.ndarray, lang: str = "en") -> Dict[str, Any]:
    """Run PaddleOCR on a single line crop."""
    try:
        paddle = get_paddle_ocr(lang=lang)
        with _INFERENCE_LOCK:
            res = paddle.predict(crop_bgr)
        if not res or not hasattr(res[0], "get"):
            return {"text": "", "confidence": 0.0, "words": []}

        texts = res[0].get("rec_texts", [])
        scores = res[0].get("rec_scores", [])
        combined_text = " ".join(t.strip() for t in texts if t.strip())

        # If crop is very wide and returned text is short (indicating CTC sequence truncation), scan in chunks
        if crop_bgr.shape[1] > 450 and len(combined_text) < 45:
            wide_texts, wide_scores = _scan_wide_paddle(paddle, crop_bgr)
            if len(" ".join(wide_texts)) > len(combined_text):
                texts = wide_texts
                scores = wide_scores
                combined_text = " ".join(t.strip() for t in texts if t.strip())

        # Filter out edge-noise fragments (e.g. ascender/descender bleed from adjacent lines)
        if len(texts) > 1 and any(s >= 0.90 for s in scores):
            cleaned_texts = []
            cleaned_scores = []
            for t, s in zip(texts, scores):
                if s < 0.65 and (len(t.strip()) < 12 or not any(c.isalnum() for c in t)):
                    continue
                cleaned_texts.append(t)
                cleaned_scores.append(s)
            if cleaned_texts:
                texts = cleaned_texts
                scores = cleaned_scores
                combined_text = " ".join(t.strip() for t in texts if t.strip())

        mean_score = float(sum(scores) / max(len(scores), 1)) if scores else 0.0
        return {
            "text": combined_text,
            "confidence": round(mean_score, 4),
            "words": texts,
            "scores": [round(float(s), 4) for s in scores],
        }
    except Exception as exc:
        logger.warning(f"PaddleOCR scan error: {exc}")
        return {"text": "", "confidence": 0.0, "error": str(exc)}


def run_trocr_on_crop(crop_bgr: np.ndarray, model_name: str = "microsoft/trocr-small-handwritten") -> Dict[str, Any]:
    """Run TrOCR on a single line crop."""
    try:
        import torch
        model, processor, tokenizer = get_trocr(model_name=model_name)
        rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)

        pixel_values = processor(pil_img, return_tensors="pt").pixel_values
        with torch.no_grad():
            outputs = model.generate(
                pixel_values,
                max_new_tokens=48,
                return_dict_in_generate=True,
                output_scores=True,
            )

        gen_ids = outputs.sequences
        text = tokenizer.batch_decode(gen_ids, skip_special_tokens=True)[0].strip()

        # Estimate confidence from token generation logits
        if hasattr(outputs, "scores") and outputs.scores:
            probs = [torch.softmax(s, dim=-1).max().item() for s in outputs.scores]
            conf = float(sum(probs) / max(len(probs), 1))
        else:
            conf = 0.85 if text else 0.0

        return {"text": text, "confidence": round(conf, 4)}
    except Exception as exc:
        logger.warning(f"TrOCR scan error: {exc}")
        return {"text": "", "confidence": 0.0, "error": str(exc)}


def scan_single_crop_parallel(crop_bgr: np.ndarray, lang: str = "en") -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Scan a single crop concurrently through PaddleOCR and TrOCR."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f_paddle = executor.submit(run_paddle_on_crop, crop_bgr, lang=lang)
        f_trocr = executor.submit(run_trocr_on_crop, crop_bgr)
        paddle_res = f_paddle.result()
        trocr_res = f_trocr.result()
    return paddle_res, trocr_res


# Common OCR typo corrections for standard document/form tokens
FORM_CORRECTIONS = {
    r"\bFQRM\b": "FORM",
    r"\bFQRM\s*1997\b": "FORM 1997",
    r"\bMUTHER'?S\b": "MOTHER'S",
    r"\bFATHER'?S\s*F\.?\s*NAME\b": "FATHER'S F.NAME",
    r"\bD\.?O\.?B\.?\s*:\s*": "D.O.B.: ",
    r"\bCERTIFCATE\b": "CERTIFICATE",
    r"\bRES\s*:\s*": "RES: ",
    r"\bPOSTAL\s+ADDRESS\s*:\s*": "POSTAL ADDRESS: ",
}


_TROCR_HALLUCINATION_PATTERNS = [
    "helplearn",
    "communityportal",
    "recentchanges",
    "uploadfile",
    "specialpages",
    "permanentlink",
    "pageinformation",
    "wikidataitem",
    "citethispage",
    "whatlinkshere",
    "relatedchanges",
    "displaystyle",
    "freeencyclopedia",
    "printableversion",
    "aboutwikipedia",
    "wikimedia",
    "wikipedia",
]


def is_trocr_hallucination(text: str) -> bool:
    """Detect common TrOCR pretraining hallucinations on blank or non-text visual noise."""
    if not text:
        return False
    lower = text.lower().replace(" ", "")
    if any(sig in lower for sig in _TROCR_HALLUCINATION_PATTERNS):
        return True

    # Check for alphabet sequence loops: e.g. "a b c d e f g h"
    if any(seq in lower for seq in ["abcdef", "bcdefg", "cdefgh"]):
        return True

    return False


def reconcile_line(paddle_res: Dict[str, Any], trocr_res: Dict[str, Any]) -> Dict[str, Any]:
    """Reconcile and arbitrate between PaddleOCR and TrOCR predictions.

    Uses confidence weighting, token similarity, and form-level corrections.
    Suppresses hallucinations on non-text or blank crops.
    """
    p_text = paddle_res.get("text", "").strip()
    p_conf = paddle_res.get("confidence", 0.0)
    t_text = trocr_res.get("text", "").strip()
    t_conf = trocr_res.get("confidence", 0.0)

    # Disqualify TrOCR if it generated a known pre-training hallucination
    if is_trocr_hallucination(t_text):
        t_text = ""
        t_conf = 0.0

    # If neither model has at least 50% confidence, treat as noise / non-text
    if max(p_conf, t_conf) < 0.50:
        return {"final_text": "", "confidence": 0.0, "status": "empty", "corrections_applied": [], "paddle": paddle_res, "trocr": trocr_res}

    # Also discard isolated single characters if confidence is under 0.70
    if p_text and len(p_text) == 1 and p_conf < 0.70 and t_conf < 0.70:
        p_text = ""
        p_conf = 0.0

    # Empty fallbacks
    if not p_text and not t_text:
        return {"final_text": "", "confidence": 0.0, "status": "empty", "corrections_applied": [], "paddle": paddle_res, "trocr": trocr_res}

    # Paddle saw NO text at all in the crop (DBNet detector returned empty)
    if not p_text:
        # If TrOCR confidence is low or text is very short/noisy, treat as empty blank paper
        if t_conf < 0.75 or len(t_text) < 3:
            return {"final_text": "", "confidence": 0.0, "status": "empty", "corrections_applied": [], "paddle": paddle_res, "trocr": trocr_res}
        return {"final_text": t_text, "confidence": t_conf, "status": "trocr_only", "corrections_applied": [], "paddle": paddle_res, "trocr": trocr_res}

    if not t_text:
        return {"final_text": p_text, "confidence": p_conf, "status": "paddle_only", "corrections_applied": [], "paddle": paddle_res, "trocr": trocr_res}

    # Similarity comparison
    similarity = difflib.SequenceMatcher(None, p_text.lower(), t_text.lower()).ratio()

    # If text is Indic/Devanagari (e.g. Hindi), prefer Paddle as TrOCR is Latin-only
    if any('\u0900' <= char <= '\u097F' for char in p_text):
        chosen = p_text
        conf = max(p_conf, 0.70)
        status = "paddle_indic"
    # If high consensus between both models
    elif similarity >= 0.85:
        chosen = p_text if len(p_text) >= len(t_text) else t_text
        conf = min(1.0, max(p_conf, t_conf) + 0.05)
        status = "consensus"
    # If Paddle is very confident (Paddle is especially accurate on printed labels & structure)
    elif p_conf >= 0.85 and p_conf >= t_conf:
        chosen = p_text
        conf = p_conf
        status = "paddle_preferred"
    # If TrOCR is substantially more confident (TrOCR excels on continuous handwriting)
    elif t_conf > p_conf + 0.20 and len(t_text) > 3:
        chosen = t_text
        conf = t_conf
        status = "trocr_preferred"
    else:
        # Default to Paddle for structured documents
        chosen = p_text if p_conf >= t_conf else t_text
        conf = max(p_conf, t_conf)
        status = "arbitrated"

    # Apply smart domain corrections
    corrections_applied = []
    final_text = chosen
    for pattern, replacement in FORM_CORRECTIONS.items():
        if re.search(pattern, final_text, re.IGNORECASE):
            final_text = re.sub(pattern, replacement, final_text, flags=re.IGNORECASE)
            corrections_applied.append(f"{pattern} -> {replacement}")

    # Clean double colons and spacing
    final_text = re.sub(r":\s*:", ":", final_text)
    final_text = re.sub(r"\s+", " ", final_text).strip()

    return {
        "final_text": final_text,
        "confidence": round(conf, 4),
        "similarity": round(similarity, 4),
        "status": status,
        "corrections_applied": corrections_applied,
        "paddle": paddle_res,
        "trocr": trocr_res,
    }



def scan_manifest_lines_parallel(
    manifest_lines: List[Dict[str, Any]],
    job_dir: Path,
    lang: str = "en",
    max_workers: int = 4,
) -> List[Dict[str, Any]]:
    """Scan all extracted line crops in parallel with Dual-OCR and reconciliation."""
    results = [None] * len(manifest_lines)

    def _process_one(idx: int, line_entry: Dict[str, Any]):
        crop_rel = line_entry.get("file")
        crop_path = job_dir / crop_rel
        if not crop_path.is_file():
            return idx, {
                "final_text": "",
                "confidence": 0.0,
                "status": "missing_crop",
                "paddle": {"text": "", "confidence": 0.0},
                "trocr": {"text": "", "confidence": 0.0},
            }
        crop_bgr = cv2.imread(str(crop_path))
        if crop_bgr is None:
            return idx, {
                "final_text": "",
                "confidence": 0.0,
                "status": "decode_fail",
                "paddle": {"text": "", "confidence": 0.0},
                "trocr": {"text": "", "confidence": 0.0},
            }

        paddle_res, trocr_res = scan_single_crop_parallel(crop_bgr, lang=lang)
        reconciled = reconcile_line(paddle_res, trocr_res)

        # Fallback to unmasked raw crop (lines_raw/) if seam-carving degraded the clean crop
        raw_rel = line_entry.get("file_raw")
        if raw_rel and reconciled.get("confidence", 0.0) < 0.96:
            raw_path = job_dir / raw_rel
            if raw_path.is_file():
                raw_bgr = cv2.imread(str(raw_path))
                if raw_bgr is not None:
                    pad_raw, trocr_raw = scan_single_crop_parallel(raw_bgr, lang=lang)
                    rec_raw = reconcile_line(pad_raw, trocr_raw)
                    if (rec_raw.get("confidence", 0.0) > reconciled.get("confidence", 0.0)) or (
                        len(rec_raw.get("final_text", "")) > len(reconciled.get("final_text", "")) + 5
                        and rec_raw.get("confidence", 0.0) >= 0.88
                    ):
                        reconciled = rec_raw

        return idx, reconciled

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_process_one, i, line) for i, line in enumerate(manifest_lines)]
        for f in concurrent.futures.as_completed(futures):
            idx, rec = f.result()
            results[idx] = rec

    return results


def scan_table_cells_parallel(
    tables: List[Dict[str, Any]],
    src_bgr: np.ndarray,
    lang: str = "en",
    max_workers: int = 4,
) -> List[Dict[str, Any]]:
    """Scan all extracted table cells concurrently using Dual-OCR.

    Populates each cell with 'text', 'confidence', and generates a clean
    Markdown table representation.
    """
    all_cells = []
    for t in tables:
        for c in t.get("cells", []):
            all_cells.append((t, c))

    if not all_cells:
        return tables

    H, W = src_bgr.shape[:2]

    def _process_cell(item):
        tbl, cell = item
        x, y, w, h = cell["abs_bbox"]

        # Clamp bounding box to source image dimensions
        x0 = max(0, min(W - 1, x))
        y0 = max(0, min(H - 1, y))
        x1 = max(x0 + 1, min(W, x0 + w))
        y1 = max(y0 + 1, min(H, y0 + h))

        crop = src_bgr[y0:y1, x0:x1]
        if crop.size == 0:
            cell["text"] = ""
            cell["confidence"] = 0.0
            return

        # Add generous padding for character recognition (tight cells like M, 1/2, 1/1 require 12px)
        pad_px = 12 if h < 35 else 6
        padded = cv2.copyMakeBorder(crop, pad_px, pad_px, pad_px, pad_px, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        ocr_res = run_paddle_on_crop(padded, lang=lang)
        text = ocr_res.get("text", "").strip()
        conf = ocr_res.get("confidence", 0.0)

        # Retry tight cells with 1.5x upscaling if empty
        if not text and h < 35 and w > 10:
            resized = cv2.resize(padded, (int(padded.shape[1] * 1.5), int(padded.shape[0] * 1.5)), interpolation=cv2.INTER_CUBIC)
            retry_res = run_paddle_on_crop(resized, lang=lang)
            if retry_res.get("text"):
                ocr_res = retry_res
                text = ocr_res.get("text", "").strip()
                conf = ocr_res.get("confidence", 0.0)

        cell["text"] = text
        cell["confidence"] = conf
        cell["words"] = ocr_res.get("words", [])

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        list(pool.map(_process_cell, all_cells))

    # Generate Markdown table representations
    for t in tables:
        cells = t.get("cells", [])
        if not cells:
            t["markdown"] = ""
            continue

        rows_dict: Dict[int, Dict[int, str]] = {}
        for c in cells:
            r = c.get("row_idx", 0)
            col = c.get("col_idx", 0)
            txt = c.get("text", "").replace("|", "/")
            if r not in rows_dict:
                rows_dict[r] = {}
            rows_dict[r][col] = txt

        # Determine maximum columns
        normal_row_lens = [len(cols) for cols in rows_dict.values() if len(cols) > 1]
        max_cols = max(normal_row_lens, default=t.get("cols_count", 1))
        max_cols = max(max_cols, max((max(cols.keys(), default=0) + 1 for cols in rows_dict.values()), default=1))

        md_lines = []
        for r in sorted(rows_dict.keys()):
            row_items = rows_dict[r]
            row_vals = [row_items.get(col, "") for col in range(max_cols)]
            md_lines.append("| " + " | ".join(row_vals) + " |")
            if r == 0:
                md_lines.append("| " + " | ".join(["---"] * max_cols) + " |")

        t["markdown"] = "\n".join(md_lines)

    return tables


def _get_line_y(entry: Dict[str, Any]) -> float:
    """Compute vertical mid-point coordinate for a line entry."""
    spine = entry.get("spine_on_source")
    if spine and len(spine) > 0:
        return float(np.mean([pt[1] for pt in spine]))
    return float(entry.get("row", 0) * 40.0)


def _is_line_inside_tables(entry: Dict[str, Any], tables: List[Dict[str, Any]]) -> bool:
    """Check whether a line crop falls entirely inside any detected table boundary."""
    spine = entry.get("spine_on_source")
    if not spine:
        return False
    xs = [pt[0] for pt in spine]
    ys = [pt[1] for pt in spine]
    x_mid = float(np.mean(xs))
    y_mid = float(np.mean(ys))
    for t in tables:
        bx, by, bw, bh = t.get("bbox", [0, 0, 0, 0])
        if (by - 6) <= y_mid <= (by + bh + 6) and (bx - 12) <= x_mid <= (bx + bw + 12):
            return True
    return False


def build_unified_document_blocks(
    scanned_lines: List[Dict[str, Any]],
    tables: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Organize prose lines and 2D tables into a single top-to-bottom reading-order list of blocks."""
    blocks = []
    active_tables = tables or []

    # 1. Add non-table lines (prose, headers, footers)
    for line in scanned_lines:
        text = (line.get("text") or line.get("final_text") or "").strip()
        if not text:
            continue
        if active_tables and _is_line_inside_tables(line, active_tables):
            continue
        blocks.append({
            "type": "line",
            "y": _get_line_y(line),
            "entry": line,
            "text": text,
        })

    # 2. Add tables at their vertical bounding-box top position
    for t in active_tables:
        bbox = t.get("bbox", [0, 0, 0, 0])
        blocks.append({
            "type": "table",
            "y": float(bbox[1]),
            "table": t,
        })

    # 3. Sort all blocks top-to-bottom by vertical coordinate
    blocks.sort(key=lambda b: b["y"])
    return blocks


def export_markdown(
    scanned_lines: List[Dict[str, Any]],
    tables: Optional[List[Dict[str, Any]]] = None,
    title: Optional[str] = None,
) -> str:
    """Reconstruct scanned lines and 2D tables into a unified, publication-grade Markdown document."""
    lines_md = []
    if title:
        lines_md.append(f"# {title}\n")

    blocks = build_unified_document_blocks(scanned_lines, tables)

    for b in blocks:
        if b["type"] == "table":
            t = b["table"]
            tbl_md = t.get("markdown", "").strip()
            if tbl_md:
                lines_md.append(f"\n### Table {t.get('table_id', '')}\n\n{tbl_md}\n")
            continue

        text = b["text"]

        # Detect Header / Title line (all caps and short)
        if text.isupper() and len(text) < 45 and not any(c in text for c in [":", "-", "/"]):
            lines_md.append(f"\n## {text}\n")
        # Detect Major Section Header (ends with colon and uppercase)
        elif text.endswith(":") and text.isupper():
            lines_md.append(f"\n### {text}\n")
        # Detect Key-Value fields (e.g. "DISTRICT: SOLAN", "TEHSIL: KANDAGHAT")
        elif ":" in text:
            formatted = re.sub(r"([A-Za-z0-9\s/.'\-]+):", r"- **\1:**", text)
            lines_md.append(formatted)
        # Checkboxes / bullet forms
        elif any(sym in text for sym in ["CERTIFICATE", "DIPLOMA", "DEGREE"]):
            lines_md.append(f"- [x] {text}")
        else:
            lines_md.append(text)

    return "\n".join(lines_md)


def export_text(
    scanned_lines: List[Dict[str, Any]],
    tables: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Reconstruct scanned lines and tables into a plain text document."""
    blocks = build_unified_document_blocks(scanned_lines, tables)
    text_pieces = []

    for b in blocks:
        if b["type"] == "table":
            t = b["table"]
            cells = t.get("cells", [])
            if not cells:
                continue
            rows_dict: Dict[int, Dict[int, str]] = {}
            for c in cells:
                r = c.get("row_idx", 0)
                col = c.get("col_idx", 0)
                rows_dict.setdefault(r, {})[col] = c.get("text", "").strip()
            max_cols = t.get("cols_count", max((max(cols.keys(), default=0) + 1 for cols in rows_dict.values()), default=1))
            table_lines = [f"\n--- [Table {t.get('table_id', '')}] ---"]
            for r in sorted(rows_dict.keys()):
                table_lines.append("\t".join(rows_dict[r].get(col, "") for col in range(max_cols)))
            text_pieces.append("\n".join(table_lines) + "\n")
        else:
            text_pieces.append(b["text"])

    return "\n".join(text_pieces)


def export_docx(
    scanned_lines: List[Dict[str, Any]],
    output_file: Path,
    tables: Optional[List[Dict[str, Any]]] = None,
    title: Optional[str] = None,
) -> Path:
    """Reconstruct scanned lines and 2D tables into a formatted Word (.docx) document."""
    import docx
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = docx.Document()
    if title:
        h = doc.add_heading(title, level=0)
        h.alignment = WD_ALIGN_PARAGRAPH.CENTER

    blocks = build_unified_document_blocks(scanned_lines, tables)

    for b in blocks:
        if b["type"] == "table":
            t = b["table"]
            cells = t.get("cells", [])
            if not cells:
                continue

            rows_dict: Dict[int, Dict[int, str]] = {}
            for c in cells:
                r = c.get("row_idx", 0)
                col = c.get("col_idx", 0)
                rows_dict.setdefault(r, {})[col] = c.get("text", "").strip()

            num_rows = max(rows_dict.keys(), default=-1) + 1
            num_cols = max((max(cols.keys(), default=-1) + 1 for cols in rows_dict.values()), default=1)
            num_cols = max(num_cols, t.get("cols_count", 1))

            doc.add_heading(f"Table {t.get('table_id', '')}", level=2)
            word_table = doc.add_table(rows=num_rows, cols=num_cols)
            word_table.style = "Table Grid"

            for r in sorted(rows_dict.keys()):
                for col in range(num_cols):
                    cell_text = rows_dict[r].get(col, "")
                    cell_obj = word_table.cell(r, col)
                    cell_obj.text = cell_text
                    if r == 0:
                        for p in cell_obj.paragraphs:
                            for run in p.runs:
                                run.bold = True
            doc.add_paragraph()  # spacing
            continue

        text = b["text"]

        # Major Title
        if text.isupper() and len(text) < 45 and not any(c in text for c in [":", "-", "/"]):
            doc.add_heading(text, level=1)
        # Section Heading
        elif text.endswith(":") and text.isupper():
            doc.add_heading(text, level=2)
        # Key-Value pairs
        elif ":" in text:
            p = doc.add_paragraph(style="List Bullet")
            parts = re.split(r"([A-Za-z0-9\s/.'\-]+:)", text)
            for part in parts:
                if part.endswith(":"):
                    run = p.add_run(part + " ")
                    run.bold = True
                else:
                    p.add_run(part)
        else:
            doc.add_paragraph(text)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_file))
    return output_file


def reassemble_page_with_tables(
    lines: List[Dict[str, Any]],
    tables: List[Dict[str, Any]],
    src_bgr: np.ndarray,
    out_path: Path,
    job_dir: Optional[Path] = None,
    pitch: float = 35.0,
):
    """Reassemble a complete page image interleaving deskewed prose lines and clean 2D table crops."""
    elements = []
    base_dir = job_dir or out_path.parent
    for l in lines:
        f_rel = l.get("file")
        if not f_rel:
            continue
        f_path = base_dir / f_rel
        if f_path.is_file():
            crop = cv2.imread(str(f_path))
            if crop is not None:
                spine = l.get("spine_on_source", [])
                y = float(np.mean([pt[1] for pt in spine])) if spine else float(l.get("row", 0) * pitch)
                elements.append({"type": "line", "y": y, "img": crop})

    for t in tables:
        tx, ty, tw, th = t.get("bbox", [0, 0, 0, 0])
        if tw > 0 and th > 0:
            H, W = src_bgr.shape[:2]
            y0, y1 = max(0, ty), min(H, ty + th)
            x0, x1 = max(0, tx), min(W, tx + tw)
            t_crop = src_bgr[y0:y1, x0:x1]
            if t_crop.size > 0:
                elements.append({"type": "table", "y": float(ty), "img": t_crop})

    if not elements:
        return

    elements.sort(key=lambda e: e["y"])
    max_w = max(e["img"].shape[1] for e in elements)
    gap = max(6, int(pitch * 0.2))
    tiles = []
    for e in elements:
        c = e["img"]
        c_pad = cv2.copyMakeBorder(c, 0, gap, 0, max_w - c.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255))
        tiles.append(c_pad)

    full_page = np.vstack(tiles)
    cv2.imwrite(str(out_path), full_page)

