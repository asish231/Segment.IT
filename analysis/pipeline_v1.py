"""Stage-by-stage line segmentation with FULL 180-degree orientation search."""
import cv2
import numpy as np
from pathlib import Path

SRC = Path("/Users/asishsharma/ocr/sample.png")
OUT = Path("/private/tmp/claude-501/-Users-asishsharma-ocr/822022fa-6644-4c21-b80b-668c40f4f47b/scratchpad/stages2")
OUT.mkdir(parents=True, exist_ok=True)

def save(name, im):
    cv2.imwrite(str(OUT / name), im)
    print("wrote", name, im.shape)

img = cv2.imread(str(SRC))
h, w = img.shape[:2]
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# ink map -> binary (same as before; this part worked fine)
bg = cv2.medianBlur(gray, 51)
ink = cv2.subtract(bg, gray)
_, binary = cv2.threshold(ink, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
binary = cv2.medianBlur(binary, 3)

n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
keep = np.zeros(n, bool)
for i in range(1, n):
    a = stats[i, cv2.CC_STAT_AREA]
    cw, ch = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
    if a >= 20 and cw < w * 0.9 and ch < h * 0.5:
        keep[i] = True
clean = np.where(keep[labels], 255, 0).astype(np.uint8)
save("01_binary_clean.png", clean)
print("components kept:", keep.sum())


def rot_mat(shape, ang):
    """Rotation that expands the canvas so nothing gets clipped."""
    hh, ww = shape[:2]
    c = (ww / 2, hh / 2)
    M = cv2.getRotationMatrix2D(c, ang, 1.0)
    cos, sin = abs(M[0, 0]), abs(M[0, 1])
    nw, nh = int(hh * sin + ww * cos), int(hh * cos + ww * sin)
    M[0, 2] += nw / 2 - c[0]
    M[1, 2] += nh / 2 - c[1]
    return M, (nw, nh)


def rotate(im, ang, flags=cv2.INTER_NEAREST):
    M, size = rot_mat(im.shape, ang)
    return cv2.warpAffine(im, M, size, flags=flags)


def peakiness(im, ang):
    """How cleanly do text lines stack when we rotate by `ang`?

    Variance of the row-ink profile, not roughness: strokes are rough at every
    angle, but only at the true text angle do you get dense bands separated by
    empty gaps.
    """
    r = rotate(im, ang)
    prof = r.sum(axis=1).astype(np.float64)
    if prof.sum() == 0:
        return 0.0
    prof = prof / prof.sum()
    return float(prof.var())


small = cv2.resize(clean, None, fx=0.4, fy=0.4, interpolation=cv2.INTER_NEAREST)

# --- coarse sweep over the WHOLE circle of possible text directions ---
coarse = np.arange(-90, 90, 1.0)
cs = np.array([peakiness(small, a) for a in coarse])
c_best = float(coarse[cs.argmax()])

# --- fine refine around the winner ---
fine = np.arange(c_best - 2, c_best + 2.01, 0.2)
fs = np.array([peakiness(small, a) for a in fine])
best = float(fine[fs.argmax()])
print("coarse best:", c_best, "-> refined:", best)

# plot the sweep
plot = np.full((340, len(coarse) * 5, 3), 255, np.uint8)
s = (cs - cs.min()) / (cs.max() - cs.min())
for i in range(len(coarse) - 1):
    cv2.line(plot, (i * 5, 320 - int(s[i] * 280)), ((i + 1) * 5, 320 - int(s[i + 1] * 280)), (200, 60, 60), 2)
bi = int(cs.argmax())
cv2.line(plot, (bi * 5, 0), (bi * 5, 340), (0, 170, 0), 2)
cv2.putText(plot, f"peak = {best:+.1f} deg", (bi * 5 - 250, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 130, 0), 2)
for tick in (-90, -45, 0, 45):
    xi = int((tick + 90) / 1.0) * 5
    cv2.line(plot, (xi, 320), (xi, 335), (0, 0, 0), 1)
    cv2.putText(plot, str(tick), (xi + 3, 334), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
save("02_angle_sweep_180.png", plot)

# --- deskew using the real angle ---
desk = rotate(clean, best)
desk_color = rotate(img, best, flags=cv2.INTER_LINEAR)
save("03_deskewed.png", desk)
save("03b_deskewed_color.png", desk_color)
dh, dw = desk.shape[:2]

# --- projection profile now that lines are horizontal ---
def profile_img(im, title):
    prof = im.sum(axis=1).astype(np.float64)
    prof = prof / (prof.max() + 1e-9)
    canvas = np.full((im.shape[0], 430, 3), 255, np.uint8)
    for y, v in enumerate(prof):
        cv2.line(canvas, (0, y), (int(v * 400), y), (190, 90, 40), 1)
    cv2.putText(canvas, title, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    return canvas

save("04_profile_after.png", profile_img(desk, "row ink profile (deskewed)"))

# --- glue strokes sideways into lines ---
ksize = max(21, int(dw * 0.04))
merged = cv2.dilate(desk, cv2.getStructuringElement(cv2.MORPH_RECT, (ksize, 3)), iterations=2)
merged = cv2.morphologyEx(merged, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (ksize, 7)))
save("05_merged_lines.png", merged)

# --- one box per line ---
cnts, _ = cv2.findContours(merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
rects = [cv2.boundingRect(c) for c in cnts if cv2.contourArea(c) > 500]
rects.sort(key=lambda r: r[1])
print("line boxes:", len(rects))

vis = cv2.cvtColor(desk, cv2.COLOR_GRAY2BGR)
vis = cv2.addWeighted(desk_color, 0.85, vis, 0.15, 0)
for i, (x, y, rw, rh) in enumerate(rects, 1):
    cv2.rectangle(vis, (x, y), (x + rw, y + rh), (0, 0, 255), 3)
    cv2.putText(vis, str(i), (max(x - 45, 5), y + rh), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 0, 0), 3)
save("06_line_boxes.png", vis)

# --- map boxes back onto the ORIGINAL page, to prove the geometry round-trips ---
M, _ = rot_mat(img.shape, best)
Minv = cv2.invertAffineTransform(M)
orig_vis = img.copy()
for i, (x, y, rw, rh) in enumerate(rects, 1):
    pts = np.array([[x, y], [x + rw, y], [x + rw, y + rh], [x, y + rh]], np.float32)
    back = (Minv @ np.hstack([pts, np.ones((4, 1), np.float32)]).T).T
    cv2.polylines(orig_vis, [back.astype(np.int32)], True, (0, 0, 255), 3)
    cv2.putText(orig_vis, str(i), tuple(back[0].astype(int)), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 0), 3)
save("07_boxes_on_original.png", orig_vis)

# --- final crops, upright and OCR-ready ---
crops = OUT / "crops"
crops.mkdir(exist_ok=True)
strip = []
for i, (x, y, rw, rh) in enumerate(rects, 1):
    pad = 10
    x0, y0 = max(x - pad, 0), max(y - pad, 0)
    x1, y1 = min(x + rw + pad, dw), min(y + rh + pad, dh)
    crop = desk_color[y0:y1, x0:x1]
    cv2.imwrite(str(crops / f"line_{i:02d}.png"), crop)
    strip.append(crop)

if strip:
    cw = max(c.shape[1] for c in strip)
    rows = []
    for c in strip:
        rows.append(cv2.copyMakeBorder(c, 5, 5, 0, cw - c.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255)))
        rows.append(np.zeros((3, cw, 3), np.uint8))
    save("08_crops_stacked.png", np.vstack(rows))
print("crops:", len(strip))
