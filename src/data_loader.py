"""
data_loader.py
---------------
Responsible for ONE thing: reading the raw input files off disk into
pandas DataFrames. No cleaning, no merging, no business logic here —
that lives in preprocessing.py (EOD mode) / customer_list.py (Priority
List mode). Keeping this separate makes it easy to swap files for a
database or API later without touching anything else.
"""

import pandas as pd
from src import config
from src.progress import Spinner


class MissingInputFileError(Exception):
    """Raised when a required input file is not found on disk."""
    pass


# ── Mode 1: EOD Report ────────────────────────────────────────────

def validate_input_files():
    """
    Checks that all 3 required EOD-mode CSVs exist in data/eod/ before
    we try to read anything. Fails fast with a clear, actionable message
    instead of a raw FileNotFoundError traceback buried in a pandas stack trace.
    """
    required_files = {
        "conversations.csv": config.CONVERSATIONS_CSV,
        "kpi_results.csv": config.KPI_RESULTS_CSV,
        "twilio_webhook_events.csv": config.TWILIO_EVENTS_CSV,
    }

    missing = [name for name, path in required_files.items() if not path.exists()]

    if missing:
        message_lines = [
            "",
            "=" * 60,
            "MISSING INPUT FILE(S) — cannot generate the EOD report.",
            "=" * 60,
            f"Expected folder: {config.EOD_DATA_DIR}",
            "",
            "Missing file(s):",
        ]
        message_lines += [f"  - {name}" for name in missing]
        message_lines += [
            "",
            "Fix: place the missing CSV(s) in the data/eod/ folder above,",
            "using those exact filenames, then run the script again.",
            "=" * 60,
            "",
        ]
        raise MissingInputFileError("\n".join(message_lines))


def load_conversations() -> pd.DataFrame:
    """Load the master call ledger (conversations.csv)."""
    with Spinner("Loading conversations.csv"):
        return pd.read_csv(config.CONVERSATIONS_CSV)


def load_kpi_results() -> pd.DataFrame:
    """Load the AI-derived per-call KPI outcomes (kpi_results.csv)."""
    with Spinner("Loading kpi_results.csv"):
        return pd.read_csv(config.KPI_RESULTS_CSV)


def load_twilio_events() -> pd.DataFrame:
    """Load raw Twilio call-progress webhook events."""
    with Spinner("Loading twilio_webhook_events.csv"):
        return pd.read_csv(config.TWILIO_EVENTS_CSV)


def load_all() -> dict:
    """Convenience wrapper: validates EOD files exist, then loads all 3."""
    validate_input_files()
    return {
        "conversations": load_conversations(),
        "kpi_results": load_kpi_results(),
        "twilio_events": load_twilio_events(),
    }


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
    """Load the raw SIM expiry customer list (customer_phone, exp_date)."""
    target = path or config.CUSTOMER_LIST_XLSX
    with Spinner("Loading sim_expiry_customer_list.xlsx"):
        return pd.read_excel(target, sheet_name=0)