# Enterprise Line Segmentation Roadmap & System Guardrails

This document specifies the technical architecture, safety guardrails, training procedures, and roadmap for the high-stakes Indic & Latin document line segmentation system built for enterprise contract delivery.

---

## 1. System Architecture: The Two-Tier Hybrid Design

Enterprise document processing must handle clean scans, phone photographs, degraded aged manuscripts, mixed-angle text, and complex tabular forms without human intervention.

```
                          Input Document
                                │
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │ TIER 1: Layout & Local Multi-Angle Detection               │
 │ (Instance Polygon Detection / DBNet++)                      │
 │                                                             │
 │ • Detects text blocks independently with per-block angles   │
 │ • Filters graphical furniture (boxes, rules, stamps)        │
 │ • Isolates multi-angle zones (e.g. 0° body + 90° margin)    │
 └──────────────────────────────┬──────────────────────────────┘
                                │
                  (Per-Zone Rotated Region Strips)
                                │
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │ TIER 2: Pixel-Level Seam Carving & Dewarping                │
 │ (Core `linecut` Engine)                                     │
 │                                                             │
 │ • Stage 0: Scale Normalisation (pen stroke width invariant) │
 │ • Stage 1: Continuous Angle Fine-Deskew (0.2° precision)    │
 │ • Stage 2: Learned Baseline Probability Map (CNN-BiLSTM)    │
 │ • Stage 3: Dynamic Programming Seam Carving (between lines) │
 │ • Stage 4: Pixel & Connected-Component Ownership            │
 │ • Stage 5: Non-Linear Line Dewarping (flattens wavy lines)  │
 └──────────────────────────────┬──────────────────────────────┘
                                │
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │ TIER 3: Upright Validation & Manifest Output                │
 │ (`orient_net` CNN + Reading-Order JSON)                     │
 │                                                             │
 │ • CNN checks glyph shapes to resolve 0° vs 180° inversion   │
 │ • If upside-down (>0.65 prob), auto-inverts page to upright │
 │ • Emits reading-order indexed crops + source polygon coords │
 │ • Calibrated confidence flags (seam_cost, height_ratio)     │
 └─────────────────────────────────────────────────────────────┘
```

---

## 2. Safety Guardrails & Calibrated Uncertainty

In a high-stakes deployment, claiming 100% accuracy without verification is fatal. Instead, enterprise systems implement **calibrated uncertainty**: the model self-evaluates every cut and flags uncertain outputs for human review.

| Guardrail Metric | Calculation | Threshold | Risk Prevented | Action when Triggered |
|---|---|---|---|---|
| `angle_margin` | $\frac{\text{Score}(\text{Winner})}{\text{Score}(\text{Rival} > 10^\circ)}$ | $< 1.50$ | Skew ambiguity; prevents cutting text diagonally | Marks `angle_uncertain: true` |
| `seam_cost` | Mean cut energy along the DP seam path | $> 0.24$ | Seam had to slice through ink (touching lines) | Marks line `review: true` |
| `height_ratio` | $\frac{\text{Line Bounding Height}}{\text{Estimated Line Pitch}}$ | $> 1.70$ or $< 0.45$ | Merged lines (double height) or stray fragments | Marks line `review: true` |
| `flip_probability` | Softmax probability from `orient_net` | $> 0.65$ | Document delivered upside-down to OCR | Automatically inverts page 180° |
| `rules_filtered` | Aspect ratio $> 10$, stroke span $> 40\%$ | Boolean match | Spurious table lines polluting text crops | Dropped from lines, recorded in manifest |

---

## 3. Training Procedures & Models

### Model 1: 180° Orientation Classifier (`orient_net`)
* **Objective**: Decides whether deskewed line crops are upright (0°) or upside-down (180°).
* **Architecture**: 4-block ConvNet + BatchNorm + AdaptiveAvgPool + FC Dropout (`linecut/orient_net.py`).
* **Training Data**: 
  - 129,674 native words from the Aksharantar corpus (`corpus/data/`) across 20 Indic languages + English dictionary words.
  - 50+ macOS system fonts covering Devanagari, Bengali, Gurmukhi, Gujarati, Tamil, Telugu, Kannada, etc.
  - Tofu (missing glyph) auto-detection prevents rendering corrupt characters.
  - Synthetic degradation: Gaussian blur, stroke dilation/erosion, perspective jitter, lighting gradients, and additive noise.
* **Command to Train**:
  ```bash
  source venv/bin/activate
  python train_orient.py --samples 6000 --epochs 14 --batch 128 --device mps
  ```
* **Expected Runtime**: **~3 to 5 minutes** on Apple Silicon M4 GPU (`mps`).
* **Expected Metrics**: Synthetic validation accuracy $> 94\%$; test accuracy on real held-out crops $> 85\%$.
* **Deliverable**: Generated weights file at `linecut/orient_net.pt` (automatically picked up by `pipeline.py`).

---

### Model 2: Core Segmentation Fine-Tuning (Kraken `blla`)
* **Objective**: Boost line-detection accuracy on degraded historical manuscripts with tight leading from 75% to >95%.
* **Architecture**: CNN feature extractor + 2D Bidirectional LSTMs along both axes (1.26M parameters).
* **Training Data Required**: 50–100 annotated document pages in standard **PAGE-XML** format.
* **Workflow via the Studio (`studio.py`)**:
  1. Launch Studio:
     ```bash
     source venv/bin/activate
     uvicorn studio:app --port 8100
     ```
  2. Open `http://localhost:8100` and load scans from `datasets/raw/` (unpacked from `PhDIndic_11.zip`).
  3. Click **Auto Prefill**: the current pipeline draws baseline proposals automatically.
  4. Manually correct errors (split merged lines, delete spurious marks). Takes ~30 seconds per page.
  5. Click **Export PAGE-XML**: saves ground-truth XML files to `datasets/pagexml/`.
* **Command to Fine-Tune**:
  ```bash
  ketos segtrain -d mps -m venv/lib/python3.12/site-packages/kraken/blla.mlmodel \
                 -o models/blla_indic.mlmodel datasets/pagexml/*.xml
  ```
* **Expected Runtime**: **~45 to 90 minutes** on Apple Silicon M4 GPU (`mps`).

---

## 4. Current Verification Benchmarks

Tested and verified against the four ground-truth benchmark pages:

| Test Page | File | Ground Truth | Detected Lines | Rules Filtered | Status |
|---|---|---|---|---|---|
| **A: Address Form** | `sample.png` | 8 lines | 8 lines | 1 border rule | **Line Count Matches, but Inverted** (180° flip open) |
| **B: Notes + Diagram** | `image.png` | ~22 lines | 23 lines | 0 | **Accurate Separation** |
| **C: Devanagari Letter** | `image copy.png` | ~24-25 lines (careful recount; an earlier ~28 estimate was wrong) | 25 lines (bands+recovery) | 0 | **Matches** - includes a 6-line right-hand address block |
| **D: Pre-Enrollment Form** | `image copy 2.png` | ~24 lines | 23 lines | 1 border rule | **23 of ~24 lines** (approximate match, borders dropped) |

---

## 5. Execution Roadmap

| Step | Milestone | Status | Details |
|---|---|---|---|
| **Step 1** | Rule Filter & Pipeline Hardening | **COMPLETED** | Rule detection active; spurious borders dropped on Page A and D. |
| **Step 2** | Model 1 Training (`orient_net.pt`) | **FAILED TRANSFER (55.3%)** | Trained on synthetic fonts (98.7% val), but failed sim-to-real transfer on handwriting (55.3%). `auto_flip` disabled by default. |
| **Step 3** | Benchmark Surya & Table Transformer | **NEXT** | Benchmark layout, lines, and tables on 4 test pages + 10 PhDIndic scans before writing any detector code. |
| **Step 4** | Studio Annotation & Model 2 Fine-Tuning | **PLANNED** | Annotate 50 Devanagari pages from `PhDIndic_11` using `studio.py` to fix tight leading under-segmentation. |
| **Step 5** | Perspective Correction & Region Pipeline | **PLANNED** | 4-point homography for 30° phone photos $\rightarrow$ layout regions $\rightarrow$ seam refiner inside regions. |
| **Step 6** | Audit Verification & Deliverable Sign-off | **PLANNED** | Automated benchmark report across 20+ held-out real client documents. |
