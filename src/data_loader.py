"""
data_loader.py
---------------
Responsible for ONE thing: reading the raw CSV files off disk into
pandas DataFrames. No cleaning, no merging, no business logic here —
that lives in preprocessing.py. Keeping this separate makes it easy
to swap CSVs for a database or API later without touching anything else.
"""

import pandas as pd
from src import config


def load_conversations() -> pd.DataFrame:
    """Load the master call ledger (conversations.csv)."""
    return pd.read_csv(config.CONVERSATIONS_CSV)


def load_kpi_results() -> pd.DataFrame:
    """Load the AI-derived per-call KPI outcomes (kpi_results.csv)."""
    return pd.read_csv(config.KPI_RESULTS_CSV)


def load_twilio_events() -> pd.DataFrame:
    """Load raw Twilio call-progress webhook events."""
    return pd.read_csv(config.TWILIO_EVENTS_CSV)


def load_all() -> dict:
    """Convenience wrapper: load all 3 inputs at once as a dict."""
    return {
        "conversations": load_conversations(),
        "kpi_results": load_kpi_results(),
        "twilio_events": load_twilio_events(),
    }
