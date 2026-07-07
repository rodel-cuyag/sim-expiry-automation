"""
validators.py
---------------
Input validation, kept in its own module so it doesn't get buried inside
main.py and can be reused/tested on its own. Currently just the
--start-date / --end-date range check for the report CLI.
"""

import datetime


class InvalidDateRangeError(Exception):
    """Raised when --start-date / --end-date are missing, malformed, or out of order."""
    pass


def _parse_single_date(date_str: str) -> datetime.date:
    try:
        return datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise InvalidDateRangeError(
            f"Invalid date '{date_str}' — expected format YYYY-MM-DD (e.g. 2026-06-25)."
        )


def parse_date_range(start_str: str, end_str: str):
    """
    Validates and parses the --start-date / --end-date CLI args.

    Rules:
      - Both must be given together, or neither (neither means "default
        to the most recent day found in the data" — resolved later in
        main.py once the data is loaded).
      - Both must be valid YYYY-MM-DD dates.
      - start_date must be <= end_date.

    Returns (start_date, end_date) as datetime.date, or (None, None) if
    neither was provided.
    """
    if (start_str is None) != (end_str is None):
        raise InvalidDateRangeError(
            "--start-date and --end-date must be given together. "
            "Provide both, or omit both to default to the most recent day in the data."
        )

    if start_str is None and end_str is None:
        return None, None

    start_date = _parse_single_date(start_str)
    end_date = _parse_single_date(end_str)

    if start_date > end_date:
        raise InvalidDateRangeError(
            f"--start-date ({start_date}) is after --end-date ({end_date}). "
            "Check the values — did you mean to swap them?"
        )

    return start_date, end_date