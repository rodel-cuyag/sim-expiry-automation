"""
customer_list.py
------------------
Business logic for Mode 2: the SIM Expiry Priority List. Takes the raw
customer_phone / exp_date list Globe provides and derives the phone
number variants + urgency tier needed for scheduling, following the
Priority Tier definition
(Tier 1 = 0-3 days to expiry, Tier 2 = 4-7 days, Tier 3 = 8+ days).

No I/O here — that lives in data_loader.py — this module only
transforms a DataFrame that's already been loaded.
"""

import re
import pandas as pd


def clean_phone(raw_value):
    """
    Splits a single customer_phone value (e.g. "+63 948 508 9512") into:
      - customer_phone_9x: the 10-digit local number with the +63 country
        code stripped (e.g. "9485089512")
      - last_four_digits: the last 4 digits of that number (e.g. "9512")

    Defensive like clean_contact_number() in preprocessing.py: strips to
    digits-only first, then removes a leading country/trunk code if
    present, rather than assuming a fixed format and crashing on anything
    else.
    """
    if pd.isna(raw_value):
        return None, None

    digits = re.sub(r"\D", "", str(raw_value))

    if digits.startswith("63") and len(digits) == 12:
        local = digits[2:]          # +63 948 508 9512 -> 9485089512
    elif digits.startswith("0") and len(digits) == 11:
        local = digits[1:]          # 09485089512 -> 9485089512
    else:
        local = digits              # already local format, or unexpected — keep as-is

    last_four = local[-4:] if len(local) >= 4 else (local or None)
    return local or None, last_four


def compute_days_remaining(exp_date, as_of_date):
    """Whole days from as_of_date to exp_date. Negative if already expired."""
    if pd.isna(exp_date):
        return None
    exp = exp_date.date() if hasattr(exp_date, "date") else exp_date
    return (exp - as_of_date).days


def compute_priority_tier(days_remaining):
    if days_remaining is None:
        return None
    if days_remaining < 0:
        return "EXPIRED"
    if days_remaining <= 3:
        return "TIER 1"
    if days_remaining <= 7:
        return "TIER 2"
    return "TIER 3"


# Sort order for the output: most urgent first (matches the scheduler
# logic in the plan — Tier 1 records always fill first).
_TIER_SORT_ORDER = {
    "EXPIRED": 0,
    "TIER 1": 1,
    "TIER 2": 2,
    "TIER 3": 3,
}


def build_priority_list(raw_df: pd.DataFrame, as_of_date) -> pd.DataFrame:
    """
    Transforms the raw (customer_phone, exp_date) list into the final
    Priority List DataFrame, ready to write to Excel.

    Output columns, in order:
      customer_phone, customer_phone_9x, last_four_digits,
      days_remaining, exp_date, priority_tier

    Sorted by days_remaining ascending (most urgent first), with tier as
    tiebreaker.
    """
    df = raw_df.copy()

    mask = df["customer_phone"].notna()
    df.loc[mask, "customer_phone"] = (
        df.loc[mask, "customer_phone"].astype(str).str.replace(r"\s+", "", regex=True)
    )

    cleaned = df["customer_phone"].apply(clean_phone)
    df["customer_phone_9x"] = cleaned.apply(lambda t: t[0])
    df["last_four_digits"] = cleaned.apply(lambda t: t[1])

    df["days_remaining"] = df["exp_date"].apply(
        lambda d: compute_days_remaining(d, as_of_date)
    )
    df["priority_tier"] = df["days_remaining"].apply(compute_priority_tier)
    df["exp_date"] = pd.to_datetime(df["exp_date"]).dt.date

    out = df[[
        "customer_phone",
        "customer_phone_9x",
        "last_four_digits",
        "days_remaining",
        "exp_date",
        "priority_tier",
    ]].copy()

    out["_tier_sort"] = out["priority_tier"].map(_TIER_SORT_ORDER)
    out = (
        out.sort_values(["days_remaining", "_tier_sort"])
        .drop(columns="_tier_sort")
        .reset_index(drop=True)
    )
    return out