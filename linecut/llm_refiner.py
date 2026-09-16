"""LLM Intelligence Correction and Document Refiner using Inception Labs Mercury-2.5.

Takes machine-extracted Dual-OCR lines (PaddleOCR + TrOCR) with layout context,
sends them to Mercury-2.5 reasoning LLM, fixes semantic and optical OCR misreads,
and outputs a polished, 100% accurate digital document.
"""
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("linecut.llm_refiner")

INCEPTION_API_URL = "https://api.inceptionlabs.ai/v1/chat/completions"
DEFAULT_MODEL = "mercury-2.5"


def get_api_key() -> Optional[str]:
    """Retrieve the Inception Labs API key from environment or .env."""
    return (
        os.environ.get("INCEPTION_LABS_MERCURY_2.5")
        or os.environ.get("INCEPTION_API_KEY")
        or os.environ.get("MERCURY_API_KEY")
    )


def refine_lines_with_llm(
    lines: List[Dict[str, Any]],
    doc_title: str = "Document",
    layout: str = "plain",
    lang: str = "en",
    timeout: int = 45,
) -> Tuple[List[Dict[str, Any]], str, Optional[str]]:
    """Send Dual-OCR recognized lines to Mercury-2.5 for intelligence correction.

    Returns:
        (updated_lines, refined_markdown, error_or_none)
    """
    api_key = get_api_key()
    if not api_key:
        return lines, "", "no_api_key"

    # Prepare compact structured lines payload for LLM reasoning
    ocr_payload = []
    for l in lines:
        ocr_payload.append({
            "line": l.get("index"),
            "row": l.get("row", 0),
            "text": l.get("text", "").strip(),
            "conf": l.get("confidence_ocr", 0.0),
        })

    prompt = f"""You are an expert Document Intelligence and OCR Error Correction Engine.
Below is the sequential, reading-order text extracted by an OCR system from a scanned document titled '{doc_title}' (language: {lang}, layout: {layout}).
The document may be in English, Hindi (Devanagari script), or bilingual.
Because of handwriting artifacts, bleed-through, and optical distortions, some lines have common OCR confusions.

Here are the extracted lines:
{json.dumps(ocr_payload, indent=2, ensure_ascii=False)}

Task:
1. Fix all optical and handwriting OCR misreads line by line using semantic, grammatical, and domain reasoning.
2. Preserve the script and language of the original text (e.g., if Hindi, output natural, grammatically correct Devanagari Hindi).
3. If a line is an obvious heading or section title, format it properly in the markdown.
4. If lines represent a table, key-value form fields, or diagram labels, format them cleanly in the markdown.
4. Output a STRICT JSON response with this exact structure:
{{
  "corrected_lines": [
    {{"line": 1, "corrected": "clean text here", "change_summary": "what was fixed"}}
  ],
  "markdown": "Full polished markdown document"
}}
Output ONLY valid JSON."""

    try:
        response = requests.post(
            INCEPTION_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": DEFAULT_MODEL,
                "reasoning_effort": "high",
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=timeout,
        )

        if response.status_code != 200:
            logger.warning(f"Inception Labs API returned status {response.status_code}: {response.text}")
            return lines, "", f"api_error_{response.status_code}"

        resp_json = response.json()
        raw_content = resp_json["choices"][0]["message"]["content"].strip()

        # Parse JSON from content (stripping markdown code blocks if wrapped)
        clean_json_str = raw_content
        if "```json" in clean_json_str:
            clean_json_str = clean_json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_json_str:
            clean_json_str = clean_json_str.split("```")[1].split("```")[0].strip()

        data = json.loads(clean_json_str)
        corrections_map = {
            item["line"]: (item.get("corrected", "").strip(), item.get("change_summary", "corrected"))
            for item in data.get("corrected_lines", [])
        }

        # Apply corrections to the lines list
        for l in lines:
            line_idx = l.get("index")
            if line_idx in corrections_map:
                corrected_text, change_summary = corrections_map[line_idx]
                l["text_raw_ocr"] = l.get("text", "")
                l["text"] = corrected_text
                l["final_text"] = corrected_text
                l["llm_correction"] = {
                    "original": l["text_raw_ocr"],
                    "corrected": corrected_text,
                    "summary": change_summary,
                }

        refined_md = data.get("markdown", "")
        return lines, refined_md, None

    except Exception as exc:
        logger.warning(f"LLM refinement exception: {exc}")
        return lines, "", str(exc)


DEFAULT_CLASSIFICATION = {"is_land_record": None, "confidence": 0.0, "reasoning": ""}


def refine_land_record_with_llm(
    land_record: Dict[str, Any],
    tables_markdown: str,
    doc_title: str = "Land Record",
    timeout: int = 45,
) -> Tuple[Dict[str, Any], str, Dict[str, Any], Optional[str]]:
    """Send structured land record data and table markdown to Mercury-2.5 for legal/domain
    refinement, and — in the same call — a hard yes/no classification of whether the source
    document is actually a land record at all.

    Returns:
        (refined_record, markdown_table, classification, error_or_none)
        classification = {"is_land_record": bool, "confidence": 0-1, "reasoning": str}
    """
    api_key = get_api_key()
    if not api_key:
        return land_record, tables_markdown, dict(DEFAULT_CLASSIFICATION), "no_api_key"

    prompt = f"""You are an expert Indian Land Records & Revenue Administration Intelligence Engine (DoLR / DILRMP).
Below is extracted data and table markdown from a scanned document titled '{doc_title}', uploaded to a
land-record digitization system. It is expected to be a Revenue Department record (Khatauni / Jamabandi /
Khasra / Form I & XIV / mutation / sale deed) in English and/or an Indian regional script, but it may not be —
users sometimes upload the wrong file. Judge this independently of OCR quality: a badly-scanned land record
is still a land record; a perfectly-clean invoice or ID card is not.

TABLE MARKDOWN:
{tables_markdown}

CURRENT EXTRACTED RECORD:
{json.dumps(land_record, indent=2, ensure_ascii=False)}

Task:
1. First, classify: is the source document actually a land/revenue record (jamabandi, khatauni, khasra,
   mutation register, sale/gift deed, patta, or similar)? Give a confidence (0-1) and a one-sentence reason.
2. If it is a land record, fix any OCR misreads in village name, tehsil, district, landowner names,
   Khasra/survey numbers, or plot areas, and cleanly populate the structured JSON per the DILRMP schema.
   If it is NOT a land record, leave "refined_record" as the input record unchanged (do not invent fields).
3. If an owner's father/husband name is embedded (e.g. 'रामेश्वर पुत्र हरपाल'), separate it cleanly into
   'name' and 'father_or_husband_name'.
4. Ensure plot areas are accurate numeric floats in hectares.
5. Output a STRICT JSON object with this exact structure:
{{
  "classification": {{"is_land_record": true, "confidence": 0.0, "reasoning": "..."}},
  "refined_record": {{
    "schema_version": "DoLR-DILRMP-v2.0",
    "metadata": {{"state": "...", "district": "...", "tehsil": "...", "village": "...", "year": "...", "survey_no": "..."}},
    "plots": [{{"khasra_no": "...", "area": "...", "area_numeric": 0.0, "land_classification": "...", "crop": "..."}}],
    "owners": [{{"name": "...", "father_or_husband_name": "...", "share": "..."}}],
    "mutations": [{{"mutation_no": "...", "details": "..."}}]
  }},
  "markdown_table": "Polished markdown representation"
}}
Output ONLY valid JSON."""

    try:
        response = requests.post(
            INCEPTION_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": DEFAULT_MODEL,
                "reasoning_effort": "high",
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=timeout,
        )

        if response.status_code != 200:
            return land_record, tables_markdown, dict(DEFAULT_CLASSIFICATION), f"api_error_{response.status_code}"

        resp_json = response.json()
        raw_content = resp_json["choices"][0]["message"]["content"].strip()
        clean_json_str = raw_content
        if "```json" in clean_json_str:
            clean_json_str = clean_json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_json_str:
            clean_json_str = clean_json_str.split("```")[1].split("```")[0].strip()

        data = json.loads(clean_json_str)

        raw_classification = data.get("classification") or {}
        classification = {
            "is_land_record": raw_classification.get("is_land_record"),
            "confidence": float(raw_classification.get("confidence") or 0.0),
            "reasoning": str(raw_classification.get("reasoning") or ""),
        }

        refined_rec = data.get("refined_record", land_record)
        # Re-run validation on the refined record
        from . import validation
        refined_rec["validation"] = validation.run_full_validation(
            plots=refined_rec.get("plots", []),
            reported_total_area=refined_rec.get("reported_total_area"),
            owners=refined_rec.get("owners", []),
        )
        refined_rec["classification"] = classification
        return refined_rec, data.get("markdown_table", tables_markdown), classification, None
    except Exception as exc:
        logger.warning(f"Mercury land record refinement exception: {exc}")
        return land_record, tables_markdown, dict(DEFAULT_CLASSIFICATION), str(exc)
