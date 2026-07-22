"""
filename_dates.py
------------------
Parses an expiry date out of a customer-list filename when the file itself
has no exp_date column (e.g. plain .txt phone lists like
"customer_list_expiring_july24.txt"). Two supported conventions:

  1. Month-name + day, year optional (defaults to current year):
     july24, jul24, jul_24, july-24, JULY24, ...
  2. Explicit numeric date, checked first (takes priority over #1):
     2026-07-24, 2026_07_24, 20260724
"""

import re
from datetime import date

MONTH_LOOKUP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

_NUMERIC_PATTERN = re.compile(r"(20\d{2})[-_]?(0[1-9]|1[0-2])[-_]?(0[1-9]|[12]\d|3[01])")
_MONTH_DAY_PATTERN = re.compile(r"([A-Za-z]{3,9})[_-]?(\d{1,2})(?:[_-]?(\d{4}))?")


class UnparsableFilenameDateError(Exception):
    """Raised when no recognizable expiry date pattern is found in a filename."""
    pass


def parse_date_from_filename(filename: str, today: date = None) -> date:
    """
    Extract an expiry date from a filename. Tries the explicit numeric
    pattern first, then falls back to month-name + day (defaulting the
    year to the current calendar year if omitted).
    Raises UnparsableFilenameDateError if neither pattern matches.
    """
    stem = filename.rsplit(".", 1)[0]

    for match in _NUMERIC_PATTERN.finditer(stem):
        year, month, day = (int(g) for g in match.groups())
        try:
            return date(year, month, day)
        except ValueError:
            continue

    for match in _MONTH_DAY_PATTERN.finditer(stem):
        month_str, day_str, year_str = match.groups()
        month = MONTH_LOOKUP.get(month_str.lower())
        if month is None:
            continue
        day = int(day_str)
        if not (1 <= day <= 31):
            continue
        year = int(year_str) if year_str else (today or date.today()).year
        try:
            return date(year, month, day)
        except ValueError:
            continue

    message = "\n".join([
        "",
        "=" * 60,
        f"UNPARSABLE FILENAME DATE — cannot determine exp_date for '{filename}'.",
        "=" * 60,
        "No recognizable expiry date pattern found in the filename.",
        "",
        "Supported naming conventions:",
        "  1. Month name + day (year optional, defaults to current year):",
        "     e.g. customer_list_expiring_july24.txt, ..._jul_24.txt",
        "  2. Explicit numeric date (YYYY-MM-DD / YYYY_MM_DD / YYYYMMDD):",
        "     e.g. customer_list_2026-07-24.txt",
        "",
        "Fix: rename the file to match one of the conventions above,",
        "or use --input <path> together with a file that has an exp_date column.",
        "=" * 60,
        "",
    ])
    raise UnparsableFilenameDateError(message)
