# Architecture

## The shape of the problem

A page arrives as pixels. Three things are unknown: how the page is rotated, how big the
writing is, and where one line ends and the next begins. Each needs a different kind of
answer, and using the wrong kind is how most attempts fail.

- **Rotation** is a global geometric fact. Cheap and exact to compute by search.
- **Scale** is a measurement. Read it off the image; never assume it.
- **Line boundaries** require knowing what handwriting looks like. That needs a model.

The pipeline is built around that split. Classical code handles geometry, a learned model
handles recognition of text-ness, and classical code again handles the pixel accounting.

## Stages

```
     source image
          |
   [0] measure scale           stroke width -> resample to canonical size
          |
   [1] find orientation        180 deg sweep, pick max profile variance
          |
   [2] build energy map        CNN baseline probability + ink density
          |
   [3] recursive seam split    DP min-cost paths, recurse, stop on pitch
          |
   [4] assign pixel ownership  per component, per pixel where straddling
          |
   [5] crop, dewarp, manifest  upright line images + positions + confidence
          |
   ordered line crops
```

### Stage 0 — measure scale

`linecut/core.py`

Binarize by estimating the page's own illumination (median blur on a downscaled copy,
which is fast and equivalent for a low-frequency signal), subtract it, then Otsu. Take the
distance transform of the result, find its ridge, and the modal ridge value doubled is the
pen stroke width.

Resample the page so one stroke is ~3px. Every constant downstream is then expressed in
stroke widths rather than pixels.

**Why this exists.** An earlier version used raw pixel constants — a 51px blur, a 20px
minimum component area. On a 377×530 form that minimum-area filter discarded 582 of 678
components, most of the actual text, before segmentation started. The pipeline could not
see how big the writing was. Scale normalisation is the fix, and it is the single most
important stage for cross-document robustness.

### Stage 1 — find orientation

`linecut/core.py:find_orientation`

Rotate the binary image to every angle across a full 180°, project ink onto the vertical
axis, and score the profile. Coarse sweep at 1°, then refine at 0.2°.

**The scoring function is the whole stage.** Sum-of-squared-differences between adjacent
rows measures roughness, and handwriting is rough at every angle — on a real page it
preferred the wrong angle by 4.82e-04 to 4.67e-04, a hair, with no sign of trouble.
Variance of the profile asks a different question — are there dense bands separated by
empty gaps? — and picked the correct angle by 2.5×.

Reports `margin`, the winner's score over the best rival more than 10° away. A low margin
means the page is genuinely ambiguous and should be reviewed.

**Limitation.** This gives the text *axis*, not which way is up. A profile is identical
upside down. See [05-training.md](05-training.md).

### Stage 2 — build energy map

`linecut/energy.py`

Runs kraken's `blla` segmentation network and takes its per-pixel baseline probability
channel. High value means "inside a text line, do not cut here".

The network:

```
input 1800px tall, variable width, 3 channels
  Conv 7x7,  64, stride 2  + GroupNorm
  Conv 3x3, 128, stride 2  + GroupNorm
  Conv 3x3, 128            + GroupNorm
  Conv 3x3, 256            + GroupNorm
  Conv 3x3, 256            + GroupNorm
  BiLSTM along x (32)
  BiLSTM along y (32)
  Conv 1x1, 32             + GroupNorm
  BiLSTM along y (32)
  BiLSTM along x (32)
  output 4 channels, sigmoid       1,261,540 parameters
```

A CNN feature extractor followed by bidirectional LSTMs along **both** axes, twice. That
2D recurrence is what lets it track a wavy baseline across a full page and know that ink
far to the left belongs to the same line. It is why this stage reads degraded manuscripts
that pure morphology cannot.

Output channels: line start separator, line end separator, baseline, text region.

Final cost is `0.8 × baseline_prob + 0.2 × ink_density`. The ink term is a weak fallback so
the page degrades gracefully rather than failing outright if the model is unavailable.

### Stage 3 — recursive seam splitting

`linecut/seams.py`

A cut is not a straight row. It enters at the left edge, leaves at the right, and may step
one pixel up or down per column — so it travels *around* descenders instead of through
them. Dynamic programming finds the globally cheapest such path in a single pass.

The recursion: project the energy within a region, find local minima, carve a seam at each
candidate, take the cheapest, split, recurse into both halves.

**Two stopping conditions, and the second is the one that matters.** Stop when the region
approaches one line pitch. *Also* stop when even the cheapest available seam costs more
than a threshold — meaning no clean cut exists, so do not force one. Without that second
condition, recursion happily shreds a single line into fragments.

Line pitch comes from the learned map: one ridge per text line, so count the ridges and
take the median spacing. An autocorrelation fallback exists but is less reliable — its
main lobe masquerades as a period and it returned 4px on a page whose real pitch was 43px.

### Stage 4 — pixel ownership

`linecut/lines.py`

Seams define bands. For each connected ink component, count its pixels per band: if 80% or
more fall in one band, the whole component belongs to that band — so a descender stays
intact with its own line. If it genuinely straddles, ownership is decided **per pixel**
along the seam.

The mask is then grown by one stroke width so anti-aliased stroke edges come along, and
everything the line does not own is replaced with white.

### Stage 5 — crop, dewarp, manifest

Each line's ink centre is measured per column, smoothed, and the columns are remapped
vertically with subpixel interpolation so a wavy manuscript line comes out level. This
matters because recognition models expect horizontal text.

The manifest records, per line: reading index, polygon on the **source** page (mapped back
through the deskew and the scale normalisation), ink pixel count, whether it was dewarped,
and three confidence signals.

## Confidence

Three signals, all falling out of stages that already run:

| signal | source | meaning when bad |
|---|---|---|
| `angle_margin` | stage 1 | page orientation is ambiguous |
| `seam_cost` | stage 3 | this cut had to pass through ink |
| `height_ratio` | stage 3 | band is off-pitch: merged, or a fragment |

A line is flagged `review: true` when the seam was expensive or the band is well off pitch.
This is how an imperfect system stays safe: it does not have to be right about everything,
it has to be honest about what it is unsure of.

## What is deliberately not here

- **No global assumption of reading direction.** Nothing assumes left-to-right.
- **No fixed thresholds in pixels.** Everything scales with measured stroke width.
- **No text/non-text classifier yet.** This is why ruled borders leak through as lines.
- **No transformer, no diffusion.** At the data scale available, a 1.3M-parameter CNN+RNN
  outperforms larger architectures, and the accuracy ceiling here is training data, not
  model capacity.
