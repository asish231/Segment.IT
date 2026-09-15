# linecut — document line segmentation

Takes a photographed or scanned document page and returns each text line as a separate,
upright, background-free image, in reading order, with its position on the source page.

Built for handwritten Indic manuscripts and forms, where line spacing is irregular, pages
arrive at arbitrary rotations, and paper is degraded.

## Documents

| file | what it covers |
|---|---|
| [01-architecture.md](01-architecture.md) | The six-stage pipeline and why each stage exists |
| [02-findings.md](02-findings.md) | Measured evidence: what failed, what worked, the numbers |
| [03-datasets.md](03-datasets.md) | Datasets on hand, what they can and cannot train, licensing |
| [04-enterprise-roadmap.md](04-enterprise-roadmap.md) | Master enterprise roadmap, guardrails, and model training |

## Quick start

```bash
source venv/bin/activate

# one page
python segment.py page.png -o output --device mps

# HTTP service
uvicorn api:app --port 8000
curl -F image=@page.png -F device=mps http://localhost:8000/segment

# annotation studio
uvicorn studio:app --port 8100     # then open http://localhost:8100
```

## Current state

Measured on four representative pages:

| page | lines present | found | notes |
|---|---|---|---|
| address form, rotated 90° | 8 | 8 | correct |
| lecture notes + diagram | ~22 | 23 | correct |
| aged Devanagari letter | ~24-25 | 25 | correct (recount corrected an earlier ~28 estimate) |
| printed form, handwritten fill | ~25 | 24 | correct |

**Known defects, all open:**

1. **180° flip unresolved.** The orientation sweep finds the text axis but cannot tell
   upright from upside-down. Output may be rotated 180°. The manifest reports
   `flip_unresolved: true`.
2. **Under-segmentation on tight leading.** Aged manuscripts with interpenetrating
   vowel marks lose lines.
3. **Page furniture.** Ruled borders and table lines can be returned as text lines.

None of these are silent: every line carries confidence signals, and lines the pipeline
doubts are marked `review: true`.

## Design principle

Nothing in this pipeline assumes a document is upright, a particular resolution, a
particular script, or that text runs left to right. Every constant is derived from
measurements of the page itself — pen stroke width, line pitch, text angle — rather than
hardcoded in pixels. That is what makes it work across a phone photo of a form and a
2000px scan of a manuscript without retuning.

## Honest limits

This is not and will not be a zero-error system. Line segmentation on degraded handwriting
is an open research problem; published state of the art sits well below 100% on material
like this. The engineering answer is not to claim perfection but to make the system report
its own uncertainty, so doubtful pages route to a human instead of emitting confident
errors. See [02-findings.md](02-findings.md).
