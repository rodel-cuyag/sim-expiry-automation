"""
customer_list.py
------------------
Business logic for Mode 2: the SIM Expiry Priority List. Takes the raw
customer_phone / exp_date list Globe provides and derives the phone
number variants needed for scheduling.

Also handles data validation and categorization for the validation report.
"""

import re
from collections import Counter
import pandas as pd


def compute_days_remaining(exp_date, as_of_date):
    """Whole days from as_of_date to exp_date. Negative if already expired."""
    if pd.isna(exp_date):
        return None
    exp = exp_date.date() if hasattr(exp_date, "date") else exp_date
    return (exp - as_of_date).days


# ── Validation helpers ─────────────────────────────────────────────


def validate_phone_format(raw_value):
    """
    Validate phone number format. Accepts +63/63 (12 digits), 09 (11 digits),
    and 9 (10 digits) formats, after stripping all non-digit characters.

    Returns (is_valid, reason, phone_9x, last_4).
    """
    if pd.isna(raw_value) or str(raw_value).strip() == "":
        return False, "Missing phone number", None, None

    digits = re.sub(r"\D", "", str(raw_value))

    if digits.startswith("63"):
        if len(digits) != 12:
            return False, "Invalid PH number length / Invalid last 4 digits", None, None
        phone_9x = digits[2:]
    elif digits.startswith("09"):
        if len(digits) != 11:
            return False, "Invalid PH number length / Invalid last 4 digits", None, None
        phone_9x = digits[1:]
    elif digits.startswith("9"):
        if len(digits) != 10:
            return False, "Invalid PH number length / Invalid last 4 digits", None, None
        phone_9x = digits
    else:
        return False, "Invalid PH code (must start with +63, 63, 09, or 9)", None, None

    last_4 = phone_9x[-4:]
    return True, None, phone_9x, last_4


def validate_date_format(raw_value, as_of_date):
    """
    Validate expiration date format.
    Returns (is_valid, reason, parsed_date, days_remaining).
    """
    if pd.isna(raw_value) or str(raw_value).strip() == "":
        return False, "Missing expiration date", None, None

    try:
        parsed = pd.to_datetime(raw_value)
        parsed_date = parsed.date() if hasattr(parsed, "date") else parsed
        days_rem = compute_days_remaining(parsed_date, as_of_date)
        return True, None, parsed_date, days_rem
    except (ValueError, TypeError):
        return False, "Invalid date format", None, None


# ── Categorization ─────────────────────────────────────────────────


def categorize_records(raw_df: pd.DataFrame, as_of_date) -> dict:
    """
    Validates and categorizes every row in the raw customer list.

    Processing order per row:
      1. Phone chain: missing → code → length (stops on first failure)
      2. Date chain: missing → format (independent of phone chain)
      3. Duplicate check (global, always runs)

    Returns a dict with three DataFrames:
        valid     — passes all checks, days_remaining >= 0
        invalid   — failed at least one check (+ ``reason`` column)
        expired   — passes checks, days_remaining < 0
    """
    df = raw_df.copy()

    # Phase 1: validate each row
    processed = []
    for _, row in df.iterrows():
        phone_raw = row.get("customer_phone")
        exp_raw = row.get("exp_date")

        reasons = []

        # Phone chain (stops on first failure)
        phone_ok, phone_reason, phone_9x, last_4 = validate_phone_format(phone_raw)
        if phone_ok:
            normalized_phone = "+63" + phone_9x
        else:
            normalized_phone = phone_display
            reasons.append(phone_reason)

        # Date chain (independent of phone chain)
        date_ok, date_reason, parsed_date, days_rem = validate_date_format(exp_raw, as_of_date)
        if not date_ok:
            reasons.append(date_reason)

        phone_display = str(phone_raw).strip() if not pd.isna(phone_raw) else ""
        processed.append({
            "phone_raw": phone_display,
            "normalized_phone": normalized_phone,
            "exp_raw": exp_raw,
            "parsed_date": parsed_date,
            "phone_9x": phone_9x,
            "last_4": last_4,
            "days_remaining": days_rem,
            "reasons": reasons,
        })

    # Phase 2: duplicate detection (global, always runs)
    phone_counts = Counter(p["phone_raw"] for p in processed if p["phone_raw"])
    for p in processed:
        if p["phone_raw"] and phone_counts[p["phone_raw"]] > 1:
            p["reasons"].append("Duplicate phone number")

    # Phase 3: classify into three buckets
    valid_list, invalid_list, expired_list = [], [], []

    for p in processed:
        reason_str = "; ".join(p["reasons"]) if p["reasons"] else None

        if reason_str:
            # Show parsed date if available, otherwise original raw value
            if p["parsed_date"] is not None:
                exp_display = p["parsed_date"]
            elif not pd.isna(p["exp_raw"]):
                exp_display = str(p["exp_raw"])
            else:
                exp_display = ""
            invalid_list.append({
                "customer_phone": p["phone_raw"],
                "exp_date": exp_display,
                "reason": reason_str,
            })
        else:
            out_row = {
                "customer_phone": p["normalized_phone"],
                "customer_phone_9x": p["phone_9x"],
                "last_four_digits": p["last_4"],
                "exp_date": p["parsed_date"],
                "days_remaining": p["days_remaining"],
            }
            if p["days_remaining"] < 0:
                expired_list.append(out_row)
            else:
                valid_list.append(out_row)

    def _sorted_df(rows, columns):
        if not rows:
            return pd.DataFrame(columns=columns)
        return pd.DataFrame(rows).sort_values("days_remaining").reset_index(drop=True)

    valid_cols = [
        "customer_phone", "customer_phone_9x", "last_four_digits",
        "days_remaining", "exp_date",
    ]
    invalid_cols = ["customer_phone", "exp_date", "reason"]

    return {
        "valid": _sorted_df(valid_list, valid_cols),
        "invalid": pd.DataFrame(invalid_list, columns=invalid_cols) if invalid_list else pd.DataFrame(columns=invalid_cols),
        "expired": _sorted_df(expired_list, valid_cols),
    }
