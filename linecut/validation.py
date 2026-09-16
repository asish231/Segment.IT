"""Automated Business Rules Validation Engine for Land Records (MoRD / DoLR PS 26018).

Implements mathematical invariants, format checks, and cross-field integrity verification:
1. Area Balance Invariant: Sum of individual plot areas == Reported Total Khata Area.
2. Ownership Share Invariant: Sum of fractional/percentage owner shares == 1.0 (100%).
3. Survey / Khasra Format Check: Verifies legal standard numbering format (e.g. 104/1, 82/4).
4. Duplicate Detection: Detects accidental duplicate survey/khasra entries.
5. Calibrated Confidence & HITL Review Routing: Flags records needing human review.
"""
import re
from fractions import Fraction
from typing import Any, Dict, List, Optional, Tuple, Union

# Values the extractor fills in when a field genuinely couldn't be read, rather than
# leaving it blank. These are "missing", not "malformed" or "duplicated" — format and
# duplicate checks should skip them instead of failing on them.
PLACEHOLDER_VALUES = {"unspecified", "unknown", "n/a", "na", "-", "--", "none", "null", ""}


def _is_placeholder(value: str) -> bool:
    return value.strip().lower() in PLACEHOLDER_VALUES


def parse_area_value(area_str: str) -> Optional[float]:
    """Parse numeric area from English or Hindi strings (e.g. '0.1000 हेक्टेयर', '1.3500 हे.').

    Handles decimal notations, standard fractions, and formats like '0000.17.00'.
    """
    if not area_str:
        return None

    clean = area_str.strip().replace("हेक्टेयर", "").replace("हे.", "").replace("ha", "").strip()

    # Handle dotted segments like Goa/Maharashtra '0000.17.00' (Ha.Ars.Sq.Mtrs)
    parts = clean.split(".")
    if len(parts) == 3:
        try:
            ha = float(parts[0])
            ares = float(parts[1])
            sq_m = float(parts[2])
            # Convert to total hectares: 1 are = 0.01 ha, 1 sq.m = 0.0001 ha
            return round(ha + ares * 0.01 + sq_m * 0.0001, 6)
        except ValueError:
            pass

    # Standard decimal float
    match = re.search(r"[-+]?\d*\.?\d+", clean)
    if match:
        try:
            return float(match.group(0))
        except ValueError:
            return None
    return None


def parse_share_fraction(share_str: str) -> Optional[float]:
    """Parse ownership share fraction or decimal (e.g. '1/2', '1/4', '0.5', '1', 'पूर्ण')."""
    if not share_str:
        return None
    s = share_str.strip()
    if s in ("पूर्ण", "1", "1.0", "1/1", "स्वयं"):
        return 1.0

    # Fraction like 1/2 or 3/4
    frac_match = re.search(r"(\d+)\s*/\s*(\d+)", s)
    if frac_match:
        try:
            num = int(frac_match.group(1))
            den = int(frac_match.group(2))
            if den > 0:
                return float(Fraction(num, den))
        except Exception:
            pass

    # Percentage like 50%
    if "%" in s:
        pct_match = re.search(r"(\d+(?:\.\d+)?)%", s)
        if pct_match:
            try:
                return float(pct_match.group(1)) / 100.0
            except ValueError:
                pass

    # Plain float
    try:
        val = float(s)
        if 0.0 <= val <= 1.0:
            return val
    except ValueError:
        pass

    return None


def validate_area_balance(
    plot_areas: Union[List[float], List[Dict[str, Any]]],
    reported_total: Optional[Union[float, str]],
    tolerance: float = 0.002,
) -> Dict[str, Any]:
    """Validate that sum of individual plot areas matches the reported total."""
    if not plot_areas:
        return {
            "rule": "area_balance",
            "status": "skipped",
            "message": "No plot areas available for validation.",
        }

    # Normalize plot_areas: if dicts, extract numeric values
    numeric_areas: List[float] = []
    for item in plot_areas:
        if isinstance(item, (int, float)):
            numeric_areas.append(float(item))
        elif isinstance(item, dict):
            num = item.get("area_numeric")
            if num is None and "area" in item:
                num = parse_area_value(str(item["area"]))
            if num is not None:
                numeric_areas.append(float(num))
        elif isinstance(item, str):
            num = parse_area_value(item)
            if num is not None:
                numeric_areas.append(float(num))

    if not numeric_areas:
        return {
            "rule": "area_balance",
            "status": "skipped",
            "message": "No parseable plot areas found for validation.",
        }

    rep_total_num: Optional[float] = None
    if reported_total is not None:
        if isinstance(reported_total, (int, float)):
            rep_total_num = float(reported_total)
        else:
            rep_total_num = parse_area_value(str(reported_total))

    computed_sum = round(sum(numeric_areas), 6)
    if rep_total_num is None:
        return {
            "rule": "area_balance",
            "status": "info",
            "computed_total": computed_sum,
            "message": f"Computed total area: {computed_sum} (no total specified in document to verify against).",
        }

    diff = abs(computed_sum - rep_total_num)
    passed = diff <= tolerance

    return {
        "rule": "area_balance",
        "status": "passed" if passed else "failed",
        "computed_total": computed_sum,
        "computed_sum": computed_sum,
        "reported_total": rep_total_num,
        "difference": round(diff, 6),
        "discrepancy": round(diff, 6),
        "tolerance": tolerance,
        "message": (
            f"Area balance verified: sum of plots ({computed_sum}) matches total ({rep_total_num})."
            if passed
            else f"Area balance mismatch: sum of plots ({computed_sum}) differs from total ({rep_total_num}) by {round(diff, 4)}."
        ),
    }


def validate_ownership_shares(
    shares: Union[List[float], List[Dict[str, Any]], List[str]], tolerance: float = 0.01
) -> Dict[str, Any]:
    """Validate that co-owner shares sum up to 1.0 (100%)."""
    if not shares:
        return {
            "rule": "ownership_shares",
            "status": "skipped",
            "message": "No ownership shares specified to validate.",
        }

    numeric_shares: List[float] = []
    for item in shares:
        if isinstance(item, (int, float)):
            numeric_shares.append(float(item))
        elif isinstance(item, dict):
            s_str = item.get("share", "")
            s_val = parse_share_fraction(str(s_str))
            if s_val is not None:
                numeric_shares.append(s_val)
        elif isinstance(item, str):
            s_val = parse_share_fraction(item)
            if s_val is not None:
                numeric_shares.append(s_val)

    if not numeric_shares:
        return {
            "rule": "ownership_shares",
            "status": "skipped",
            "message": "No parseable ownership shares specified to validate.",
        }

    total_share = round(sum(numeric_shares), 4)
    passed = abs(total_share - 1.0) <= tolerance

    return {
        "rule": "ownership_shares",
        "status": "passed" if passed else "failed",
        "total_share": total_share,
        "computed_sum": total_share,
        "message": (
            f"Ownership share verified: total equals {total_share * 100:.1f}%."
            if passed
            else f"Ownership share discrepancy: total share is {total_share * 100:.1f}% (expected 100%)."
        ),
    }


def validate_khasra_numbers(
    khasra_list: Union[List[str], List[Dict[str, Any]]]
) -> Dict[str, Any]:
    """Check format validity and duplicates for Khasra / Survey numbers."""
    if not khasra_list:
        return {
            "rule": "khasra_format",
            "status": "skipped",
            "message": "No Khasra numbers found.",
        }

    # Normalize to string list
    normalized_list: List[str] = []
    for item in khasra_list:
        if isinstance(item, str):
            normalized_list.append(item)
        elif isinstance(item, dict):
            val = item.get("khasra_no") or item.get("survey_no")
            if val:
                normalized_list.append(str(val))

    if not normalized_list:
        return {
            "rule": "khasra_format",
            "status": "skipped",
            "message": "No Khasra numbers found.",
        }

    # A field the extractor couldn't read at all (filled with a placeholder like
    # "unspecified") is missing data, not a malformed or duplicate value — skip it here
    # rather than penalizing the record for what's really an OCR gap.
    unspecified_count = sum(1 for k in normalized_list if _is_placeholder(k))
    checkable = [k for k in normalized_list if not _is_placeholder(k)]

    if not checkable:
        return {
            "rule": "khasra_format",
            "status": "skipped",
            "message": f"All {unspecified_count} Khasra/Survey number(s) are unread/unspecified — nothing to check.",
        }

    # Standard pattern: numbers, optionally with slash/dash subdivision (e.g. 452, 452/1, 82-A, 82/4, 128/2-A)
    pattern = re.compile(r"^[0-9]+([/\-][0-9A-Za-z]+)*$")
    invalid = []
    seen = set()
    duplicates = []

    for k in checkable:
        k_clean = k.strip()
        if not pattern.match(k_clean):
            invalid.append(k_clean)
        if k_clean in seen:
            duplicates.append(k_clean)
        seen.add(k_clean)

    passed = len(invalid) == 0 and len(duplicates) == 0
    unspecified_note = f" ({unspecified_count} unspecified, skipped)" if unspecified_count else ""

    return {
        "rule": "khasra_format",
        "status": "passed" if passed else "failed",
        "total_checked": len(checkable),
        "unspecified": unspecified_count,
        "invalid_format": invalid,
        "duplicates": duplicates,
        "message": (
            f"All {len(checkable)} Khasra/Survey numbers valid with no duplicates{unspecified_note}."
            if passed
            else f"Issues detected in Khasra numbers: invalid={invalid}, duplicates={duplicates}{unspecified_note}"
        ),
    }


def run_full_validation(
    plots: Union[List[Dict[str, Any]], Dict[str, Any]],
    reported_total_area: Optional[Union[float, str]] = None,
    owners: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Execute all automated business validation rules on extracted land record data."""
    if isinstance(plots, dict):
        rec = plots
        plots_list = rec.get("plots", [])
        if reported_total_area is None:
            reported_total_area = rec.get("reported_total_area")
        if owners is None:
            owners = rec.get("owners", [])
    else:
        plots_list = plots
    plot_areas = []
    khasra_numbers = []
    for p in plots_list:
        area_val = parse_area_value(str(p.get("area", "")))
        if area_val is not None:
            plot_areas.append(area_val)
        k_no = p.get("khasra_no") or p.get("survey_no")
        if k_no:
            khasra_numbers.append(str(k_no))

    area_check = validate_area_balance(plot_areas, reported_total_area)
    khasra_check = validate_khasra_numbers(khasra_numbers)

    # 2. Ownership Shares Check
    share_values = []
    if owners:
        for o in owners:
            s_val = parse_share_fraction(str(o.get("share", "")))
            if s_val is not None:
                share_values.append(s_val)
    share_check = validate_ownership_shares(share_values)

    all_checks = [area_check, khasra_check, share_check]
    failed_checks = [c for c in all_checks if c["status"] == "failed"]
    is_valid = len(failed_checks) == 0

    return {
        "validation_passed": is_valid,
        "total_rules_checked": len(all_checks),
        "rules_passed": len([c for c in all_checks if c["status"] == "passed"]),
        "rules_failed": len(failed_checks),
        "rules_skipped": len([c for c in all_checks if c["status"] in ("skipped", "info")]),
        "checks": all_checks,
        "review_required": not is_valid,
        "review_reasons": [c["message"] for c in failed_checks],
    }
