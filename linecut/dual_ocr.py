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

logger = logging.getLogger("linecut.dual_ocr")

# Lazy global model singletons
_PADDLE_MODEL = None
_TROCR_MODEL = None
_TROCR_PROCESSOR = None
_TROCR_TOKENIZER = None


def get_paddle_ocr(lang: str = "en"):
    """Lazy-load and cache the PaddleOCR engine."""
    global _PADDLE_MODEL
    if _PADDLE_MODEL is None:
        from paddleocr import PaddleOCR
        # Suppress orientation/unwarping in Paddle since LineCut already handles deskew & rectification
        _PADDLE_MODEL = PaddleOCR(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            lang=lang,
        )
    return _PADDLE_MODEL


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


def run_paddle_on_crop(crop_bgr: np.ndarray, lang: str = "en") -> Dict[str, Any]:
    """Run PaddleOCR on a single line crop."""
    try:
        paddle = get_paddle_ocr(lang=lang)
        res = paddle.predict(crop_bgr)
        if not res or not hasattr(res[0], "get"):
            return {"text": "", "confidence": 0.0, "words": []}

        texts = res[0].get("rec_texts", [])
        scores = res[0].get("rec_scores", [])
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


def reconcile_line(paddle_res: Dict[str, Any], trocr_res: Dict[str, Any]) -> Dict[str, Any]:
    """Reconcile and arbitrate between PaddleOCR and TrOCR predictions.

    Uses confidence weighting, token similarity, and form-level corrections.
    """
    p_text = paddle_res.get("text", "").strip()
    p_conf = paddle_res.get("confidence", 0.0)
    t_text = trocr_res.get("text", "").strip()
    t_conf = trocr_res.get("confidence", 0.0)

    # Empty fallbacks
    if not p_text and not t_text:
        return {"final_text": "", "confidence": 0.0, "status": "empty", "corrections_applied": [], "paddle": paddle_res, "trocr": trocr_res}
    if not p_text:
        return {"final_text": t_text, "confidence": t_conf, "status": "trocr_only", "corrections_applied": [], "paddle": paddle_res, "trocr": trocr_res}
    if not t_text:
        return {"final_text": p_text, "confidence": p_conf, "status": "paddle_only", "corrections_applied": [], "paddle": paddle_res, "trocr": trocr_res}

    # Similarity comparison
    similarity = difflib.SequenceMatcher(None, p_text.lower(), t_text.lower()).ratio()

    # If high consensus between both models
    if similarity >= 0.85:
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
        return idx, reconciled

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_process_one, i, line) for i, line in enumerate(manifest_lines)]
        for f in concurrent.futures.as_completed(futures):
            idx, rec = f.result()
            results[idx] = rec

    return results


def export_markdown(scanned_lines: List[Dict[str, Any]], title: Optional[str] = None) -> str:
    """Reconstruct scanned lines into a clean Markdown document."""
    lines_md = []
    if title:
        lines_md.append(f"# {title}\n")

    for entry in scanned_lines:
        text = entry.get("final_text", "").strip()
        if not text:
            continue

        # Detect Header / Title line (all caps and short)
        if text.isupper() and len(text) < 40 and not any(c in text for c in [":", "-", "/"]):
            lines_md.append(f"\n## {text}\n")
        # Detect Major Section Header (ends with colon and uppercase)
        elif text.endswith(":") and text.isupper():
            lines_md.append(f"\n### {text}\n")
        # Detect Key-Value fields (e.g. "FAMILY NAME: ROORDA")
        elif ":" in text:
            # Format keys in bold
            formatted = re.sub(r"([A-Z0-9\s/.'\-]+):", r"- **\1:**", text)
            lines_md.append(formatted)
        # Checkboxes (e.g. containing circles, ticks, or 'O')
        elif any(sym in text for sym in ["CERTIFICATE", "DIPLOMA", "DEGREE"]):
            lines_md.append(f"- [x] {text}")
        else:
            lines_md.append(text)

    return "\n".join(lines_md)


def export_text(scanned_lines: List[Dict[str, Any]]) -> str:
    """Reconstruct scanned lines into plain text document format."""
    return "\n".join(entry.get("final_text", "").strip() for entry in scanned_lines if entry.get("final_text"))


def export_docx(scanned_lines: List[Dict[str, Any]], output_file: Path, title: Optional[str] = None) -> Path:
    """Reconstruct scanned lines into a formatted Word (.docx) document."""
    import docx
    from docx.shared import Inches, Pt, RGBColor

    doc = docx.Document()
    if title:
        h = doc.add_heading(title, level=0)
        h.alignment = docx.enum.text.WD_ALIGN_PARAGRAPH.CENTER

    for entry in scanned_lines:
        text = entry.get("final_text", "").strip()
        if not text:
            continue

        # Major Title
        if text.isupper() and len(text) < 40 and not any(c in text for c in [":", "-", "/"]):
            doc.add_heading(text, level=1)
        # Section Heading
        elif text.endswith(":") and text.isupper():
            doc.add_heading(text, level=2)
        # Key-Value pairs
        elif ":" in text:
            p = doc.add_paragraph(style="List Bullet")
            parts = re.split(r"([A-Z0-9\s/.'\-]+:)", text)
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
