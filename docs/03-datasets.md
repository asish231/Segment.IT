# Datasets

## Licensing — read before training

Most academic document datasets are released **research-only**. A model trained on
research-only data cannot generally ship inside a commercial deliverable. This is a
contractual problem, not a technical one, and it is cheapest to resolve before training
rather than after.

Check the licence of every dataset below against the terms of the engagement. The same
applies to kraken's pretrained weights: the *code* is Apache-2.0, but pretrained model
weights can carry separate terms and must be verified independently.

## What is on hand

### Aksharantar (`archive (3).zip`, 747 MB)

Transliteration corpus from AI4Bharat. JSONL, one record per line:

```json
{"unique_identifier": "brx1", "native word": "आंनासो", "english word": "angnasw",
 "source": "AK-Uni", "score": null}
```

20 scripts: asm ben brx guj hin kan kas kok mai mal mar mni nep ori pan san sid tam tel urd.
Validation splits extracted to `corpus/data/` — 75,952 unique words, 18 MB.

**This is text, not images.** It can train exactly one thing: the orientation classifier,
by rendering real words in system fonts. It cannot improve segmentation.

### PhDIndic_11 (`PhDIndic_11.zip`, 847 MB)

1,469 scanned handwritten document pages across 11 scripts:

| script | pages | script | pages |
|---|---|---|---|
| devnagari | 221 | tamil | 121 |
| urdu | 202 | roman | 115 |
| oriya | 173 | malayalam | 108 |
| bangla | 162 | gujarati | 101 |
| gurumukhi | 133 | telugu | 86 |
| | | kannada | 47 |

TIFF, roughly 800–1700 × 2000–2500px, colour. Generally clean scans, white ground,
well-separated lines — easier than the degraded client pages.

**No annotations.** This dataset was built for *script identification*, so there are no
line polygons or baselines. It is raw material for the annotation studio, and it is the
most valuable thing available: real Indic handwriting at volume, ready to label.

### DIBCO 2017 (`DIBCO2017_Dataset.7z`, 44 MB)

20 degraded document images, BMP. **The ground-truth binarization masks are not in this
archive** — only the input images.

Limited use as delivered: a hard test set for stage 0 binarization on degraded paper. Not
training data without the GT masks, which are distributed separately.

## What each dataset can and cannot do

| need | dataset | status |
|---|---|---|
| orientation classifier | Aksharantar + system fonts | ready, labels synthesised |
| better line segmentation | PhDIndic_11 | needs annotation first |
| binarization robustness | DIBCO 2017 | test only, GT masks missing |
| client-domain accuracy | client pages | not yet provided |

## What is still missing

The one thing that would most improve segmentation is **document images with line-level
annotations** — pages where every text line has a baseline or polygon drawn. Two routes:

**Annotate PhDIndic_11 ourselves.** 1,469 pages available; 100–300 annotated is enough to
fine-tune. This is what the studio is for, and correction-based labelling makes it an
afternoon rather than a week. See [04-annotation.md](04-annotation.md).

**Obtain pre-annotated sets.** Search these names directly:

| dataset | content | relevance |
|---|---|---|
| cBAD / READ-BAD | historical archival pages, baselines | highest — same annotation format kraken trains on |
| DIVA-HisDB | historical manuscripts, pixel-level layout | high |
| IAM Handwriting DB | English handwritten, line-segmented | standard benchmark |
| IAM-HistDB | Saint Gall, Parzival | historical handwritten |
| FUNSD / XFUND | scanned forms, field annotations | matches the form document class |
| PubLayNet, DocBank | printed layout, very large | low — printed, not handwritten |

Indic-specific sets (IIIT-INDIC-HW-WORDS, IIIT-HW-Dev) are mostly **word-level**, useful
for recognition later but not for line segmentation now.

## How datasets connect to the pipeline

```
Aksharantar  ──render──>  synthetic lines  ──train──>  orientation classifier
                                                           |
                                                      stage 1 completion

PhDIndic_11  ──segment──>  pre-filled lines  ──correct──>  PAGE-XML
                              (studio)                        |
                                                         fine-tune stage 2

DIBCO 2017   ──────────────────────────────────────────>  stage 0 test set

client pages ──segment──>  pre-filled lines  ──correct──>  PAGE-XML
                              (studio)                        |
                                                    highest-value fine-tune
```

The studio is the junction. It turns unannotated images from any source into the one
format that trains the segmenter.

## On self-training with pseudo-labels

Tempting and partly valid: run the pipeline over thousands of pages, keep the confident
outputs, train on them, repeat. The confidence signals already exist to select them.

**It cannot fix systematic bias.** The pipeline under-segments tight Devanagari
*consistently*. Those confident-looking merged bands become labels that teach the model
that merging is correct, and the model then agrees with itself, permanently. Self-training
corrects random error, never the teacher's bias.

Anchoring fixes it: keep 50–100 genuinely hand-corrected pages of the hardest class in
every training epoch. Those contradict the bias each pass, and pseudo-labels then safely
scale that anchor across thousands of pages. Do not run the loop unanchored.
