#!/usr/bin/env python
"""Generate the segmentation viewer: one self-contained HTML page over the run output.

Scans output/ for whatever pages are there, so it always reflects the last run.
Manifest data is inlined rather than fetched, because the artifact sandbox blocks XHR.
"""
import json
import shutil
from pathlib import Path

import cv2

OUT = Path("output")
ASSETS = Path("viewer_assets")

# Friendly names for the sample pages; any other page falls back to its folder name.
LABELS = {
    "sample": "Address form",
    "image": "Lecture notes",
    "image copy": "Devanagari letter",
    "image copy 2": "Enrollment form",
}
NOTES = {
    "sample": "Photographed at 90 deg. Crops are inverted because orientation is resolved "
              "downstream by recognition confidence.",
    "image": "Bleed-through from the reverse side, plus an embedded ER diagram.",
    "image copy": "Aged paper, tight leading, interpenetrating matras.",
    "image copy 2": "Printed form with handwritten fill, table rules, low resolution.",
}


def build_assets(pages):
    ASSETS.mkdir(exist_ok=True)
    for page in pages:
        slug = page.replace(" ", "_")
        m = json.loads((OUT / page / "manifest.json").read_text())
        src = cv2.imread(m["source"])
        if src is not None:
            s = 900 / max(src.shape[:2])
            if s < 1:
                src = cv2.resize(src, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            cv2.imwrite(f"{ASSETS}/{slug}_source.jpg", src, [cv2.IMWRITE_JPEG_QUALITY, 82])
        ov = cv2.imread(str(OUT / page / "debug" / "instances.png"))
        if ov is not None:
            s = 900 / max(ov.shape[:2])
            if s < 1:
                ov = cv2.resize(ov, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            cv2.imwrite(f"{ASSETS}/{slug}_overlay.jpg", ov, [cv2.IMWRITE_JPEG_QUALITY, 82])
        re = cv2.imread(str(OUT / page / "page_reassembled.png"))
        if re is not None:
            sc = 760 / max(re.shape[1], 1)
            if sc < 1:
                re = cv2.resize(re, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
            cv2.imwrite(f"{ASSETS}/{slug}_reassembled.jpg", re, [cv2.IMWRITE_JPEG_QUALITY, 84])
        for ln in m["lines"]:
            c = cv2.imread(str(OUT / page / ln["file"]))
            if c is None:
                continue
            s = 760 / max(c.shape[1], 1)
            if s < 1:
                c = cv2.resize(c, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            cv2.imwrite(f"{ASSETS}/{slug}_line_{ln['index']:04d}.jpg", c,
                        [cv2.IMWRITE_JPEG_QUALITY, 84])


def collect(pages):
    out = {}
    for page in pages:
        slug = page.replace(" ", "_")
        m = json.loads((OUT / page / "manifest.json").read_text())
        out[slug] = {
            "label": LABELS.get(page, page),
            "note": NOTES.get(page, ""),
            "layout": m["layout"],
            "rules_h": m["rules_horizontal"],
            "rules_v": m["rules_vertical"],
            "gutters": m["column_gutters"],
            "rows": m["rows"],
            "pitch": m["line_pitch_px"],
            "stroke": m["stroke_width_px"],
            "deskew": m["deskew_deg"],
            "margin": m["deskew_margin"],
            "seconds": m["seconds"],
            "flip_unresolved": m["flip_unresolved"],
            "source_size": m["source_size"],
            "lines": [
                {
                    "i": l["index"],
                    "row": l["row"],
                    "fields": l["fields"],
                    "w": l["size"][0],
                    "h": l["size"][1],
                    "angle": l["angle_deg"],
                    "curve": l["curvature_px"],
                    "ink": l["ink_pixels"],
                    "review": l["confidence"]["review"],
                }
                for l in m["lines"]
            ],
        }
    return out


TEMPLATE = """<title>Linecut Segmentation Viewer</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
  :root {
    --ground:#f5f6f7; --panel:#ffffff; --panel2:#eceff2; --line:#d6dbe0; --line2:#c2c9d1;
    --ink:#161a1f; --ink2:#414a55; --muted:#6d7784;
    --accent:#d9531e; --accent-soft:#fbeae2;
    --ok:#1f7a52; --ok-soft:#e2f1ea; --warn:#9a6508; --warn-soft:#f8eeda;
    --mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;
    --sans:"IBM Plex Sans",system-ui,-apple-system,sans-serif;
  }
  @media (prefers-color-scheme:dark){ :root:not([data-theme="light"]){
    --ground:#101317; --panel:#171b21; --panel2:#1e242c; --line:#2a313a; --line2:#39424d;
    --ink:#e8ecf0; --ink2:#bcc5cf; --muted:#8a94a1;
    --accent:#ff7a45; --accent-soft:#2a1810;
    --ok:#5fc496; --ok-soft:#14291f; --warn:#d9a441; --warn-soft:#2a2113;
  }}
  :root[data-theme="dark"]{
    --ground:#101317; --panel:#171b21; --panel2:#1e242c; --line:#2a313a; --line2:#39424d;
    --ink:#e8ecf0; --ink2:#bcc5cf; --muted:#8a94a1;
    --accent:#ff7a45; --accent-soft:#2a1810;
    --ok:#5fc496; --ok-soft:#14291f; --warn:#d9a441; --warn-soft:#2a2113;
  }
  *{box-sizing:border-box}
  body{background:var(--ground);color:var(--ink);font-family:var(--sans);font-size:14px;line-height:1.55}
  .wrap{max-width:1240px;margin:0 auto;padding-inline:20px;padding-block:32px 72px}

  header{border-bottom:2px solid var(--ink);padding-bottom:20px}
  .eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.13em;text-transform:uppercase;color:var(--muted)}
  h1{font-size:clamp(24px,4vw,36px);margin:8px 0 0;letter-spacing:-.02em;font-weight:600;text-wrap:balance}
  .sub{color:var(--ink2);margin:10px 0 0;max-width:62ch}

  .tabs{display:flex;gap:6px;flex-wrap:wrap;margin-top:24px}
  .tab{background:var(--panel2);border:1px solid var(--line);color:var(--ink2);border-radius:6px;
       padding:9px 14px;font:500 13px var(--sans);cursor:pointer}
  .tab:hover{border-color:var(--line2)}
  .tab.on{background:var(--accent);border-color:var(--accent);color:#fff}

  .note{margin-top:20px;padding:12px 15px;border-left:3px solid var(--accent);
        background:var(--accent-soft);color:var(--ink2);font-size:13.5px}

  .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(112px,1fr));gap:1px;
         background:var(--line);border:1px solid var(--line);margin-top:20px}
  .stat{background:var(--panel);padding:11px 13px}
  .stat dt{font-family:var(--mono);font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
  .stat dd{margin:3px 0 0;font:600 17px var(--mono);font-variant-numeric:tabular-nums}
  .stat dd.ok{color:var(--ok)} .stat dd.warn{color:var(--warn)}

  h2{font-size:17px;margin:36px 0 12px;font-weight:600;letter-spacing:-.01em}
  .views{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
  figure{margin:0;background:var(--panel);border:1px solid var(--line);padding:10px}
  figure img{display:block;width:100%;height:auto;background:#fff}
  figcaption{font-family:var(--mono);font-size:11px;color:var(--muted);margin-top:8px}

  .lines{display:flex;flex-direction:column;gap:1px;background:var(--line);
         border:1px solid var(--line);margin-top:12px}
  .ln{background:var(--panel);display:grid;grid-template-columns:52px 1fr 190px;
      gap:14px;padding:10px 12px;align-items:center}
  .ln:hover{background:var(--panel2)}
  .idx{font:600 13px var(--mono);color:var(--accent);font-variant-numeric:tabular-nums}
  .idx small{display:block;color:var(--muted);font-weight:400;font-size:10px}
  .strip{overflow-x:auto}
  .strip img{display:block;max-width:100%;height:auto;background:#fff;border:1px solid var(--line)}
  .meta{font-family:var(--mono);font-size:10.5px;color:var(--muted);line-height:1.75;text-align:right}
  .pill{display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;font-weight:600}
  .pill.rev{background:var(--warn-soft);color:var(--warn)}
  .pill.f{background:var(--ok-soft);color:var(--ok)}

  footer{margin-top:52px;padding-top:18px;border-top:1px solid var(--line);
         font-family:var(--mono);font-size:11.5px;color:var(--muted)}
  @media(max-width:1000px){ .views{grid-template-columns:1fr 1fr} }
  @media(max-width:820px){ .views{grid-template-columns:1fr} .ln{grid-template-columns:44px 1fr}
    .meta{grid-column:1/-1;text-align:left} }
</style>

<div class="wrap">
  <header>
    <div class="eyebrow">linecut &middot; segmentation output</div>
    <h1>Segmentation Viewer</h1>
    <p class="sub">Every page below was processed by one command with default settings. Left is
    what went in, right is what the segmenter found, and beneath that is every line it cut out,
    in reading order.</p>
  </header>

  <div class="tabs" id="tabs"></div>
  <div class="note" id="note"></div>
  <dl class="stats" id="stats"></dl>

  <h2>Input, detection, and reassembly</h2>
  <div class="views">
    <figure><img id="src" alt="Source page"><figcaption id="srccap"></figcaption></figure>
    <figure><img id="ovl" alt="Detected lines"><figcaption>Detected spines (orange) and line boundaries (green).</figcaption></figure>
    <figure><img id="rea" alt="Reassembled page"><figcaption>Every extracted line stacked back in order &mdash; a cleaned, deskewed page, and a check that nothing was lost or duplicated.</figcaption></figure>
  </div>

  <h2 id="lines-h">Extracted lines</h2>
  <div class="lines" id="lines"></div>

  <footer id="foot"></footer>
</div>

<script>
const DATA = __DATA__;
const $ = id => document.getElementById(id);
let current = Object.keys(DATA)[0];

function render(slug){
  current = slug;
  const d = DATA[slug];

  $('tabs').innerHTML = Object.entries(DATA).map(([k,v]) =>
    `<button class="tab${k===slug?' on':''}" data-k="${k}">${v.label}</button>`).join('');
  $('tabs').querySelectorAll('.tab').forEach(b => b.onclick = () => render(b.dataset.k));

  $('note').textContent = d.note;

  const multi = d.lines.filter(l => l.fields.length > 1).length;
  const flagged = d.lines.filter(l => l.review).length;
  const stats = [
    ['lines found', d.lines.length, ''],
    ['layout', d.layout, ''],
    ['rows', d.rows, ''],
    ['h-rules', d.rules_h, ''],
    ['v-rules', d.rules_v, ''],
    ['multi-field', multi, multi ? 'ok' : ''],
    ['flagged', flagged, flagged ? 'warn' : 'ok'],
    ['deskew', d.deskew + '\\u00b0', ''],
    ['seconds', d.seconds, ''],
  ];
  $('stats').innerHTML = stats.map(([k,v,c]) =>
    `<div class="stat"><dt>${k}</dt><dd class="${c}">${v}</dd></div>`).join('');

  $('src').src = slug + '_source.jpg';
  $('ovl').src = slug + '_overlay.jpg';
  $('rea').src = slug + '_reassembled.jpg';
  $('srccap').textContent = `Source, ${d.source_size[0]} x ${d.source_size[1]} px. Stroke ${d.stroke}px, pitch ${d.pitch}px.`;

  $('lines-h').textContent = `Extracted lines (${d.lines.length})`;
  $('lines').innerHTML = d.lines.map(l => {
    const f = l.fields.length > 1 ? `<span class="pill f">${l.fields.length} fields</span>` : '';
    const r = l.review ? '<span class="pill rev">review</span>' : '';
    const pad = String(l.i).padStart(4,'0');
    return `<div class="ln">
      <div class="idx">${l.i}<small>row ${l.row}</small></div>
      <div class="strip"><img loading="lazy" src="${slug}_line_${pad}.jpg" alt="Line ${l.i}"></div>
      <div class="meta">${l.w}\\u00d7${l.h}px &middot; ${l.ink} ink<br>
        ${l.angle}\\u00b0 &middot; curve ${l.curve}px<br>${f} ${r}</div>
    </div>`;
  }).join('');

  $('foot').textContent = d.flip_unresolved
    ? 'Orientation note: flip is unresolved by design. If recognition finds a page inverted, rotate each crop 180 degrees and reverse the line order.'
    : '';
}
render(current);
</script>
"""


def main():
    pages = sorted(d.name for d in OUT.iterdir()
                   if d.is_dir() and (d / "manifest.json").is_file())
    if not pages:
        raise SystemExit("no pages in output/ - run segment.py first")
    if ASSETS.exists():
        shutil.rmtree(ASSETS)
    build_assets(pages)
    data = collect(pages)
    html = TEMPLATE.replace("__DATA__", json.dumps(data, separators=(",", ":")))
    (ASSETS / "viewer.html").write_text(html)
    print(f"viewer built for {len(pages)} page(s): {', '.join(pages)}")


if __name__ == "__main__":
    main()
