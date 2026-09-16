# MoRD / DoLR Land Record Digitization & Validation (PS 26018)

Aligned with **Ministry of Rural Development (MoRD) / Department of Land Resources (DoLR)** Problem Statement **26018**: *Intelligent Land Record Digitization and Validation System* (Smart India Hackathon).

---

## 1. Executive Summary & Problem Resolution

### The Fundamental Problem
Standard OCR engines and page-wide text line cutters slice horizontally across the full page width. When applied to multi-column tabular land records (such as **Madhya Pradesh Khasra Panchsala** or **Goa Form I & XIV Mutation Registers**), this results in **catastrophic column welding**:
- Co-owner names get horizontally welded with mutation numbers (`"Maria Alina Filomena Afonso Rodrigues alias 45173"`).
- Plot areas get merged with soil classifications.
- Structured tabular data is destroyed, rendering automated validation impossible.

### The Solution: Two-Tier Structural Extraction
1. **Tier 1 (2D Table & Cell Grid Isolation):** Directional morphological kernels detect horizontal and vertical printed rules to isolate discrete table ROIs, filter outer page frames, and extract 2D coordinate-bounded cell boxes `[x, y, w, h]`.
2. **Tier 2 (Cell-by-Cell Dual-OCR):** Each individual cell is cropped with white padding and scanned independently via thread-safe Dual-OCR (PaddleOCR + TrOCR) or localized Devanagari models.
3. **DoLR Schema Compilation:** Cell grids are clustered into row/column matrices, column headers are identified via domain keyword scoring, and mapped into the canonical **`DoLR-DILRMP-v2.0`** revenue schema.
4. **Automated Business Rules Engine:** Mathematical invariants and integrity checks run automatically on the extracted data:
   - **Area Balance Invariant:** $\sum \text{Individual Plot Areas} == \text{Reported Total Area}$
   - **Ownership Share Invariant:** $\sum \text{Co-owner Shares} == 1.0\ (100\%)$
   - **Khasra / Survey Number Format & Duplicates:** Legal subdivision regex pattern checking (`128/2-A`, `104/1`) and duplicate detection.
   - **Calibrated Review Routing:** Automatically flags records requiring Human-In-The-Loop (HITL) audit.
5. **Mercury-2.5 LLM Reasoning Refinement:** Disambiguates legal abbreviations (*s/o, w/o, c/o, alias*), separates joint parentage, and standardizes transliterated revenue terms.

---

## 2. Canonical DoLR-DILRMP-v2.0 Schema

The engine compiles extracted records into the standardized DoLR JSON schema:

```json
{
  "schema_version": "DoLR-DILRMP-v2.0",
  "metadata": {
    "state": "Madhya Pradesh",
    "district": "Indore",
    "tehsil": "Sanwer",
    "village": "Chandravatiganj",
    "year": "2024-2025",
    "survey_no": "127",
    "sub_div": "1"
  },
  "plots": [
    {
      "khasra_no": "127",
      "area": "0.1000 हेक्टेयर",
      "area_numeric": 0.1,
      "land_classification": "कृषि",
      "crop": "खरीफ - सोयाबीन"
    }
  ],
  "owners": [
    {
      "name": "Maria Alina Filomena Afonso Rodrigues",
      "alias": "Alina Rodrigues",
      "parentage": "",
      "share": "1.0",
      "address": ""
    }
  ],
  "mutations": [
    {
      "mutation_no": "45173",
      "nature": "कृषि उपज का दृष्टिबंधक दर्ज",
      "date": "05/06"
    }
  ],
  "reported_total_area": 0.1,
  "validation": {
    "validation_passed": true,
    "total_rules_checked": 3,
    "rules_passed": 2,
    "rules_failed": 0,
    "rules_skipped": 1,
    "checks": [
      {
        "rule": "area_balance",
        "status": "passed",
        "computed_total": 0.1,
        "reported_total": 0.1,
        "difference": 0.0,
        "message": "Area balance verified: sum of plots (0.1) matches total (0.1)."
      },
      {
        "rule": "khasra_format",
        "status": "passed",
        "total_checked": 1,
        "invalid_format": [],
        "duplicates": [],
        "message": "All 1 Khasra/Survey numbers valid with no duplicates."
      },
      {
        "rule": "ownership_shares",
        "status": "skipped",
        "message": "No ownership shares specified to validate."
      }
    ],
    "review_required": false,
    "review_reasons": []
  }
}
```

---

## 3. CLI Usage

Run full segmentation, table isolation, cell OCR, schema compilation, and validation:

```bash
# Process MP Khasra Devanagari Record
./venv/bin/python segment.py "image.png" -o output/test_mp --ocr --lang hi --device cpu

# Process Goa Form I & XIV English Record
./venv/bin/python segment.py "image copy 2.png" -o output/test_goa --ocr --lang en --device cpu

# Run without table extraction (plain lines only)
./venv/bin/python segment.py "image.png" -o output/plain --ocr --no-tables
```

Generated outputs inside target directory:
- `land_record.json`: Standardized DoLR-DILRMP-v2.0 record with full validation audit.
- `tables.md`: 2D Markdown tables preserving exact row/column structures.
- `document.md`: Complete document text with tables and prose.
- `document.docx`: Word document output.
- `lines/`: Clean segmented line crops.

---

## 4. REST API Usage

Start the FastAPI service:
```bash
./venv/bin/uvicorn api:app --host 0.0.0.0 --port 8000
```

### Endpoints:
- `POST /segment`: Upload document image with parameters `extract_tables=true`, `ocr=true`, `ocr_lang=hi|en`, `llm_refine=true|false`.
- `GET /jobs/{job_id}/land_record.json`: Fetch verified DoLR revenue JSON.
- `GET /jobs/{job_id}/document.md`: Fetch generated Markdown with tables.
- `GET /jobs/{job_id}/document.docx`: Download Word document.

Example `curl` query:
```bash
curl -X POST "http://127.0.0.1:8000/segment" \
  -F "image=@image.png" \
  -F "ocr=true" \
  -F "ocr_lang=hi" \
  -F "extract_tables=true" \
  -F "llm_refine=false" | jq .land_record
```

---

## 5. Automated Verification Test Suite

All validation invariants, 2D grid cell clustering, schema compilation, and REST endpoints are verified via Python unit and integration tests:

```bash
./venv/bin/python -m unittest tests/test_land_records.py -v
```

Test coverage includes:
1. `test_area_balance_exact_match`
2. `test_area_balance_mismatch`
3. `test_area_balance_no_reported`
4. `test_ownership_shares_perfect_sum`
5. `test_ownership_shares_decimal_percentages`
6. `test_ownership_shares_mismatch`
7. `test_khasra_numbers_valid`
8. `test_khasra_numbers_duplicates`
9. `test_run_full_validation_workflow`
10. `test_detect_tables`
11. `test_extract_table_cells`
12. `test_cluster_cells_into_grid`
13. `test_build_structured_land_record`
14. `test_segment_with_tables_and_land_record_fetch`
