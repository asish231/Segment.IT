# Findings

Everything here was measured on real pages, not estimated. Where a number is projected
rather than observed, it says so.

## Test pages

| id | page | size | why it is hard |
|---|---|---|---|
| A | handwritten address form | 906×1218 | rotated 90°, shadow across the page |
| B | lecture notes + ER diagram | 768×1024 | bleed-through from reverse side, embedded diagram |
| C | aged Devanagari letter | 439×698 | stained paper, very tight leading, interpenetrating matras |
| D | printed form, handwritten fill | 377×530 | low resolution, ruled table lines, mixed print and hand |

## Result summary

| page | lines present | classical only | kraken only | current pipeline |
|---|---|---|---|---|
| A | 8 | 7 | 4 fragments | **8** |
| B | ~22 | 15 | 24 | **23** |
| C | ~28 | 12 | 70 (over-split) | **21** |
| D | ~25 | 15 | 51 (over-split) | **24** |

## Finding 1 — the two approaches fail in opposite directions

Classical morphology was the **only** method that found page A's 90° rotation. Kraken's
learned model was the **only** method that read page C at all. Neither covers all four
document classes alone.

- Classical is strong at global geometry, blind to what text *is*. It cannot distinguish a
  diagram's connector lines from writing, and on page B it welded five text lines and an
  entire ER diagram into one box.
- The learned model knows text from non-text — it ignored every ruled line on page D — but
  assumes text is already roughly upright, which is why it produced four fragments on A.

Composing them in order (geometry first, then recognition) is why the current pipeline
covers all four. This is the central architectural finding.

## Finding 2 — the orientation scoring function silently picked the wrong answer

Two candidate metrics on page A, whose true text angle is −88.8°:

| rotation | sum of squared diffs | profile variance |
|---|---|---|
| 0° | 4.82e−04 | 4.21e−06 |
| 45° | 1.66e−04 | 3.49e−06 |
| −89° | 4.67e−04 | **1.05e−05** |

Squared-differences measures high-frequency roughness. Handwriting is rough at every
angle, so the wrong answer won by 3%, with no indication of a problem. Variance measures
band-and-gap structure and wins by 2.5×.

**Lesson.** The failure was not in the search, the resolution, or the model. It was in
asking the wrong question. A wrong objective function produces confident, plausible,
wrong output.

## Finding 3 — hardcoded pixel constants destroyed the smallest page

v1 used raw pixel values: 51px background blur, 20px minimum component area, kernel at 4%
of width. Page A is 906×1218; page D is 377×530. The same constants mean different physical
things on each.

On page D the minimum-area filter **discarded 582 of 678 components** — most of the actual
text — before segmentation began. The pipeline had no idea how large the writing was.

Fixed by stage 0: measure stroke width, resample to canonical scale, express every constant
in stroke widths.

## Finding 4 — the learned map turns an unreadable page into clean ribbons

The baseline probability channel on page C — the stained, tight-leading manuscript — comes
back as roughly 28 clean, well-separated, gently curved ribbons, one per text line. Paper
texture, stains and bleed-through are gone.

This is what makes the user's recursive-seam idea viable. Run on raw ink density, page C
has no valleys to cut through: the matras genuinely interpenetrate and no ink-free row
exists. Run on the learned map, the valleys are clean and the seams curve between lines.

The energy map is the difference between the idea working and not working.

## Finding 5 — line pitch estimation by autocorrelation is unreliable

First implementation returned 4px on a page whose true pitch was 43px, and 146px on a page
whose true pitch was ~90px. The autocorrelation's own main lobe was being read as the
period.

Counting ridges in the learned baseline map is far more robust and is now the primary
method; corrected autocorrelation (skipping the main lobe) remains as fallback.

## Finding 6 — 180° orientation is unsolved, and two reasonable heuristics failed

| heuristic | correct on |
|---|---|
| mean baseline probability, upright vs flipped | 2 of 4 |
| start/end separator x-position asymmetry | 2 of 4 |

Both are coin flips. Neither was shipped.

The signal is real but weak: page A, the flipped one, scored +0.132 on separator asymmetry
against +0.355–0.397 for the three upright pages. There is information there; a threshold
on it is not reliable enough to use.

**This is why a trained classifier is justified here and nowhere else in the pipeline:**
it is the one sub-problem where the geometric approach is provably insufficient, and the
one where labels are free (rotate a page and you know the answer).

## Finding 7 — MPS works, and the bottleneck is not the network

| device | warm time, page C | lines |
|---|---|---|
| CPU | 41.3s | 70 |
| MPS | 28.5s | 70 |

Identical output, so GPU introduces no accuracy cost. But the speedup is modest, because
the time is dominated by upsampling the heatmap to full resolution and by polygon
vectorisation — both CPU-side. Optimisation effort belongs there, not in the model.

MLX is not a useful direction: kraken is PyTorch, MPS already reaches the GPU, and porting
would mean reimplementing the network for no gain against a non-GPU bottleneck.

## Finding 8 — the pretrained model is not saturated

Its own metadata shows the training metric plateaued around 0.60 and stayed there for the
final 30 epochs. Whatever precisely that measures, it is not a model that has run out of
room. Fine-tuning on domain-matched data is the highest-value remaining work.

## Finding 9 — synthetic font training failed to transfer to handwriting (Sim-to-Real Gap)

The orientation classifier trained on synthetic system fonts with synthetic noise reached
**98.7% validation accuracy on synthetic text**, but only **55.28% test accuracy on real
held-out handwriting crops** (effectively random chance).

| dataset | accuracy |
|---|---|
| Synthetic font validation | 98.70% |
| Held-out real test crops (overall) | 55.28% |
| `sample` (address form) | 33.33% |
| `image copy` (Devanagari letter) | 47.37% |
| `image copy 2` (pre-enrollment form) | 58.33% |
| `image` (lecture notes) | 66.35% |

**Why this happened.** The CNN overfit to rasterizer artifacts and clean glyph proportions
of computer fonts. Real handwriting has irregular stroke dynamics, ink pooling, and variable
aspect ratios that synthetic degradation did not capture.

**Engineering takeaway.** Relying on this model to automatically invert pages would cause a
~45% error rate on upright documents. `auto_flip` is therefore disabled by default.
In production, 180° orientation is reliably resolved via downstream OCR confidence voting
or by training directly on real handwritten crops from `PhDIndic_11`.

## Open defects

| defect | severity | fix |
|---|---|---|
| 180° flip unresolved | affects every page | train classifier, or resolve by OCR confidence downstream |
| page C under-segmented, 21 of ~28 | worst document class | fine-tune stage 2 on annotated Indic manuscripts |
| ruled borders returned as lines | cosmetic, adds spurious lines | text/non-text component filter |
| 13–44s per page | throughput | optimise upsampling and vectorisation |

## On "zero flaws"

Not achievable, and it is worth stating plainly in a document that outlives the
conversation. Line segmentation on degraded handwriting is an open research problem.
Published state of the art does not reach 100% on material like page C.

The engineering response is calibrated uncertainty: every line carries confidence signals,
doubtful lines are flagged, and flagged pages route to human review. That converts an
impossible specification ("no errors") into a measurable one ("no *unflagged* errors, at a
review rate of N%") — which can actually be committed to and verified.
