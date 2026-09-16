# BhoomiAI / linecut — Master Interview Notes: Working + AI/ML Core (Fundamentals → Core → Why)

> **Target:** 25 LPA Product / Applied-AI interview. System: Intelligent Land Record Digitization & Validation (MoRD/DoLR PS 26018).
> **Scope of this file:** complete focus on **how it works + the AI/ML part**, from first-principles fundamentals to exact code, layer counts, thresholds, and *why each choice was made over alternatives*.
> **Codebase:** `api.py`, `segment.py`, `linecut/{core,energy,seams,lines,bands,ribbons,instances,pipeline,structure,table_extractor,stamp_extractor,dual_ocr,llm_refiner,validation,land_records,orient_net}.py`

---

## 0. The 30-second pitch (memorize)

> "Linecut digitizes degraded Indian land records — MP Khasra, Goa Form I & XIV — that normal OCR destroys by welding table columns together. It does Tier-0 table/stamp isolation with classical morphology, then per-line segmentation driven by Kraken's CNN+BiLSTM baseline map plus band-constrained spines, then parallel Dual-OCR (PaddleOCR for print/Indic + TrOCR for handwriting) with confidence arbitration, then Mercury-2.5 LLM cleanup, then mathematical validation — area sums, share sums, Khasra format — that routes doubtful records to humans. Every output carries calibrated confidence, not just text."

### 3-minute architecture (draw this on board)

```
SCAN/PHOTO
  │
  ▼
[TIER-0] Table-First Masking (classical CV) ── table_extractor + stamp_extractor
  │  masks tables/stamps white so line-cutter never slices them
  ▼
[STAGE 0] Scale normalise (core.py) ── stroke-width → resample to 3px
  ▼
[STAGE 1] Rough deskew (core.py) ── variance-profile search ±45°, 0.2° fine
  ▼
[STAGE 2] Energy map (energy.py) ── Kraken blla CNN+BiLSTM 0.8 + ink 0.2
  ▼
[STAGE 3a GLOBAL] DP seams (seams.py)  OR  [STAGE 3b INSTANCES] Bands (bands.py) ← DEFAULT
  │  global: one angle, horizontal seams   │  instances: per-line angle+curve spines
  ▼
[STAGE 4] Ownership (lines.py / bands.py) ── 80% component rule, else per-pixel
  ▼
[STAGE 5] Rectify/Dewarp/Crop (ribbons.py) ── perpendicular sampling, white masking
  ▼
[OCR] Dual-OCR parallel (dual_ocr.py) ── Paddle + TrOCR + reconcile + raw-fallback
  ▼
[CELLS] Table cells Dual-OCR + grid clustering → Markdown
  ▼
[REFINE] Mercury-2.5 LLM (llm_refiner.py) ── OCR fix + land-record fix
  ▼
[VALIDATE] Business rules (validation.py) + schema (land_records.py) → DoLR-DILRMP-v2.0 JSON
  ▼
Markdown / TXT / DOCX / land_record.json / page_reassembled.png + manifest.json (confidences)
```

Default production path is **`POST /segment` with `mode=instances`, `extract_tables=true`, `ocr=true`, `llm_refine=true`** → `segment_page_instances(method="bands")`.

---

## 1. Fundamentals: what problem are we actually solving?

### 1.1 Line segmentation ≠ OCR

* **Segmentation:** pixels → ordered line crops + positions. Question: *where is each line?*
* **Recognition (OCR):** crop → text. Question: *what does it say?*
* If segmentation welds two columns (`"Maria Afonso ... alias 45173"`), no OCR can unweld it. **Segmentation errors are irreversible downstream.** Hence Tier-0 exists.

### 1.2 Why Indic land records break naive segmenters

1. **Multi-column ruled tables:** a horizontal cut across full page width fuses `owner | area | mutation` into one string. This is *catastrophic column welding* (`docs/05-land-records-and-validation.md`).
2. **Tight leading + matras:** in Devanagari, vowel signs (matras) interpenetrate the gap between lines. There is **no ink-free row** — raw ink-density profile has no valley to cut through.
3. **Degradation:** stains, bleed-through, shadows, low-res phone photos (377×530), 90° rotation, wavy baselines, stamps/seals with 3–4× edge density of text.
4. **Mixed content:** print + handwriting + tables + emblems on one page.

### 1.3 Core insight (from `docs/02-findings.md`)

| Approach | Wins at | Blind to |
|---|---|---|
| Classical morphology/geometry | Global rotation, scale, rules, cheap & exact | What *is* text vs diagram/rule/stain |
| Learned baseline map (Kraken) | Text-ness: ignores rules, finds faint lines in stains | Assumes roughly upright text (collapses ~160× at 47°) |

**Composition order is the finding:** geometry first (deskew/normalise), then recognition (learned map), then pixel accounting (classical again). Neither alone covers test pages A–D; composed they do (8/8, 23/22, 21/28→25/25, 24/24).

---

## 2. End-to-end working (file-by-file, stage-by-stage)

### Stage 0 — Measure scale (`linecut/core.py:measure_scale`, `binarize`, `stroke_width`, `normalise`)

**Fundamental:** a pixel means different physical things at 377px vs 1700px wide. All later constants must be in *stroke widths*, not pixels.

1. `estimate_background()`: downscale by `radius//8`, median-blur (low-frequency illumination), upscale. Fast equivalent for illumination field.
2. `binarize()`: `ink = background − gray`, then Otsu threshold + 3×3 median. Two-pass: rough binary → measure `stroke_width` → re-binarize with `radius = sw*12`.
3. `stroke_width()`: distance-transform → ridge (dilate + local-max) → `2 × median(ridge)`. Modal pen width.
4. `normalise()`: `factor = clip(3.0/sw, 0.35, 4.0)`. Resample with `INTER_AREA` (down) / `INTER_CUBIC` (up). If `|factor−1|<0.05`, skip.

**Why chosen:** v1 hardcoded `51px blur, 20px min-area` discarded **582/678 components** on the smallest page before segmentation started. Scale normalisation is called "single most important stage for cross-document robustness" in `docs/01-architecture.md`.

**Interview line:** *"We never assume resolution; we measure the pen."*

### Stage 1 — Orientation (`linecut/core.py:find_orientation`)

**Fundamental:** projection profile. Rotate binary image, sum ink per row → 1-D profile. At true angle you get dense bands + empty gaps; elsewhere ink smears uniformly.

* Coarse sweep `-45°…+45°` step `1.0°`, fine `±2°` step `0.2°` on 0.4× downscaled image.
* **Score = variance of normalized profile**, NOT sum-of-squared-differences. Measured on 90°-rotated page A: SSD picked wrong angle (4.82e-04 vs 4.67e-04, 3% margin, confident-wrong); variance picked right by **2.5×** (1.05e-05 vs 4.21e-06).
* `margin = score(winner)/score(best rival >10° away)`. `margin<1.5` → `angle_uncertain=true`.
* Bounded to ±45° so vertical table rules don't cause 90° flips.

**Why not full 180° here:** a profile is identical upside-down. Axis ≠ direction. 180° needs glyph shape → learned classifier ( §4.2).

### Stage 2 — Energy / cut-cost map (`linecut/energy.py:build`, `baseline_map`, `ink_energy`)

**Fundamental:** we need a map where high = "inside a line, don't cut here".

```python
cost = 0.8 * dilated_baseline_prob + 0.2 * blurred_ink_density
```

* `baseline_map()`: Kraken `blla` heatmap channel `baselines/default`, resized to image. See §4.1 for network.
* Dilation vertically by `~stroke*1.5` elliptical kernel: penalize grazing a line edge, not just centre.
* `ink_energy()`: Gaussian blur `k=stroke*2`, normalized 0…1. Weak fallback so page degrades gracefully if model missing (`energy="ink-only"` in manifest).

**Why 0.8/0.2:** learned map carries the decision; ink only prevents total failure. Tuned empirically; ink alone has no valleys on tight Devanagari (Finding 4).

### Stage 3-global — Recursive DP seams (`linecut/seams.py`) — used when `mode=global`

**Fundamental:** dynamic programming shortest path. A seam enters left edge, exits right, steps ≤1px up/down per column → curves *around* descenders instead of through them. Single left-to-right DP pass gives globally cheapest path.

* `carve_seam(cost)`: `acc[:,x] += min(up,mid,down)` + backpointers, traceback from min of last column. Returns `(path, mean_cost)`.
* `pitch_from_baselines(prob)`: sum baseline map vertically → peaks → median spacing. Primary pitch. Fallback `line_pitch()` = autocorrelation skipping main lobe (original returned 4px vs true 43px before fix).
* `find_seams()`: recurse: profile → cheapest 8 local minima → carve in `±pitch*0.4` strip → keep cheapest if `mean_cost ≤ threshold (default 0.30)` → split at `mean(path)` → recurse both halves. Stop when `height < pitch*1.6` OR no cheap seam (second condition prevents shredding single lines into fragments). `max_depth=14`.
* `label_map()`: band index per pixel from seam stack.

**Confidence from this stage:** `seam_cost` (expensive = cut through ink = suspect).

### Stage 3-instances — Bands (`linecut/bands.py`) — DEFAULT (`method="bands"`)

**Adapted from SeamFormer (Vadlamudi et al., ICDAR 2023). Inverts the order:** coarse count/position FIRST from whole-page profile (robust, never fragments), then precise spine using ONLY ink inside a band around that position.

* `find_centerlines(prob, pitch)`: `profile=prob.sum(axis=1)`, Gaussian smooth `k=pitch*0.3`, peaks `>0.15*max`, enforce `min_sep=pitch*0.5` (strongest-first NMS).
* `recover_missed_centerlines()`: faint lines lose to global `0.15*max`. Re-check *within each gap* against gap-local max (`0.35*local_max`, `>0.06*global_max`). Only between confident lines, never past first/last (margins live there). Second pass if gap `>2×pitch`.
* `spine_in_band(prob, ink, y_center, half=pitch*0.55)`: weight = `0.7*prob + 0.3*ink`, column-wise weighted centroid, hold last-y through gaps, smooth with `k≈pitch` (NOT stroke — stroke-scale wobble shears glyphs sideways during rectification; measured bug).
* `local_kinks()`: second-derivative of smoothed spine `> pitch*0.35/window` → candidate straddling-two-lines.
* `resolve_split()`: at kink, sum energy in narrow local strip `±pitch*0.6` wide, `±pitch*1.5` tall → look for 2 peaks straddling spine, separated by `≥pitch*0.6`. Only split on confirmed local evidence, not kink alone (handwriting waviness also kinks but has no second peak).
* `extract_banded()`: full pass + locate-and-verify refinement. `assign_by_nearest_spine()`: every ink pixel → nearest spine's interpolated y at that column (1-indexed, -1 = no ink). Diacritics resolve correctly because comparison is to actual curve, not fixed boundary.

**Why bands over ribbons (`ribbons.py` bottom-up)?** Ribbons threshold highlighter → connected components → stitch fragments. Fragile: wrong stitch fuses two real lines, and failure recurs under different params. Bands excludes stray matras *by construction* (outside search region) not by post-hoc heuristic gate.

### Stage 4 — Ownership (`linecut/lines.py:assign_ownership` for global; bands owner for instances)

* Global: per connected component, count pixels per band. If `≥80%` in one band → whole component to that band (keeps descender intact). Else per-pixel along seam. Grow mask by 1 stroke (anti-aliased halo), white-out the rest.
* Instances: `owner==rid` mask per spine + neighbour-halo suppression: dilate *other* lines' ink by `stroke*2`, rectify both strips, paint neighbour ink white in own crop. Masks neighbour geometry, keeps own photo pixels intact (masking to own binary would discard 41% of real dark pixels on photos → speckle-shredding; measured).

### Stage 5 — Crop / dewarp / rectify (`linecut/lines.py:extract,dewarp` + `linecut/ribbons.py:rectify,trim`)

* Global `dewarp()`: per-column ink centre → interpolate gaps → smooth `k=12% width` → shift columns so centre runs level via `cv2.remap` cubic. Skip if `max|shift|<1.5px` or `<20%` valid columns.
* Instances `rectify()`: sample *perpendicular to own spine*: output column = arc-length along spine, output row = normal offset `height=pitch*1.8`. Straightens tilt + curvature in one remap. `trim()` to owned-ink bbox + `stroke*2` pad.
* `is_graphical_rule()`: drop solid rules (max connected width `>40%` crop, `aspect>10`, `ink_h<stroke*10`, `≤6` components) → `rules_filtered` count, not lines.
* `is_non_text_region()`: HSV saturation `>140` on owned pixels → watermark/stamp/logo reject (measured: watermark sat 220 vs text 60–65).
* Reading order: global = top-to-bottom bands; instances = `sort(round(centre_y/(pitch*0.6)), centre_x)`.
* Structure (`structure.py`): `find_rules` (directional opening `w//12`), `classify` → `grid|ruled_rows|columnar|plain`, `page_gutters`, `split_fields`, `assign_rows`. No model.

### Tier-0 — Table-first + stamp masking (`segment.py`, `api.py` Tier-0 block)

Runs BEFORE segmentation when `extract_tables=true`:

1. `table_extractor.extract_all_tables()` → bboxes.
2. `stamp_extractor.detect_stamps()` → bboxes.
3. `segment_src = decoded.copy(); cv2.rectangle(..., white, -1)` over each.
4. Line segmenter sees only prose. Cells OCR'd separately (§4.5). Final doc re-interleaves by y (`build_unified_document_blocks`, `reassemble_page_with_tables`).

**Why:** without this, prose cutter slices tables horizontally → column welding. Masking converts "tables + prose" into "prose-only" for the cutter, which is what it is good at.

---

## 3. AI/ML Core — models, layers, training, why

### 3.1 Model 1 — Kraken `blla` baseline segmenter (the segmentation brain)

**Where:** `linecut/energy.py:_load_model` → `kraken.lib.vgsl.TorchVGSLModel.load_model("kraken/blla.mlmodel")` → `kraken.blla.compute_segmentation_map()`.

**What it is (fundamentals):** semantic segmentation at pixel level. Input photo → per-pixel probability of 4 classes: `line-start-separator, line-end-separator, baseline, text-region`. We use `baselines/default` channel.

**Exact architecture (from `docs/01-architecture.md`, 1,261,540 params):**

```
input H=1800, W=variable, C=3
 Conv 7×7, 64, stride 2 + GroupNorm
 Conv 3×3, 128, stride 2 + GroupNorm
 Conv 3×3, 128 + GroupNorm
 Conv 3×3, 256 + GroupNorm
 Conv 3×3, 256 + GroupNorm
 BiLSTM along x (hidden 32)
 BiLSTM along y (hidden 32)
 Conv 1×1, 32 + GroupNorm
 BiLSTM along y (hidden 32)
 BiLSTM along x (hidden 32)
 Conv 1×1 → 4 channels, sigmoid
```

**Fundamentals gloss (for interview):**

* *Convolution:* local pattern filter (stroke fragments, edges). 7×7 stride-2 first layer = large receptive field cheaply + downsample.
* *GroupNorm (not BatchNorm):* normalizes per-sample channel groups; stable for small/variable batch sizes typical in segmentation training (batch=1 page).
* *BiLSTM along x then y, twice:* recurrence = memory along axis. LSTM cell has forget/input/output gates → carries baseline continuity across words/gaps. Bidirectional = left+right (or top+bottom) context. Doing it on **both axes, twice** is what lets it track a wavy baseline across full page width and know far-left ink belongs to same line. Pure CNN sees local texture; 2-D recurrence sees *line-ness*.
* *Sigmoid output:* independent per-pixel probability per class (not softmax — classes can overlap).

**Why this model (and not DBNet / Transformer / pure morphology):**

* Morphology cannot distinguish text from ruled lines/diagrams and has no valleys on tight Devanagari. Kraken's map on stained page C returns ~28 clean curved ribbons with stains/bleed gone (Finding 4) — makes seam idea viable at all.
* DBNet++ detects boxes/polygons, not pixel baselines with start/end separators; overkill + needs retraining for manuscripts. Kraken `blla` is pretrained on historical manuscripts (cBAD/READ-BAD family format) — closest to degraded Indic manuscripts.
* Transformer/diffusion at available data scale loses to 1.3M CNN+RNN; ceiling is training data, not capacity (`docs/01-architecture.md`: "deliberately no transformer").
* Pretrained metric plateaued ~0.60 for last 30 epochs → not saturated → fine-tuning on domain data is highest-value work (Finding 8). Plan: annotate 100–300 PhDIndic_11 pages via studio → `ketos segtrain` 45–90 min on M4 MPS.

**Limitations to state honestly:** needs roughly upright text (coverage collapses ~160× at 47° → hence Stage-1 deskew first); under-segments tightest Devanagari (21/28 on page C before bands+recovery → 25/25 after); upsampling heatmap + polygon vectorization dominate runtime (13–44s/page), not GPU — so MPS gives modest speedup, MLX port pointless (Finding 7).

### 3.2 Model 2 — `orient_net` 180° classifier (the flip resolver)

**Where:** `linecut/orient_net.py`, weights `linecut/orient_net.pt`. Used in `pipeline.py` when `auto_flip=true` (default OFF).

**Why needed (fundamental):** projection profile is invariant to 180° rotation. `line` upside-down ≡ same profile. Must learn glyph shape (e.g., Devanagari shirorekha on top, ascenders vs descenders).

**Exact architecture (`build_model()`):**

```python
def block(cin, cout, pool=True):
    Conv2d(cin, cout, 3, padding=1) + BatchNorm2d + ReLU [+ MaxPool2d(2)]

Sequential(
  block(1,32),      # 1×32×192 → 32×16×96
  block(32,64),     # → 64×8×48
  block(64,128),    # → 128×4×24
  block(128,128, pool=False),  # → 128×4×24
  AdaptiveAvgPool2d(1),  # → 128×1×1 (handles variable width)
  Flatten,              # → 128
  Linear(128,64) + ReLU + Dropout(0.3),
  Linear(64,2)          # logits: [upright, flipped]
)
```

* Input: `prepare()` → gray → scale height to 32px, aspect-preserved width capped 192px, left-aligned on white 32×192 canvas → `(x−0.5)/0.5` normalize.
* Inference: `flip_probability(crops)` → softmax `[:,1]` per line → width-weighted mean (long lines carry more glyph evidence). `>0.65` → re-run pipeline with `rotate_extra+180°`.
* Params: ~ (1*32*9 + 32*64*9 + 64*128*9 + 128*128*9) ≈ 240K conv + 8K FC — tiny by design.

**Training & why it failed (must know for senior interview):**

* Data: 129,674 Aksharantar native words (20 scripts) rendered in 50+ macOS system fonts + English dict words, with tofu-detection, synthetic degradation (blur, dilate/erode, perspective, lighting, noise). Labels free (rotate = flipped). `train_orient.py --samples 6000 --epochs 14 --batch 128 --device mps` (~3–5 min M4).
* Result: **98.7% synthetic val but 55.28% on real handwriting** (sample 33%, Devanagari letter 47%, form 58%, notes 66%) — classic **sim-to-real gap**: CNN overfit rasterizer artifacts/clean proportions; missed irregular stroke dynamics, ink pooling, variable aspect.
* Consequence: auto-invert on this model would corrupt ~45% of upright docs → `auto_flip` disabled by default; 180° resolved downstream via OCR-confidence voting or retraining on real `PhDIndic_11` crops. Two hand-heuristics (mean baseline prob, separator asymmetry) also coin-flips (2/4 each) → not shipped (Finding 6).
* **Interview line:** *"Labels are free here, signal is shape-only, so a small CNN is justified — and only here. Everywhere else geometry suffices."*

### 3.3 Model 3 — PaddleOCR (print + Indic workhorse)

**Where:** `linecut/dual_ocr.py:get_paddle_ocr`, `run_paddle_on_crop`, `_scan_wide_paddle`.

**Fundamentals:** PaddleOCR = two-stage: **DB (Differentiable Binarization) text detector** finds word boxes inside the crop + **CRNN/SVTR recognizer** (CNN backbone + sequence model + CTC/attention decode) reads them. Multilingual checkpoints (`lang=hi` for Devanagari/Hindi, `en` for Latin). We disable its orientation/unwarping (`use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False`) because linecut already deskews/rectifies.

**How we use it (non-obvious details):**

* Per-language singleton cache + `_INFERENCE_LOCK` (Paddle's C++ runtime crashes under concurrent infer without lock) + `ThreadPool(max_workers=4)` across lines.
* Wide-crop sliding: if `W>450` and text `<45 chars` (CTC truncation signature), slide `max_chunk_w=420, overlap=60`, split at lowest-ink column, pad 10px white, concat `rec_texts`.
* Edge-noise filter: if `>1` texts and any `score≥0.90`, drop fragments with `score<0.65` AND (`len<12` or no alnum) — kills ascender/descender bleed from neighbours.
* Cell path: `pad 12px if h<35 else 6px`, retry tight cells at 1.5× cubic upscale.
* Confidence: `mean(rec_scores)`, rounded 4dp.

**Why chosen:** best open printed-text + Indic-script (Devanagari) accuracy; TrOCR is Latin-only. Paddle preferred for structured docs, labels, tables. Indic rule: if Paddle text contains `\u0900–\u097F`, choose Paddle regardless (`paddle_indic`, floor 0.70).

### 3.4 Model 4 — TrOCR-small-handwritten (handwriting specialist)

**Where:** `dual_ocr.py:get_trocr`, `run_trocr_on_crop` (`microsoft/trocr-small-handwritten`).

**Fundamentals:** **VisionEncoderDecoder**: ViT-style image encoder splits crop into patches → Transformer encoder → autoregressive Transformer decoder generates subword tokens (XLMRoberta tokenizer). No explicit detection; whole crop → string. Pretrained in stages: synthetic printed → handwritten (IAM). Small variant ≈ tens of millions params (ViT-small-class encoder + compact decoder) — fast enough per-line on CPU, hence `trocr-small` not base/large.

* Code: `processor(pil).pixel_values` → `model.generate(max_new_tokens=48, output_scores=True)` → `tokenizer.batch_decode` → confidence = `mean(max(softmax(logit)))` per generated token (0.85 fallback if no scores).
* Runs in same 2-worker pool as Paddle per crop (`scan_single_crop_parallel`).

**Why chosen + guardrails:** excels on continuous cursive where Paddle's detector fragments. But (a) Latin-only → loses Hindi, (b) hallucinates on blank/noise because generative decoder *must* emit something: known Wikipedia-pretraining loops (`helplearn, communityportal, displaystyle, abcdef...`, full list `_TROCR_HALLUCINATION_PATTERNS`) + alphabet loops. Mitigations: `is_trocr_hallucination()` → disqualify; `max(p_conf,t_conf)<0.50` → empty; single-char `<0.70` → empty; Paddle-empty + (`t_conf<0.75` or `len<3`) → empty. Without these, blank paper returns fake encyclopedia text at 0.93 confidence — must cite in interview.

### 3.5 Dual reconciliation — the arbitration algorithm (`reconcile_line`)

```
p_text,p_conf / t_text,t_conf
 → strip hallucinations
 → if max<0.50 → empty
 → single-char gate
 → if both empty → empty
 → if !p_text → trocr_only (if t_conf≥0.75 and len≥3 else empty)
 → if !t_text → paddle_only
 → sim = SequenceMatcher(p.lower(), t.lower())
 → if Indic in p → paddle_indic
 → elif sim≥0.85 → consensus (longer, +0.05 bonus capped 1.0)
 → elif p≥0.85 and p≥t → paddle_preferred
 → elif t>p+0.20 and len>3 → trocr_preferred
 → else arbitrated (higher conf)
 → FORM_CORRECTIONS regex (FQRM→FORM, MUTHER'S→MOTHER'S, etc.) + `::`/`\s+` cleanup
```

Plus **raw-crop fallback** (`scan_manifest_lines_parallel`): if clean-crop confidence `<0.96` and `lines_raw/` exists, rescan raw; keep raw if higher conf OR (`len+5` and `≥0.88`). Seam-masking sometimes degrades glyphs; raw recovers.

### 3.6 Model 5 — Mercury-2.5 reasoning LLM (`linecut/llm_refiner.py`)

**Fundamentals:** large autoregressive Transformer with reasoning effort; used as *correction + structuring* pass, not extractor. Prompt sends reading-order lines + confidences (or table markdown + draft record), demands strict JSON (`corrected_lines[{line,corrected,change_summary}] + markdown`, or `refined_record{DoLR schema} + markdown_table`), `reasoning_effort=high`, 45s timeout, strips ```json fences.

**What it fixes:** optical confusions via semantics/grammar/domain (`s/o,w/o,c/o,alias`, joint parentage `रामेश्वर पुत्र हरपाल` → `name + father_or_husband_name`, transliterated revenue terms, header formatting). Land path re-runs `validation.run_full_validation` after refine.

**Why last, not first:** LLM cannot see pixels; feeding it raw OCR without geometry/confidence invites hallucination. Pipeline gives it ordered, scored, layout-typed evidence + constrains output to JSON diff. Failures degrade to `md_text = dual_ocr.export_markdown(...)` fallback, never crash.

---

## 4. Classical CV that makes ML usable (know the math)

| Piece | Math / op | Why |
|---|---|---|
| Otsu | minimize intra-class variance of ink/background histogram | parameter-free threshold per page illumination |
| Distance-transform stroke | `2×median(ridge)` | scale-invariant constant base |
| Directional morphology (tables) | `open(bw, rect(W//25,1))` + `open(bw, rect(1,H//25))`, `close 3×3` | long horizontal/vertical rules survive, text doesn't; gap-closing for scans |
| Canny + density (stamps) | `mean(edges>0)` per row, MA smooth `H//25`, `≥0.20` sustained `≥25px`, width `≥25%` page | guilloche 3–4× denser than prose; tables zeroed first |
| DP seam | `acc[x]+=min(up,mid,down)`, traceback | cheapest left-right path curves around ink |
| Autocorrelation pitch (fallback) | `argmax(acorr)` after skipping main lobe | periodicity = line spacing; main lobe ≠ period |
| Ownership 80% | `bincount(comp×bands+label)` | descender stays whole; straddlers split per-pixel |
| Remap dewarp/rectify | `cv2.remap(cubic)` along centre/normal | subpixel straightening recognizers expect |
| NMS for peaks | strongest-first, `min_sep` suppression | one peak per line, no doubles |

---

## 5. Tables & stamps — Tier-0 in depth

**Tables (`table_extractor.py`):** `adaptiveThreshold(~gray,15,-2)` → `h_lines/v_lines` → `grid=h|v` → `RETR_TREE` contours → reject full-page frames (`w≥0.98W & h≥0.95H` or `h≥0.85H`) → require `h_density≥1.2w & v_density≥0.8h` → drop outer boxes enclosing inner ones → dedupe IoU>0.75 → sort top-to-bottom. Cells: invert grid → `RETR_CCOMP` → `≥20×12px`, trim 1–2px (1px if `<32px` to save ascenders), flag `merged=w>0.65×table_w` → drop containers enveloping others → `cluster_cells_into_grid`: sort by y, group by vertical overlap `>0.35×min(h)` or `|mid|<18px`, sort each row by x → `row_idx/col_idx/is_header`. Keep tables with `≥2` cells. Cells OCR'd with padding/upscale (§3.3) → Markdown (`| … |` + `---` header).

**Stamps (`stamp_extractor.py`):** Canny 50/150 → zero table zones → row density → MA smooth → bands `≥0.20` (release at 0.18 hysteresis) → horizontal extent `col_density>0.04` → keep `w≥0.25W` → `edge_density` + `revenue_stamp_medallion` + save `stamps/stamp_XX.png`. Masked in Tier-0 so seams/OCR never hallucinate engravings.

**Schema (`land_records.py`):** header keyword scoring (`normalize_field_name`: share→area→khasra→khata→owner→class→mutation→crop, Hindi+English) → best header row → data rows after it → `plots{khasra_no,area,area_numeric,classification,crop}`, `owners{name,share,share_fraction}`, `mutations{no,details}`, `metadata{state,district,tehsil,village,year,survey_no,sub_div}` via bilingual regex → composite `survey/subdiv` → `validation`.

---

## 6. Confidence & calibration — the safety system

| Signal | Source | Formula / threshold | Meaning when bad |
|---|---|---|---|
| `angle_margin` | Stage 1 | `score(win)/score(rival>10°)`; `<1.5` → `angle_uncertain` | skew ambiguous, cuts will be diagonal |
| `seam_cost` | Stage 3 | mean DP cost; `>threshold*0.8` (=0.24 at 0.30) → `review` | cut sliced through ink |
| `height_ratio` | Stage 3/5 | `bbox_h/pitch`; `>1.7` or `<0.45` → `review` | merged double-line or fragment |
| `curved/off_axis` | Instances | `curvature>stroke*2`, `curvature>pitch*0.5` or `ink<12×stroke²` → `review` | wavy / tiny suspect |
| `flip_probability` | orient_net | width-weighted softmax; `>0.65` → auto-rotate | page upside-down |
| `confidence_ocr` | Dual-OCR | Paddle mean / TrOCR token-mean / reconciled +0.05 | recognition doubt; `status` tells arbiter |
| `validation` | Rules engine | `passed/failed/skipped`, `review_required` | business invariant violated → HITL |

**Philosophy (Finding: "On zero flaws"):** 100% on degraded handwriting is not SOTA-achievable. Contract on *"no unflagged errors at N% review rate"* — measurable, verifiable. Every line carries signals; every record carries audit (`checks[{rule,status,message}]`).

---

## 7. Accuracy — how it is collected (say this precisely)

1. **Line-count accuracy (empirical, `docs/02-findings.md` + `04-enterprise-roadmap.md` §4):** 4 benchmark pages with human-counted ground truth. Current: A 8/8, B 23/~22, C 25/~24–25 (bands+recovery fixed 21→25), D 23/~24. Report as *"matches / approximate / under-segmented"*, never as single %. Method: run `segment.py`, compare `lines_found` vs human count, inspect `page_reassembled.png` top-to-bottom (stack doubles as verification view).
2. **Orientation accuracy:** synthetic val 98.7% vs real held-out 55.28% (per-page breakdown in findings). Collected by rendering Aksharantar words vs hand-cropping real lines, `flip_probability` vs true flip. Lesson: synthetic ≠ real.
3. **OCR accuracy:** *not* WER-measured on client pages (no transcripts). Proxied by `confidence_ocr` distribution + `status` histogram (consensus rate) + spot-reading `document.md`. Unit-tested arbitration logic (`test_reconcile_*`: consensus, Wikipedia-hallucination suppression, low-conf reject).
4. **Table accuracy:** synthetic 3×3 grid image in `test_land_records.py` (`detect/cluster/cells ≥4`, bbox ±10px) + integration `POST /segment (ocr=false)` → `land_record.schema_version==DoLR-DILRMP-v2.0` → `GET /jobs/{id}/land_record.json`.
5. **Business-rule accuracy:** deterministic invariants, fully unit-tested: `area_balance` (`Σplots vs reported`, tol 0.002, parses `0.1000 हेक्टेयर`, `0000.17.00` Ha.Ars.SqM), `ownership_shares` (`Σ==1.0`, tol 0.01, parses `1/2,60%,पूर्ण`), `khasra_format` (regex + duplicates). `run_full_validation` → `validation_passed/review_required`.
6. **What to admit:** no held-out WER/CER on client handwriting yet; needs 20+ annotated client docs for audit sign-off (Roadmap Step 6). Pseudo-label self-training without 50–100 hand-corrected anchors *bakes in* under-segmentation bias — must anchor (`docs/03-datasets.md`).

---

## 8. API / CLI / artifacts cheat-sheet

**CLI:** `segment.py IMAGE -o OUT [--mode instances|global] [--device cpu|mps] [--threshold 0.30] [--no-dewarp] [--ocr --lang hi|en] [--no-tables] [--no-llm] [--debug]` → `lines/`, `lines_raw/`, `manifest.json`, `document.{md,txt,docx}`, `land_record.json`, `tables.md`, `latent.json`, `page_reassembled.png`, `stamps/`, `debug/{energy,seams,ownership,highlighter,instances}.png`.

**API (`api.py`, v2.1, `uvicorn api:app --port 8000`, docs at `/docs`):**

| Method | Path | Key params / body | Returns |
|---|---|---|---|
| GET | `/health` | — | `{status, jobs_dir}` |
| POST | `/segment` | multipart `image` + forms above; `MAX 40MB` | manifest + `lines[{index,file,png_base64,text,confidence_ocr,dual_ocr,spine_on_source,polygon_on_source}]` + `tables,stamps,land_record,validation,markdown,documents{md,docx,txt,latent,land_record urls}` |
| GET | `/jobs/{id}/document.{md,docx,txt}` | `job_id alnum` | file |
| GET | `/jobs/{id}/latent.json` | — | `{job_id,source,lines_found,deskew_deg,layout,lines}` |
| GET | `/jobs/{id}/land_record.json` | — | DoLR JSON |
| GET | `/jobs/{id}/lines/{index}?variant=clean\|raw` | — | PNG crop |
| DELETE | `/jobs/{id}` | — | `{deleted}` |

`manifest.json` (instances): `mode,method,stroke_width_px,scale_factor,deskew_deg,deskew_margin,line_pitch_px,layout,rules_*,gutters,rows,ribbons_detected/after_merge,lines_found/curved/flagged,angle_spread_deg,reading_order,seconds,lines[]`. Global adds `angle_deg,angle_margin,angle_uncertain,seams,energy`.

---

## 9. Why-not alternatives (interview differentiator)

* **Why not end-to-end TrOCR on full page?** Loses geometry, tables weld, no confidence per cut, hallucinates. Pipeline gives ordered, scored evidence LLM can correct.
* **Why not Transformer segmenter?** Data < capacity need; 1.3M CNN+BiLSTM wins, trains/fine-tunes in <90 min, runs CPU.
* **Why variance not SSD for angle?** Roughness is angle-invariant; band-gap structure is not. Wrong objective = confident-wrong.
* **Why pitch from learned ridges not autocorrelation?** Main lobe masquerades as period (4px vs 43px).
* **Why bands not ribbons?** Construction-time exclusion beats post-hoc gates; kinks verified by local re-check, not blind split.
* **Why Paddle + TrOCR not one?** Print/Indic vs handwriting are different distributions; arbitration + hallucination gates beat either alone.
* **Why LLM last?** No pixels → must be constrained corrector on scored evidence, with deterministic fallback.
* **Why MPS not MLX?** Kraken is PyTorch; bottleneck is CPU upsample/vectorize, not matmul.

---

## 10. Open defects (say proactively — senior signal)

* 180° auto-flip unresolved (55% real acc) — OCR-vote or real-data retrain needed.
* Tightest Devanagari still riskiest — needs 50–100 PAGE-XML fine-tune.
* Ruled borders as lines — mostly fixed by `is_graphical_rule`, edge cases remain.
* 13–44 s/page — optimize upsampling/vectorization, not model.
* Stamp detector is density-heuristic — ornate borders can over-trigger; tables excluded first to limit.

---

## 11. Interview Q&A bank (one-line answers)

1. **How does the segmenter work?** Tier-0 mask → normalise scale → variance deskew → Kraken cost map → bands/spines or DP seams → ownership → rectify → OCR → LLM → validate.
2. **What are bands?** Coarse whole-page peaks first, then per-line centroid fit restricted to `±0.55×pitch` strip; kinks split only on locally confirmed double peaks; pixels assigned to nearest spine curve.
3. **Which NNs?** Kraken blla (segmentation), orient_net custom CNN (flip), PaddleOCR DB+CRNN (print/Indic), TrOCR ViT+Transformer (handwriting), Mercury-2.5 LLM (correction).
4. **How many layers?** Kraken: 5 conv + 4 BiLSTM + 2×1×1 (≈1.26M). Orient: 4 conv blocks + pool + 2 FC. TrOCR-small: ViT-small-class encoder (~12L) + 6L decoder (~62M class). Paddle: DB-det + SVTR/CRNN-rec (version-dependent, cited as engine).
5. **Why this pipeline?** Classical=geometry, learned=text-ness; opposite failures compose to full coverage; scale-invariance via stroke; calibrated uncertainty instead of fake 100%.
6. **What is confidence?** Cut cost + height ratio + angle margin + OCR token/det scores + arbiter status + rule audit; `review=true` routes to human.
7. **How is accuracy collected?** Human line counts A–D, synthetic-vs-real flip acc, deterministic rule unit tests (14+), synthetic-grid table tests, API integration test; no client WER yet — honest gap with anchor-plan.
8. **What is pitch?** Median inter-line spacing from learned ridges; sets band half-height, seam stop (`1.6×pitch`), kink thresholds.
9. **Why 0.8/0.2 energy?** Learned dominates; ink prevents collapse when model unsure/absent.
10. **Why threshold 0.30?** Max mean seam cost to accept cut; higher shreds lines, lower misses cuts; flagged at 0.24.
11. **Paddle vs TrOCR when disagree?** Sim≥0.85 consensus; Paddle≥0.85 print; TrOCR+0.20 hand; Indic→Paddle; else higher conf; hallucinations vetoed.
12. **TrOCR hallucinations?** Wikipedia loops + alphabet loops on blanks at ~0.9 conf; pattern list + `<0.50` + single-char + Paddle-empty gates suppress.
13. **Tables without welding?** Directional kernels isolate grid → invert → components = cells → cluster to rows/cols → per-cell OCR with padding → Markdown + DoLR mapping.
14. **Stamps?** Canny density ≥0.20 sustained ≥25px, width ≥25% page; masked pre-segmentation.
15. **DoLR schema?** `DoLR-DILRMP-v2.0`: metadata/plots/owners/mutations/reported_total/validation.
16. **Area invariant?** `|Σplots − reported| ≤ 0.002`, parses Hindi units + `Ha.Ars.SqM`.
17. **Shares invariant?** `|Σ−1.0| ≤ 0.01`, parses fractions/percent/`पूर्ण`.
18. **Khasra check?** Regex `^[0-9]+([/-][0-9A-Za-z]+)*$` + duplicates.
19. **Bands vs seams?** Bands=default instances (mixed angles/curves); seams=global (flat pages, faster mental model).
20. **Dewarp vs rectify?** Global shifts columns level; instances samples perpendicular to spine (tilt+curve together).
21. **Scale factor?** `3.0/stroke` clipped 0.35–4.0; all constants downstream in stroke units.
22. **MPS speedup small why?** Bottleneck CPU upsample/vectorize, not GPU matmul.
23. **Why GroupNorm in Kraken, BatchNorm in orient?** Kraken trains batch-1 pages (GN stable); orient trains batch-128 crops (BN fine + cheaper).
24. **Why Dropout 0.3 in orient?** Tiny net on synthetic fonts overfits fast; 0.3 + AdaptiveAvgPool regularize.
25. **LLM prompt?** Ordered lines+confs → strict JSON diff + markdown; land: tables-md + draft → refined DoLR JSON; re-validate after.
26. **Raw fallback?** Clean `<0.96` → rescan `lines_raw/`; keep if higher or much longer at ≥0.88.
27. **Reading order?** Bands: `round(y/(0.6×pitch)), x`; final doc: lines+tables+stamps sorted by y.
28. **Datasets?** Aksharantar (orient-synthetic only), PhDIndic_11 1469pp (needs annotation for seg fine-tune), DIBCO20 (binarize test), cBAD/READ-BAD (pretrain family), client pages (highest value, missing).
29. **Biggest risk?** Unflagged merge on tight Devanagari → mitigated by bands+recovery+kink-verify + review flags + anchor fine-tune.

---

## 12. One-page revision sheet (last-night)

* Order: mask → scale(3px) → deskew(variance,±45,0.2) → cost(0.8L+0.2I) → bands(0.55pitch,0.15peak,0.6sep) / seams(0.30) → own(80%) → rectify(1.8pitch) → Dual(Paddle+TrOCR, <0.50 empty, 0.85 consensus) → LLM(JSON) → validate(0.002,0.01,regex).
* Nets: Kraken 1.26M CNN+BiLSTM×4; Orient 4-conv+2FC ~0.25M, 32×192, >0.65 flip; Paddle print/Indic; TrOCR-small hand Latin, 48 tokens; Mercury-2.5 refine.
* Confs: seam>0.24, hr∉[0.45,1.7], margin<1.5, flip>0.65 → review/HITL.
* Acc: A8/8 B23/22 C25/25 D23/24; orient synth98.7 real55.3; rules unit-tested; no client WER yet.
* Endpoints: `POST /segment`, `GET /jobs/{id}/{document.md,docx,txt,latent.json,land_record.json,lines/i}`.

*End of master notes — generated from current `feature/table-first-pipeline` code + `docs/01–05`.*
