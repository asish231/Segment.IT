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
    ap.add_argument("--no-tables", action="store_true", help="skip 2D table grid extraction and land record compilation")
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

        if not args.no_tables:
            import cv2
            from linecut import table_extractor, land_records
            print(f"\n[Tier 1: Table Extraction] Detecting 2D tables and cell grids for {image.name}...")
            src_img = cv2.imread(str(image))
            if src_img is not None:
                detected_tables = table_extractor.extract_all_tables(src_img)
                print(f"  Detected {len(detected_tables)} table(s) across document.")
                for t in detected_tables:
                    print(f"    Table {t['table_id']}: {t['rows_count']} rows x {t['cols_count']} cols ({t['cells_count']} cells)")

                if args.ocr and detected_tables:
                    from linecut import dual_ocr
                    print(f"  Scanning table cells with Dual-OCR (lang={args.lang})...")
                    detected_tables = dual_ocr.scan_table_cells_parallel(detected_tables, src_img, lang=args.lang)

                    l_rec = land_records.build_structured_land_record(detected_tables, m.get("lines", []))

                    if not args.no_llm:
                        from linecut import llm_refiner
                        try:
                            all_tbl_md = "\n\n".join(t.get("markdown", "") for t in detected_tables if t.get("markdown"))
                            refined_rec, refined_tbl_md, _ = llm_refiner.refine_land_record_with_llm(
                                l_rec, all_tbl_md, doc_title=image.stem
                            )
                            if refined_rec:
                                l_rec = refined_rec
                        except Exception:
                            pass

                    # Re-export unified document (prose + tables interleaved in true reading order)
                    md_text = dual_ocr.export_markdown(m["lines"], tables=detected_tables, title=doc_title)
                    txt_text = dual_ocr.export_text(m["lines"], tables=detected_tables)
                    dual_ocr.export_docx(m["lines"], docx_path, tables=detected_tables, title=doc_title)
                    (out / "document.md").write_text(md_text, encoding="utf-8")
                    (out / "document.txt").write_text(txt_text, encoding="utf-8")

                    # Write land_record.json and table markdown
                    (out / "land_record.json").write_text(json.dumps(l_rec, indent=2, ensure_ascii=False), encoding="utf-8")
                    all_md_tables = "\n\n".join(f"### Table {t['table_id']}\n\n{t.get('markdown', '')}" for t in detected_tables)
                    (out / "tables.md").write_text(all_md_tables, encoding="utf-8")

                    print(f"\n[MoRD / DoLR Land Record Compilation]")
                    print(f"  State: {l_rec.get('metadata', {}).get('state', 'Unknown')}, District: {l_rec.get('metadata', {}).get('district', 'Unknown')}, Village: {l_rec.get('metadata', {}).get('village', 'Unknown')}")
                    print(f"  Plots: {len(l_rec.get('plots', []))} plot(s) extracted.")
                    print(f"  Owners: {len(l_rec.get('owners', []))} owner(s) extracted.")
                    print(f"  Mutations: {len(l_rec.get('mutations', []))} mutation record(s) extracted.")
                    val = l_rec.get("validation", {})
                    status_str = "PASSED" if val.get("validation_passed") else "REVIEW REQUIRED"
                    print(f"  Automated Validation: [{status_str}] ({val.get('rules_passed', 0)} passed, {val.get('rules_failed', 0)} failed)")
                    for chk in val.get("checks", []):
                        print(f"    - {chk.get('rule')}: [{chk.get('status').upper()}] {chk.get('message')}")
                    print(f"  Saved: {out}/land_record.json and {out}/tables.md")


if __name__ == "__main__":
    main()
