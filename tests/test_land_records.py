"""Comprehensive automated test suite for MoRD / DoLR Land Record Digitization & Validation.

Covers:
1. Validation Engine: Area Invariants, Ownership Share Balance, Khasra Number Validation.
2. Land Record Schema Compiler: Canonical DoLR-DILRMP-v2.0 schema structure, header detection.
3. 2D Table & Cell Extractor: Coordinate isolation, grid clustering, margin trimming.
4. FastAPI Integration: End-to-end endpoint verification for /segment and /jobs/{job_id}/land_record.json.
"""

import json
import unittest
import numpy as np
import cv2
from pathlib import Path

from linecut import validation, land_records, table_extractor
from fastapi.testclient import TestClient
from api import app


class TestLandRecordValidation(unittest.TestCase):
    """Tests for linecut.validation business rules."""

    def test_area_balance_exact_match(self):
        plots = [
            {"khasra_no": "101/1", "area": "1.5000", "area_numeric": 1.5},
            {"khasra_no": "101/2", "area": "0.5000", "area_numeric": 0.5},
            {"khasra_no": "102", "area": "2.0000", "area_numeric": 2.0},
        ]
        res = validation.validate_area_balance(plots, reported_total="4.0000")
        self.assertEqual(res["status"], "passed")
        self.assertAlmostEqual(res["computed_total"], 4.0)
        self.assertAlmostEqual(res["reported_total"], 4.0)

    def test_area_balance_mismatch(self):
        plots = [
            {"khasra_no": "101/1", "area": "1.5000", "area_numeric": 1.5},
            {"khasra_no": "101/2", "area": "0.5000", "area_numeric": 0.5},
        ]
        res = validation.validate_area_balance(plots, reported_total="3.0000")
        self.assertEqual(res["status"], "failed")
        self.assertAlmostEqual(res["discrepancy"], 1.0)
        self.assertIn("mismatch", res["message"].lower())

    def test_area_balance_no_reported(self):
        plots = [
            {"khasra_no": "127", "area": "0.1000", "area_numeric": 0.1},
        ]
        res = validation.validate_area_balance(plots, reported_total=None)
        self.assertEqual(res["status"], "info")
        self.assertAlmostEqual(res["computed_total"], 0.1)

    def test_ownership_shares_perfect_sum(self):
        owners = [
            {"name": "Ramesh Kumar", "share": "1/2"},
            {"name": "Suresh Kumar", "share": "1/2"},
        ]
        res = validation.validate_ownership_shares(owners)
        self.assertEqual(res["status"], "passed")
        self.assertAlmostEqual(res["computed_sum"], 1.0)

    def test_ownership_shares_decimal_percentages(self):
        owners = [
            {"name": "Owner A", "share": "60%"},
            {"name": "Owner B", "share": "40%"},
        ]
        res = validation.validate_ownership_shares(owners)
        self.assertEqual(res["status"], "passed")
        self.assertAlmostEqual(res["computed_sum"], 1.0)

    def test_ownership_shares_mismatch(self):
        owners = [
            {"name": "Owner A", "share": "1/3"},
            {"name": "Owner B", "share": "1/3"},
        ]
        res = validation.validate_ownership_shares(owners)
        self.assertEqual(res["status"], "failed")
        self.assertIn("discrepancy", res["message"].lower())

    def test_khasra_numbers_valid(self):
        plots = [
            {"khasra_no": "127"},
            {"khasra_no": "128/1"},
            {"khasra_no": "128/2-A"},
        ]
        res = validation.validate_khasra_numbers(plots)
        self.assertEqual(res["status"], "passed")
        self.assertEqual(len(res["invalid_format"]), 0)
        self.assertEqual(len(res["duplicates"]), 0)

    def test_khasra_numbers_duplicates(self):
        plots = [
            {"khasra_no": "127"},
            {"khasra_no": "127"},
        ]
        res = validation.validate_khasra_numbers(plots)
        self.assertEqual(res["status"], "failed")
        self.assertIn("127", res["duplicates"])

    def test_run_full_validation_workflow(self):
        rec = {
            "plots": [{"khasra_no": "104/1", "area": "2.5", "area_numeric": 2.5}],
            "owners": [{"name": "Rajesh Sharma", "share": "1.0"}],
            "reported_total_area": "2.5",
        }
        val = validation.run_full_validation(rec)
        self.assertTrue(val["validation_passed"])
        self.assertFalse(val["review_required"])
        self.assertEqual(val["rules_passed"], 3)


class TestTableExtractor(unittest.TestCase):
    """Tests for 2D table detection and grid cell extraction."""

    def setUp(self):
        # Create a synthetic image with a 3x3 table grid
        self.img = np.full((300, 400, 3), 255, dtype=np.uint8)
        # Draw outer rectangle
        cv2.rectangle(self.img, (50, 50), (350, 250), (0, 0, 0), 2)
        # Draw 2 horizontal lines
        cv2.line(self.img, (50, 116), (350, 116), (0, 0, 0), 2)
        cv2.line(self.img, (50, 183), (350, 183), (0, 0, 0), 2)
        # Draw 2 vertical lines
        cv2.line(self.img, (150, 50), (150, 250), (0, 0, 0), 2)
        cv2.line(self.img, (250, 50), (250, 250), (0, 0, 0), 2)

    def test_detect_tables(self):
        tables_list, table_grid, h_lines, v_lines = table_extractor.detect_tables(self.img)
        self.assertGreaterEqual(len(tables_list), 1)
        t = tables_list[0]
        self.assertIn("bbox", t)
        # Check reasonable bbox bounds
        x, y, w, h = t["bbox"]
        self.assertAlmostEqual(x, 50, delta=10)
        self.assertAlmostEqual(y, 50, delta=10)

    def test_extract_table_cells(self):
        tables_list, table_grid, h_lines, v_lines = table_extractor.detect_tables(self.img)
        t = tables_list[0]
        cells = table_extractor.extract_table_cells(table_grid, t["bbox"])
        # Should detect interior cells for a 3x3 grid
        self.assertGreaterEqual(len(cells), 4)

    def test_cluster_cells_into_grid(self):
        tables_list, table_grid, h_lines, v_lines = table_extractor.detect_tables(self.img)
        t = tables_list[0]
        cells = table_extractor.extract_table_cells(table_grid, t["bbox"])
        grid = table_extractor.cluster_cells_into_grid(cells)
        self.assertGreaterEqual(len(grid), 4)
        self.assertTrue(all("row_idx" in c and "col_idx" in c for c in grid))


class TestLandRecordSchemaCompiler(unittest.TestCase):
    """Tests for compiling tables into canonical DoLR-DILRMP-v2.0 schema."""

    def test_build_structured_land_record(self):
        tables = [
            {
                "table_id": 1,
                "bbox": [50, 50, 300, 200],
                "num_rows": 2,
                "num_cols": 3,
                "headers": ["Khasra No", "Plot Area (Ha)", "Owner Name"],
                "cells": [
                    {"row_idx": 1, "col_idx": 0, "text": "104/1", "column_header": "Khasra No"},
                    {"row_idx": 1, "col_idx": 1, "text": "1.2500", "column_header": "Plot Area (Ha)"},
                    {"row_idx": 1, "col_idx": 2, "text": "Ram Prasad", "column_header": "Owner Name"},
                ],
            }
        ]
        rec = land_records.build_structured_land_record(tables, [])
        self.assertEqual(rec["schema_version"], "DoLR-DILRMP-v2.0")
        self.assertEqual(len(rec["plots"]), 1)
        self.assertEqual(rec["plots"][0]["khasra_no"], "104/1")
        self.assertEqual(rec["plots"][0]["area_numeric"], 1.25)
        self.assertEqual(len(rec["owners"]), 1)
        self.assertEqual(rec["owners"][0]["name"], "Ram Prasad")


class TestFastAPIIntegration(unittest.TestCase):
    """Integration test using TestClient on FastAPI endpoints."""

    def setUp(self):
        self.client = TestClient(app)

    def test_segment_with_tables_and_land_record_fetch(self):
        img_path = Path("image copy 2.png")
        if not img_path.exists():
            self.skipTest("image copy 2.png not present")

        img_bytes = img_path.read_bytes()
        response = self.client.post(
            "/segment",
            files={"image": ("image_copy_2.png", img_bytes, "image/png")},
            data={"ocr": "false", "extract_tables": "true", "include_images": "false"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("job_id", data)
        self.assertIn("land_record", data)
        self.assertEqual(data["land_record"]["schema_version"], "DoLR-DILRMP-v2.0")

        job_id = data["job_id"]
        # Fetch land_record.json endpoint
        lr_resp = self.client.get(f"/jobs/{job_id}/land_record.json")
        self.assertEqual(lr_resp.status_code, 200)
        lr_data = lr_resp.json()
        self.assertEqual(lr_data["schema_version"], "DoLR-DILRMP-v2.0")


class TestDualOCRReconciliation(unittest.TestCase):
    """Tests for linecut.dual_ocr reconciliation, hallucination suppression, and noise rejection."""

    def test_reconcile_real_text_consensus(self):
        from linecut import dual_ocr
        p = {"text": "United Provinces FOR COPIES ONLY", "confidence": 0.995}
        t = {"text": "United Provinces FOR COPIES ONLY", "confidence": 0.98}
        rec = dual_ocr.reconcile_line(p, t)
        self.assertEqual(rec["final_text"], "United Provinces FOR COPIES ONLY")
        self.assertEqual(rec["status"], "consensus")

    def test_reconcile_suppress_wikipedia_hallucinations(self):
        from linecut import dual_ocr
        p_empty = {"text": "", "confidence": 0.0}
        t_hallucinated = {"text": "HelpLearn to editCommunity portalRecent changesUpload file", "confidence": 0.93}
        rec = dual_ocr.reconcile_line(p_empty, t_hallucinated)
        self.assertEqual(rec["final_text"], "")
        self.assertEqual(rec["status"], "empty")

        t_whatlinks = {"text": "What links hereRelated changesUpload fileSpecial pagesPermanent link", "confidence": 0.92}
        rec2 = dual_ocr.reconcile_line(p_empty, t_whatlinks)
        self.assertEqual(rec2["final_text"], "")

    def test_reconcile_reject_low_confidence_noise(self):
        from linecut import dual_ocr
        p_noise = {"text": "( 6)", "confidence": 0.38}
        t_noise = {"text": "What links here", "confidence": 0.91}
        rec = dual_ocr.reconcile_line(p_noise, t_noise)
        self.assertEqual(rec["final_text"], "")

        p_digit_noise = {"text": "2", "confidence": 0.63}
        t_digit_noise = {"text": "unsuccessful", "confidence": 0.44}
        rec2 = dual_ocr.reconcile_line(p_digit_noise, t_digit_noise)
        self.assertEqual(rec2["final_text"], "")


if __name__ == "__main__":
    unittest.main()

