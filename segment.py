#!/usr/bin/env python
"""Segment document images into per-line crops.

    python segment.py IMAGE [IMAGE ...] [-o OUT] [--device mps] [--debug]

Writes OUT/<stem>/lines/line_0001.png ... plus manifest.json carrying each line's
position on the source page and its confidence signals.
"""
import argparse
from pathlib import Path

from linecut import segment_page, segment_page_instances


def main():
    ap = argparse.ArgumentParser(description="Segment document images into text lines.")
    ap.add_argument("images", nargs="+", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("output"))
    ap.add_argument("--device", default="cpu", help="cpu or mps")
    ap.add_argument("--threshold", type=float, default=0.30,
                    help="max seam cost to accept a cut; lower cuts less")
    ap.add_argument("--no-dewarp", action="store_true", help="skip per-line straightening")
    ap.add_argument("--mode", choices=["global", "instances"], default="instances",
                    help="global: one page angle plus horizontal seams. "
                         "instances: one angle and curve per detected line.")
    ap.add_argument("--debug", action="store_true", help="also write energy/seam/ownership maps")
    args = ap.parse_args()

    for image in args.images:
        out = args.out / image.stem
        if args.mode == "instances":
            m = segment_page_instances(image, out, device=args.device, debug=args.debug)
            print(f"{image.name}: {m['lines_found']} lines "
                  f"({m['lines_flagged']} flagged, {m['lines_curved']} curved)  "
                  f"deskew={m['deskew_deg']:+.1f}  spread={m['angle_spread_deg']:.1f}deg  "
                  f"pitch={m['line_pitch_px']}  {m['seconds']}s -> {out}")
        else:
            m = segment_page(image, out, device=args.device,
                             dewarp=not args.no_dewarp, threshold=args.threshold,
                             debug=args.debug)
            print(f"{image.name}: {m['lines_found']} lines "
                  f"({m['lines_flagged']} flagged)  angle={m['angle_deg']:+.1f} "
                  f"margin={m['angle_margin']}  pitch={m['line_pitch_px']}  "
                  f"stroke={m['stroke_width_px']}  {m['energy']}  {m['seconds']}s -> {out}")


if __name__ == "__main__":
    main()
