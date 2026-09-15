#!/usr/bin/env python
"""Train the 180-degree flip classifier that completes orientation handling.

The variance sweep in linecut/core.py resolves the text axis but not which way is up,
because a projection profile is identical upside down. This learns that from glyph shape.

Labels are free: a rendered line is upright, its 180-degree rotation is not. Text comes
from the Aksharantar corpus (real words, 20 Indic scripts) plus an English word list,
rendered in system fonts and degraded to resemble photographed paper.

No real line crop is ever trained on - all of them are held out as the test set.

    python train_orient.py --device mps --epochs 14
"""
import argparse
import glob
import json
import os
import random
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from linecut.orient_net import IN_H, IN_W, build_model, normalise, prepare_raw

FONT_DIRS = ["/System/Library/Fonts/Supplemental", "/System/Library/Fonts", "/Library/Fonts"]
PRIVATE_USE = ""  # no font defines this, so it renders as the missing-glyph box


def font_files():
    out = []
    for d in FONT_DIRS:
        for pattern in ("*.ttf", "*.ttc", "*.otf"):
            out.extend(glob.glob(os.path.join(d, pattern)))
    skip = ("emoji", "braille", "symbol", "dingbat", "webding", "wingding", "logo", "apple color")
    return sorted(p for p in set(out) if not any(s in os.path.basename(p).lower() for s in skip))


def _open_font(path, size, index=0):
    try:
        return ImageFont.truetype(path, size, index=index)
    except Exception:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            return None


def _glyph(font, ch):
    img = Image.new("L", (90, 90), 255)
    ImageDraw.Draw(img).text((6, 6), ch, font=font, fill=0)
    return np.asarray(img)


def supports(font, sample):
    """True if the font draws real glyphs rather than the missing-glyph box."""
    ref = _glyph(font, PRIVATE_USE)
    checked = 0
    for ch in sample:
        if ch.isspace():
            continue
        if not np.array_equal(_glyph(font, ch), ref):
            return True
        checked += 1
        if checked >= 6:
            break
    return False


def load_corpus(corpus_dir="corpus/data", per_lang=4000):
    """{language: [words]} from the Aksharantar validation splits."""
    langs = {}
    for path in sorted(glob.glob(f"{corpus_dir}/*/*_valid.json")):
        lang = os.path.basename(path).split("_")[0]
        words = set()
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    w = json.loads(line).get("native word", "").strip()
                except Exception:
                    continue
                if 1 < len(w) < 24:
                    words.add(w)
                if len(words) >= per_lang:
                    break
        if len(words) > 200:
            langs[lang] = sorted(words)

    eng = Path("/usr/share/dict/words")
    if eng.is_file():
        langs["eng"] = [w.strip() for w in eng.read_text(errors="ignore").splitlines()
                        if 2 < len(w.strip()) < 14][:40000]
    return langs


def pair_fonts_to_languages(langs, verbose=True):
    """Auto-discover which installed fonts can actually render each script."""
    pairs = {}
    files = font_files()
    for lang, words in langs.items():
        sample = "".join(words[i] for i in range(0, min(len(words), 40), 8))
        usable = []
        for path in files:
            font = _open_font(path, 28)
            if font is None:
                continue
            try:
                if supports(font, sample):
                    usable.append(path)
            except Exception:
                continue
        if usable:
            pairs[lang] = usable
        if verbose:
            print(f"  {lang:5s} {len(words):6d} words  {len(usable):3d} fonts")
    return pairs


def render_line(rng, font_paths, words):
    path = rng.choice(font_paths)
    size = rng.randint(20, 44)
    index = rng.randint(0, 1) if path.endswith(".ttc") else 0
    font = _open_font(path, size, index)
    if font is None:
        return None

    text = " ".join(rng.choice(words) for _ in range(rng.randint(2, 8)))
    if rng.random() < 0.15:
        text = text.upper()

    width = min(6000, 80 + int(len(text) * size * 1.4))
    img = Image.new("L", (width, size * 5), 255)
    try:
        ImageDraw.Draw(img).text((30, size), text, font=font, fill=rng.randint(0, 80))
        box = img.getbbox()
    except Exception:
        return None
    if box is None:
        return None

    pad = max(3, size // 6)
    x0 = max(box[0] - pad, 0)
    y0 = max(box[1] - pad, 0)
    x1 = min(box[2] + pad, img.width)
    y1 = min(box[3] + pad, img.height)
    crop = np.asarray(img.crop((x0, y0, x1, y1)))
    if crop.shape[0] < 10 or crop.shape[1] < 30:
        return None
    return crop


def degrade(img, rng):
    """Make a clean render look like ink on photographed paper."""
    out = img.astype(np.float32)
    if rng.random() < 0.5:
        out = cv2.GaussianBlur(out, (rng.choice([3, 5]), rng.choice([3, 5])), 0)
    if rng.random() < 0.4:
        op = cv2.MORPH_ERODE if rng.random() < 0.5 else cv2.MORPH_DILATE
        out = cv2.morphologyEx(out, op, np.ones((2, 2), np.uint8))
    if rng.random() < 0.4:
        h, w = out.shape
        M = cv2.getRotationMatrix2D((w / 2, h / 2), rng.uniform(-3, 3), 1.0)
        out = cv2.warpAffine(out, M, (w, h), borderValue=255)
    if rng.random() < 0.6:
        out = out * rng.uniform(0.7, 1.0) + rng.uniform(0, 50)
    if rng.random() < 0.5:
        w = out.shape[1]
        grad = np.linspace(rng.uniform(-30, 0), rng.uniform(0, 30), w, dtype=np.float32)
        out = out + grad[None, :]
    if rng.random() < 0.75:
        out = out + np.random.normal(0, rng.uniform(2, 16), out.shape).astype(np.float32)
    if rng.random() < 0.35:
        f = rng.uniform(0.4, 0.85)
        small = cv2.resize(out, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
        out = cv2.resize(small, (out.shape[1], out.shape[0]), interpolation=cv2.INTER_LINEAR)
    return np.clip(out, 0, 255).astype(np.uint8)


def synth(n, pairs, langs, seed=0):
    rng = random.Random(seed)
    np.random.seed(seed)
    names = sorted(pairs)
    xs, ys = [], []
    attempts = 0
    while len(xs) < n * 2 and attempts < n * 12:
        attempts += 1
        lang = rng.choice(names)
        line = render_line(rng, pairs[lang], langs[lang])
        if line is None:
            continue
        line = degrade(line, rng)
        for img, label in ((line, 0), (cv2.rotate(line, cv2.ROTATE_180), 1)):
            raw = prepare_raw(img)
            if raw is not None:
                xs.append(raw)
                ys.append(label)
    return np.stack(xs), np.array(ys, np.int64)


def real_crops(upright_globs, flipped_globs):
    """Held-out test set built from actual pipeline output."""
    xs, ys, src = [], [], []
    todo = [(g, 0) for g in upright_globs] + [(g, 1) for g in flipped_globs]
    for pattern, base in todo:
        for f in sorted(glob.glob(pattern)):
            img = cv2.imread(f, cv2.IMREAD_GRAYSCALE)
            if img is None or img.shape[0] < 8 or img.shape[1] < 30:
                continue
            for variant, label in ((img, base), (cv2.rotate(img, cv2.ROTATE_180), 1 - base)):
                raw = prepare_raw(variant)
                if raw is not None:
                    xs.append(raw)
                    ys.append(label)
                    src.append(Path(f).parent.parent.name)
    if not xs:
        return None, None, None
    return np.stack(xs), np.array(ys, np.int64), np.array(src)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=6000)
    ap.add_argument("--epochs", type=int, default=14)
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--device", default="mps")
    ap.add_argument("--out", type=Path, default=Path("linecut/orient_net.pt"))
    args = ap.parse_args()

    import torch
    import torch.nn as nn

    print("corpus:")
    langs = load_corpus()
    pairs = pair_fonts_to_languages(langs)
    print(f"scripts renderable: {len(pairs)}")

    print("synthesising ...")
    xtr, ytr = synth(args.samples, pairs, langs, seed=1)
    xva, yva = synth(max(500, args.samples // 12), pairs, langs, seed=77)
    xte, yte, ste = real_crops(
        upright_globs=["output/image/lines/*.png", "output/image copy/lines/*.png",
                       "output/image copy 2/lines/*.png"],
        flipped_globs=["output/sample/lines/*.png"],
    )
    print(f"train {len(xtr)} | synth-val {len(xva)} | real held-out {0 if xte is None else len(xte)}")

    dev = torch.device(args.device)
    model = build_model().to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    steps = args.epochs * max(1, len(xtr) // args.batch)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=steps)
    lossf = nn.CrossEntropyLoss()

    def accuracy(x, y):
        if x is None:
            return float("nan"), None
        model.eval()
        preds = []
        with torch.no_grad():
            for i in range(0, len(x), 256):
                xb = torch.from_numpy(normalise(x[i:i + 256]))[:, None].to(dev)
                preds.append(model(xb).argmax(1).cpu().numpy())
        preds = np.concatenate(preds)
        return float((preds == y).mean()), preds

    for epoch in range(1, args.epochs + 1):
        model.train()
        order = np.random.permutation(len(xtr))
        running = 0.0
        for i in range(0, len(order) - args.batch + 1, args.batch):
            idx = order[i:i + args.batch]
            xb = torch.from_numpy(normalise(xtr[idx]))[:, None].to(dev)
            yb = torch.from_numpy(ytr[idx]).to(dev)
            opt.zero_grad()
            loss = lossf(model(xb), yb)
            loss.backward()
            opt.step()
            if sched.last_epoch < steps - 1:
                sched.step()
            running += float(loss.detach()) * len(idx)
        va, _ = accuracy(xva, yva)
        te, _ = accuracy(xte, yte)
        print(f"epoch {epoch:2d}  loss={running/len(order):.4f}  synth_val={va:.4f}  real_test={te:.4f}")

    te, preds = accuracy(xte, yte)
    if preds is not None:
        print("\nper-page accuracy on held-out real crops:")
        for page in sorted(set(ste)):
            m = ste == page
            print(f"  {page:16s} {int(m.sum()):4d} crops  {float((preds[m]==yte[m]).mean()):.4f}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), args.out)
    print(f"\nsaved {args.out}")


if __name__ == "__main__":
    main()
