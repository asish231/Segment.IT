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
    ap.add_argument("--ocr", action="store_true", help="run parallel Dual-OCR and export .md / .docx / .txt")
    ap.add_argument("--lang", default="en", help="target OCR language (default: en)")
    ap.add_argument("--no-llm", action="store_true", help="skip Inception Labs Mercury-2.5 intelligence correction pass")
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

        if args.ocr and m.get("lines"):
            from linecut import dual_ocr, llm_refiner
            import json
            print(f"Running Dual-OCR (PaddleOCR + TrOCR) on {len(m['lines'])} lines...")
            scanned = dual_ocr.scan_manifest_lines_parallel(m["lines"], out, lang=args.lang)
            for line_entry, ocr_result in zip(m["lines"], scanned):
                line_entry["text"] = ocr_result.get("final_text", "")
                line_entry["final_text"] = ocr_result.get("final_text", "")
                line_entry["confidence_ocr"] = ocr_result.get("confidence", 0.0)
                line_entry["dual_ocr"] = ocr_result

            doc_title = image.stem
            md_text = ""

            if not args.no_llm:
                print(f"Running Inception Labs Mercury-2.5 Intelligence Error Correction...")
                try:
                    m["lines"], md_text, llm_err = llm_refiner.refine_lines_with_llm(
                        m["lines"], doc_title=doc_title, layout=m.get("layout", "plain"), lang=args.lang
                    )
                    if llm_err:
                        print(f"  [LLM Refiner Notice]: {llm_err} (falling back to raw Dual-OCR)")
                    else:
                        print(f"  [LLM Refiner]: Mercury-2.5 reasoning refinement completed successfully!")
                except Exception as exc:
                    print(f"  [LLM Refiner Warning]: {exc} (falling back to raw Dual-OCR)")

            if not md_text:
                md_text = dual_ocr.export_markdown(m["lines"], title=doc_title)
            txt_text = dual_ocr.export_text(m["lines"])
            docx_path = out / "document.docx"
            dual_ocr.export_docx(m["lines"], docx_path, title=doc_title)

            (out / "document.md").write_text(md_text, encoding="utf-8")
            (out / "document.txt").write_text(txt_text, encoding="utf-8")
            (out / "latent.json").write_text(
                json.dumps({
                    "source": str(image),
                    "lines_found": m.get("lines_found", len(m["lines"])),
                    "deskew_deg": m.get("deskew_deg"),
                    "layout": m.get("layout"),
                    "lines": m["lines"]
                }, indent=2),
                encoding="utf-8"
            )
            print(f"Generated documents in {out}: document.md, document.docx, document.txt, latent.json")


if __name__ == "__main__":
    main()
