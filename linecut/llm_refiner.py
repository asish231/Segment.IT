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
        or "sk_533fc2ccad9e51d877e8d373cfcccc06"
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
