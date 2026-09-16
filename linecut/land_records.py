"""Indian Land Record Schema Parser and Entity Extractor (MoRD / DoLR PS 26018).

Transforms extracted 2D table grids and text into standard DILRMP/DoLR revenue schemas:
- Landowner Details (Name, Father's Name, Share)
- Survey / Khasra Number
- Khata / Khewat Number
- Plot Area (Hectares, Bigha-Biswa, Sq. Meters)
- Location Metadata (State, District, Tehsil, Village, Year)
- Land Classification & Crops
- Mutation & Registration Orders
"""
import re
from typing import Any, Dict, List, Optional

from . import validation


def normalize_field_name(header_text: str) -> str:
    """Classify a table column header string into a canonical revenue attribute."""
    h = header_text.lower().strip()

    # Share / Hissa (check before landowner since headers often read 'Landowner Share')
    if any(k in h for k in ["share", "अंश", "हिस्सा", "भाग"]):
        return "share"

    # Area / Rakba (check before landowner since headers often read 'Landowner Land Area')
    if any(k in h for k in ["area", "क्षेत्रफल", "रकबा", "लागण", "विस्तार", "केत्रफल", "फेसल"]):
        return "plot_area"

    # Khasra / Survey
    if any(k in h for k in ["khasra", "खसरा", "सर्वे", "survey", "गाटा", "plot no", "भू-खण्ड", "सवेक्षण"]):
        return "khasra_no"

    # Khata / Khewat
    if any(k in h for k in ["khata", "खाता", "खेवट", "khewat", "खाते"]):
        return "khata_no"

    # Landowner / Occupant
    if any(k in h for k in ["occupant", "owner", "भूमिस्वामी", "खातेदार", "काश्तकार", "मालिक", "कब्जेदार", "landowner"]):
        return "landowner_name"

    # Land Type / Classification
    if any(k in h for k in ["classification", "प्रकार", "श्रेणी", "किस्म", "जमीन", "वर्ग"]):
        return "land_classification"

    # Mutation / Orders
    if any(k in h for k in ["mutation", "नामांतरण", "दाखिल", "फेरफार", "आदेश", "कैफियत"]):
        return "mutation_no"

    # Crop
    if any(k in h for k in ["crop", "फसल", "खरीफ", "रबी", "सोयाबीन"]):
        return "crop"

    return "generic_field"


def extract_metadata_from_text(full_text: str) -> Dict[str, str]:
    """Extract District, Tehsil, Village, and Year from text using regex."""
    meta = {
        "state": "",
        "district": "",
        "tehsil": "",
        "village": "",
        "year": "",
        "survey_no": "",
        "sub_div": "",
    }

    # State
    if "madhya pradesh" in full_text.lower() or "मध्यप्रदेश" in full_text:
        meta["state"] = "Madhya Pradesh"
    elif "himachal" in full_text.lower() or "हिमाचल" in full_text:
        meta["state"] = "Himachal Pradesh"
    elif "goa" in full_text.lower() or "salcete" in full_text.lower() or "गोवा" in full_text:
        meta["state"] = "Goa"
    elif "uttar pradesh" in full_text.lower() or "उत्तर प्रदेश" in full_text:
        meta["state"] = "Uttar Pradesh"

    # District (ज़िला / District)
    dist_m = re.search(r"(?:जिला|District)\s*(?:[:-]+\s*|\s+)([A-Za-z0-9\u0900-\u097F]+)", full_text, re.IGNORECASE)
    if dist_m:
        meta["district"] = dist_m.group(1).strip()

    # Tehsil / Sub Tehsil (तहसील / Taluka / Tehsil)
    tehsil_m = re.search(r"(?:तहसील|Tehsil(?:\s*/\s*Sub\s*Tehsil)?|Taluka)\s*(?:[:-]+\s*|\s+)([A-Za-z0-9\u0900-\u097F]+)", full_text, re.IGNORECASE)
    if tehsil_m:
        meta["tehsil"] = tehsil_m.group(1).strip()

    # Village (ग्राम / Revenue Village / Village)
    village_m = re.search(r"(?:ग्राम|Revenue\s*Village(?:\s*\(LGD\s*Code\))?|Village)\s*(?:[:-]+\s*|\s+)([A-Za-z0-9\u0900-\u097F]+)", full_text, re.IGNORECASE)
    if village_m:
        meta["village"] = village_m.group(1).strip()

    # Year (वर्ष / Jamabandi Year / Year)
    year_m = re.search(r"(?:वर्ष|(?:Jamabandi\s*)?Year)\s*(?:[:-]+\s*|\s+)([0-9]{4}(?:-[0-9]{2,4})?)", full_text, re.IGNORECASE)
    if year_m:
        meta["year"] = year_m.group(1).strip()

    # Survey No (सर्वे नंबर / Survey No)
    survey_m = re.search(r"(?:Survey No\.?|सर्वे नंबर)\s*(?:[:-]+\s*|\s+)([0-9]+)", full_text, re.IGNORECASE)
    if survey_m:
        meta["survey_no"] = survey_m.group(1).strip()

    # Sub Div No
    subdiv_m = re.search(r"(?:Sub Div\.? No\.?|हिस्सा नंबर)\s*(?:[:-]+\s*|\s+)([0-9]+)", full_text, re.IGNORECASE)
    if subdiv_m:
        meta["sub_div"] = subdiv_m.group(1).strip()

    return meta


def build_structured_land_record(
    tables_data: List[Dict[str, Any]], header_lines: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Compile extracted tables and header metadata into the canonical DoLR schema."""
    lines_text = " ".join(l.get("text", "") for l in header_lines[:20])
    metadata = extract_metadata_from_text(lines_text)

    plots: List[Dict[str, Any]] = []
    owners: List[Dict[str, Any]] = []
    mutations: List[Dict[str, Any]] = []
    reported_total_area: Optional[float] = None

    for t in tables_data:
        cells = t.get("cells", [])
        if not cells:
            continue

        # Group cells by row index
        cells_by_row: Dict[int, List[Dict[str, Any]]] = {}
        for c in cells:
            r = c.get("row_idx") if "row_idx" in c else c.get("row", 0)
            cells_by_row.setdefault(r, []).append(c)

        # Also check early rows for metadata (e.g. Row 0 having 'ग्रामः', 'तहसील:', 'जिला:', 'वर्ष:')
        for r in range(min(2, len(cells_by_row))):
            row_str = " ".join(c.get("text", "") for c in cells_by_row.get(r, []))
            row_meta = extract_metadata_from_text(row_str)
            for k, v in row_meta.items():
                if v and not metadata.get(k):
                    metadata[k] = v

        # Find the row with the most column header keywords
        header_row_idx = 0
        best_header_score = -1

        for r, row_cells in cells_by_row.items():
            score = 0
            for c in row_cells:
                field = normalize_field_name(c.get("text", ""))
                if field != "generic_field":
                    score += 1
            if score > best_header_score:
                best_header_score = score
                header_row_idx = r

        # Map column index to canonical field name based on table headers or detected header row
        headers = {}
        if t.get("headers"):
            for idx, h_text in enumerate(t["headers"]):
                headers[idx] = normalize_field_name(h_text)
        else:
            for c in cells_by_row.get(header_row_idx, []):
                col = c.get("col_idx") if "col_idx" in c else c.get("col", 0)
                text = c.get("text", "")
                headers[col] = normalize_field_name(text)

        # Process data rows (rows strictly after header_row_idx)
        for r in sorted(cells_by_row.keys()):
            if r <= header_row_idx and not t.get("headers"):
                continue

            row_cells = cells_by_row[r]
            row_data = {}
            for c in row_cells:
                col = c.get("col_idx") if "col_idx" in c else c.get("col", 0)
                col_header = c.get("column_header")
                if col_header:
                    field = normalize_field_name(col_header)
                else:
                    field = headers.get(col, f"col_{col}")
                val = c.get("text", "").strip()
                if val:
                    row_data[field] = val

            # Also scan all cells in this row for numeric area values (e.g. '0.1000 हेक्टेयर')
            for c in row_cells:
                val = c.get("text", "").strip()
                if "हेक्टेयर" in val or "हे." in val or "ha" in val.lower() or "sq" in val.lower():
                    if "plot_area" not in row_data:
                        row_data["plot_area"] = val

            # Check for plot entry
            k_no = row_data.get("khasra_no") or metadata.get("survey_no")
            p_area = row_data.get("plot_area")
            if p_area:
                p_val = validation.parse_area_value(str(p_area))
                if p_val is not None:
                    plots.append({
                        "khasra_no": k_no or "unspecified",
                        "area": p_area,
                        "area_numeric": p_val,
                        "land_classification": row_data.get("land_classification", "कृषि"),
                        "crop": row_data.get("crop", ""),
                    })
                if "कुल" in str(row_data) or "total" in str(row_data).lower():
                    tot_val = validation.parse_area_value(str(p_area))
                    if tot_val:
                        reported_total_area = tot_val

            # Check for owner entry
            o_name = row_data.get("landowner_name")
            if o_name and len(o_name) > 2 and not any(k in o_name for k in ["भूमिस्वामी", "काश्तकार", "Occupant"]):
                owners.append({
                    "name": o_name,
                    "share": row_data.get("share", "1"),
                    "share_fraction": validation.parse_share_fraction(row_data.get("share", "1")),
                })

            # Check for mutation entry
            m_no = row_data.get("mutation_no")
            if m_no and m_no != "Mutation No.":
                mutations.append({
                    "mutation_no": m_no,
                    "details": row_data.get("generic_field", ""),
                })

    # If survey_no and sub_div exist in metadata, compose composite survey
    if metadata.get("survey_no") and metadata.get("sub_div"):
        composite = f"{metadata['survey_no']}/{metadata['sub_div']}"
        for p in plots:
            if p["khasra_no"] in ("unspecified", metadata.get("survey_no")):
                p["khasra_no"] = composite

    # Run automated validation engine
    val_report = validation.run_full_validation(
        plots=plots, reported_total_area=reported_total_area, owners=owners
    )

    return {
        "schema_version": "DoLR-DILRMP-v2.0",
        "metadata": metadata,
        "plots": plots,
        "owners": owners,
        "mutations": mutations,
        "reported_total_area": reported_total_area,
        "validation": val_report,
    }
