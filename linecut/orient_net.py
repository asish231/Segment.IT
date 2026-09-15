"""180-degree orientation classifier.

A text line and the same line turned upside down are identical to every projection
statistic, so orientation has to be learned from glyph shape. This is a small CNN over
line crops; a page is decided by averaging its lines' votes.
"""
from pathlib import Path

import cv2
import numpy as np

IN_H, IN_W = 32, 192
WEIGHTS = Path(__file__).with_name("orient_net.pt")


def _torch():
    import torch
    return torch


def build_model():
    import torch.nn as nn

    def block(cin, cout, pool=True):
        layers = [nn.Conv2d(cin, cout, 3, padding=1), nn.BatchNorm2d(cout), nn.ReLU(inplace=True)]
        if pool:
            layers.append(nn.MaxPool2d(2))
        return layers

    return nn.Sequential(
        *block(1, 32), *block(32, 64), *block(64, 128), *block(128, 128, pool=False),
        nn.AdaptiveAvgPool2d(1), nn.Flatten(),
        nn.Linear(128, 64), nn.ReLU(inplace=True), nn.Dropout(0.3), nn.Linear(64, 2),
    )


def prepare_raw(crop):
    """Line crop -> 32x192 uint8 canvas, aspect preserved and left-aligned."""
    if crop.ndim == 3:
        crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    h, w = crop.shape[:2]
    if h < 2 or w < 2:
        return None
    scale = IN_H / h
    new_w = max(8, min(int(round(w * scale)), IN_W))
    resized = cv2.resize(crop, (new_w, IN_H), interpolation=cv2.INTER_AREA)
    canvas = np.full((IN_H, IN_W), 255, np.uint8)
    canvas[:, :new_w] = resized
    return canvas


def normalise(canvas):
    arr = canvas.astype(np.float32) / 255.0
    return (arr - 0.5) / 0.5


def prepare(crop):
    """Line crop -> normalised 1x32x192 float array."""
    raw = prepare_raw(crop)
    return None if raw is None else normalise(raw)


_CACHE = {}


def load(device="cpu", path=WEIGHTS):
    key = (str(path), device)
    if key in _CACHE:
        return _CACHE[key]
    torch = _torch()
    if not Path(path).is_file():
        raise FileNotFoundError(f"no orientation weights at {path} - run train_orient.py")
    model = build_model()
    model.load_state_dict(torch.load(path, map_location=device))
    model.eval().to(device)
    _CACHE[key] = model
    return model


def flip_probability(crops, device="cpu", path=WEIGHTS, batch=64):
    """Mean probability that these line crops are upside down, plus per-line values."""
    torch = _torch()
    model = load(device=device, path=path)
    prepped = [p for p in (prepare(c) for c in crops) if p is not None]
    if not prepped:
        return 0.0, []

    probs = []
    with torch.no_grad():
        for i in range(0, len(prepped), batch):
            chunk = np.stack(prepped[i:i + batch])[:, None, :, :]
            logits = model(torch.from_numpy(chunk).to(device))
            probs.extend(torch.softmax(logits, dim=1)[:, 1].cpu().numpy().tolist())

    # weight by line width: long lines carry more glyph evidence than stray marks
    widths = np.array([c.shape[1] for c, p in zip(crops, prepped)], dtype=np.float64)[:len(probs)]
    weights = widths / widths.sum() if widths.sum() > 0 else None
    mean = float(np.average(probs, weights=weights)) if weights is not None else float(np.mean(probs))
    return mean, probs
