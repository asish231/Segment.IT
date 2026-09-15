"""Stage 2: the cut-cost map.

High value means "this pixel is inside a text line, do not cut here". The learned
baseline map carries the decision; ink density is a weak fallback so the page still
degrades gracefully if the model is unavailable or unsure.
"""
import cv2
import numpy as np
from PIL import Image

_MODEL = None


def _load_model():
    global _MODEL
    if _MODEL is None:
        from importlib import resources
        from kraken.lib import vgsl
        _MODEL = vgsl.TorchVGSLModel.load_model(resources.files("kraken").joinpath("blla.mlmodel"))
    return _MODEL


def baseline_map(bgr, device="cpu"):
    """Per-pixel probability that a pixel sits on a text line, from kraken's segmenter."""
    import kraken.blla as blla

    pil = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    res = blla.compute_segmentation_map(pil, model=_load_model(), device=device)
    heat, cls_map = res["heatmap"], res["cls_map"]

    idx = cls_map["baselines"]["default"]
    prob = np.asarray(heat[idx], dtype=np.float32)
    if prob.shape != bgr.shape[:2]:
        prob = cv2.resize(prob, (bgr.shape[1], bgr.shape[0]), interpolation=cv2.INTER_LINEAR)
    return prob


def ink_energy(binary, stroke=3.0):
    """Blurred ink density, normalised to 0..1."""
    k = max(3, int(stroke * 2) | 1)
    dens = cv2.GaussianBlur(binary.astype(np.float32) / 255.0, (k, k), 0)
    peak = dens.max()
    return dens / peak if peak > 0 else dens


def build(bgr, binary, stroke=3.0, device="cpu", w_learned=0.8, w_ink=0.2):
    """Combined cut-cost map plus the baseline probability on its own.

    The baseline map is dilated vertically by roughly one stroke so a seam is
    penalised for grazing a line's edge, not only its centre.
    """
    ink = ink_energy(binary, stroke)
    try:
        prob = baseline_map(bgr, device=device)
        k = max(3, int(stroke * 1.5) | 1)
        spread = cv2.dilate(prob, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, k)))
        cost = w_learned * spread + w_ink * ink
        return cost.astype(np.float32), prob
    except Exception:
        return ink.astype(np.float32), None
