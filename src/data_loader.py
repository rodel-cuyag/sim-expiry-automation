"""
data_loader.py
--------------
Responsible for ONE thing: reading the raw input files off disk into
pandas DataFrames. No cleaning, no merging, no business logic here —
that lives in preprocessing.py (EOD mode) / customer_list.py (Priority
List mode). Keeping this separate makes it easy to swap files for a
database or API later without touching anything else.

For EOD mode, instead of requiring hardcoded filenames, the loader scans
the data/eod/ directory for CSV files and identifies each one by its
column headers (signature matching). Files can be named anything —
"kpi_results 2.csv", "twilio webhook events.csv", etc. — as long as
the required columns are present.
"""

import pandas as pd
from src import config
from src.progress import Spinner


class MissingInputFileError(Exception):
    """Raised when a required input file is not found on disk."""
    pass


class MissingHeaderError(Exception):
    """Raised when the customer list input is missing required columns."""
    pass


# ── Mode 1: EOD Report ────────────────────────────────────────────

def _discover_eod_files() -> dict:
    """
    Scan data/eod/ for CSV files and identify each one by matching its
    column headers against EOD_FILE_SIGNATURES. Returns a dict mapping
    role -> {path, columns, filename}.

    Raises MissingInputFileError if:
      - No CSVs found in the directory
      - A role has zero matching files
      - Multiple files match the same role (handled because each assigned
        file is removed from consideration for subsequent roles)
    """
    csv_paths = sorted(config.EOD_DATA_DIR.glob("*.csv"))

    if not csv_paths:
        raise MissingInputFileError(
            f"No CSV files found in {config.EOD_DATA_DIR}. "
            "Place at least the required CSV files there and run again."
        )

    # Load column headers for every CSV in the folder.
    candidates = {}
    for path in csv_paths:
        df = pd.read_csv(path, nrows=0)
        candidates[path.name] = {
            "path": path,
            "columns": set(df.columns),
        }

    # Match each role to the best file (highest signature-column overlap).
    assigned = {}
    used_files = set()

    for role, sig in config.EOD_FILE_SIGNATURES.items():
        best_file = None
        best_score = 0

        for fname, info in candidates.items():
            if fname in used_files:
                continue
            score = len(info["columns"] & sig)
            if score > best_score:
                best_score = score
                best_file = fname

        if best_file is None or best_score == 0:
            found_list = ", ".join(candidates)
            raise MissingInputFileError(
                f"Could not find a CSV with the '{role}' signature columns: "
                f"{', '.join(sorted(sig))}.\n"
                f"Found files: [{found_list}]\n"
                f"Ensure a CSV in {config.EOD_DATA_DIR} has the "
                f"expected columns listed above."
            )

        assigned[role] = {
            "path": candidates[best_file]["path"],
            "columns": candidates[best_file]["columns"],
            "filename": best_file,
        }
        used_files.add(best_file)

    # Warn about unmatched files that will be ignored.
    for fname in candidates:
        if fname not in used_files:
            print(f"Warning: '{fname}' did not match any known "
                  f"signature and will be ignored.")

    return assigned


def _validate_eod_headers(role: str, columns: set, filename: str):
    """
    Check that a discovered file has all required columns for its role.
    Raises MissingHeaderError with a clear message if any are missing.
    """
    required = config.EOD_REQUIRED_COLUMNS[role]
    missing = [col for col in required if col not in columns]

    if missing:
        msg_lines = [
            "",
            "=" * 60,
            f"MISSING REQUIRED HEADERS in '{filename}' (matched as '{role}')",
            "=" * 60,
            f"Expected: {', '.join(required)}",
            f"Found:    {', '.join(sorted(columns))}",
            f"Missing:  {', '.join(missing)}",
            "",
            "Fix: make sure the CSV file has the columns listed above",
            "with those exact names, then run the script again.",
            "=" * 60,
            "",
        ]
        raise MissingHeaderError("\n".join(msg_lines))


def load_all() -> dict:
    """
    Discover, validate, and load all 3 EOD input CSVs.
    Returns dict with keys 'conversations', 'kpi_results', 'twilio_events'.
    """
    discovered = _discover_eod_files()

    loaded = {}
    for role, info in discovered.items():
        _validate_eod_headers(role, info["columns"], info["filename"])
        with Spinner(f"Loading {info['filename']}"):
            loaded[role] = pd.read_csv(info["path"])

    return loaded


# ── Mode 2: Priority List ─────────────────────────────────────────

def validate_customer_list_file(path=None):
    """
    Checks that the customer list workbook exists before we try to read
    it. `path` lets --input override the default config location.
    """
    target = path or config.CUSTOMER_LIST_XLSX

    if not target.exists():
        message = "\n".join([
            "",
            "=" * 60,
            "MISSING INPUT FILE — cannot generate the priority list.",
            "=" * 60,
            f"Expected file: {target}",
            "",
            "Fix: place the customer list workbook at the path above",
            "(or pass --input <path> to point at a different location),",
            "then run the script again.",
            "=" * 60,
            "",
        ])
        raise MissingInputFileError(message)


def load_customer_list(path=None) -> pd.DataFrame:
    """Load the raw SIM expiry customer list (customer_phone, exp_date).
    Supports .xlsx and .csv — auto-detected from file extension."""
    target = path or config.CUSTOMER_LIST_XLSX
    with Spinner(f"Loading {target.name}"):
        suffix = target.suffix.lower()
        if suffix == ".csv":
            return pd.read_csv(target)
        return pd.read_excel(target, sheet_name=0)


def validate_customer_list_headers(df: pd.DataFrame):
    """
    Checks that the DataFrame contains all required columns.
    Raises MissingHeaderError with a clear message if any are missing.
    """
    required = config.REQUIRED_CUSTOMER_LIST_HEADERS
    missing = [col for col in required if col not in df.columns]

    if missing:
        message = "\n".join([
            "",
            "=" * 60,
            "MISSING REQUIRED HEADERS — cannot generate the priority list.",
            "=" * 60,
            f"Expected headers: {', '.join(required)}",
            f"Found headers:    {', '.join(df.columns.tolist())}",
            f"Missing header(s): {', '.join(missing)}",
            "",
            "Fix: make sure the input file (CSV or Excel) has the columns",
            "listed above with those exact names, then run the script again.",
            "=" * 60,
            "",
        ])
        raise MissingHeaderError(message)
