# BhoomiAI / linecut — Intelligent Land Record Digitization & Validation System

An enterprise-grade, AI-powered system for digitizing and validating historical Indian land records, cadastral survey registers, and legacy documents, aligned with **Ministry of Rural Development (MoRD) / Department of Land Resources (DoLR) Problem Statement 26018** (Smart India Hackathon).

---

## 🌟 Key Capabilities

1. **Two-Tier Document Segmentation:**
   - **Tier 1 (2D Table & Cell Grid Isolation):** Directional morphological kernels detect horizontal and vertical grid rules, eliminate page border frames, and isolate individual cell bounding boxes `[x, y, w, h]`. Eliminates catastrophic horizontal column welding across landowner names, mutation numbers, and plot areas.
   - **Tier 2 (Curved Baseline Linecut):** High-precision seam-carving and deskewing for non-tabular prose, marginal notes, and handwritten entries.

2. **Thread-Safe Dual-OCR Architecture:**
   - Parallel scan using **PaddleOCR** (printed text & Indic scripts: Hindi/Devanagari, English) and **TrOCR** (handwritten text).
   - Thread-safe synchronization locks prevent C++ runtime memory clashes.
   - 2D Markdown table generation preserving row/column alignment.

3. **Canonical DoLR-DILRMP-v2.0 Schema Mapping:**
   - Automatically maps extracted cells and header text into standardized revenue schema fields: `state`, `district`, `tehsil`, `village`, `year`, `khasra_no`, `khata_no`, `plot_area`, `ownership_share`, `crop`, `land_classification`, and `mutation_no`.

4. **Automated Mathematical & Business Rule Validation:**
   - **Area Balance Invariant:** $\sum \text{Plot Areas} == \text{Reported Total Area}$ (supporting hectares, ares, sq meters, bigha-biswa).
   - **Ownership Share Invariant:** $\sum \text{Co-owner Shares} == 1.0\ (100\%)$.
   - **Khasra / Survey Number Format & Duplicates:** Legal subdivision regex pattern checking (`128/2-A`, `104/1`) and duplicate detection.
   - **Human-In-The-Loop (HITL) Routing:** Calibrated confidence scoring automatically routes doubtful records to human audit.

5. **Mercury-2.5 LLM Reasoning Refinement:**
   - Inception Labs Mercury-2.5 model resolves ambiguous legal abbreviations (*s/o, w/o, c/o, alias*), separates joint parentage, and polishes messy OCR output.

---

## 🚀 Quick Start

### 1. Environment Setup
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. CLI Execution
```bash
# Process MP Khasra Devanagari Record (Hindi)
./venv/bin/python segment.py "image.png" -o output/mp_khasra --ocr --lang hi --device cpu

# Process Goa Form I & XIV Mutation Record (English)
./venv/bin/python segment.py "image copy 2.png" -o output/goa_record --ocr --lang en --device cpu

# Run without tables (prose line segmentation only)
./venv/bin/python segment.py "image.png" -o output/plain --ocr --no-tables
```

Outputs generated in target directory:
- `land_record.json`: Standardized DoLR-DILRMP-v2.0 JSON with validation audit report.
- `tables.md`: 2D Markdown tables.
- `document.md`: Unified Markdown document.
- `document.docx`: Word document export.
- `lines/`: Clean segmented line crops.

### 3. REST API Service
```bash
# Start FastAPI server
./venv/bin/uvicorn api:app --host 0.0.0.0 --port 8000
```

Interactive API documentation available at: `http://localhost:8000/docs`

#### Example `POST /segment` Request:
```bash
curl -X POST "http://127.0.0.1:8000/segment" \
  -F "image=@image.png" \
  -F "ocr=true" \
  -F "ocr_lang=hi" \
  -F "extract_tables=true" \
  -F "llm_refine=false"
```

#### Fetch Verified Land Record JSON:
```bash
curl -s "http://127.0.0.1:8000/jobs/{job_id}/land_record.json" | jq .
```

---

## 🧪 Automated Test Suite

Run the full automated test suite covering business rule validation, table cell grid isolation, DoLR schema compilation, and FastAPI endpoints:

```bash
./venv/bin/python -m unittest tests/test_land_records.py -v
```

---

## 📚 Documentation

- [01-architecture.md](docs/01-architecture.md): Six-stage linecut pipeline architecture.
- [02-findings.md](docs/02-findings.md): Empirical measurements and error analysis.
- [03-datasets.md](docs/03-datasets.md): Training datasets and Indic manuscripts.
- [04-enterprise-roadmap.md](docs/04-enterprise-roadmap.md): Master enterprise roadmap and model training.
- [05-land-records-and-validation.md](docs/05-land-records-and-validation.md): Deep dive into MoRD/DoLR Problem Statement 26018 implementation.
