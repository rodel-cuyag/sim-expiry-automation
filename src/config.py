"""
config.py
---------
Single source of truth for file paths and settings.
Change AGENT_ID here (or via --agent-id CLI flag) to point the whole
pipeline at a different agent without touching any other file.
"""

from pathlib import Path

# ── Project folders ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent      # project root
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

# ── Input CSV files ──────────────────────────────────────────────
CONVERSATIONS_CSV = DATA_DIR / "conversations.csv"
KPI_RESULTS_CSV = DATA_DIR / "kpi_results.csv"
TWILIO_EVENTS_CSV = DATA_DIR / "twilio_webhook_events.csv"

# ── Dynamic agent filter ─────────────────────────────────────────
# This is the ONLY line you need to change to run the report for a
# different agent. It can also be overridden with --agent-id on the CLI.
AGENT_ID = 1060

# ── Output file ───────────────────────────────────────────────────
# Filled in with the report date at runtime (see main.py)
OUTPUT_FILENAME_TEMPLATE = "SIM_Expiry_EOD_Report_{agent_id}_{date}.xlsx"

# ── Timezone ──────────────────────────────────────────────────────
# Source timestamps are epoch millis (UTC). Plan requires PHT (UTC+8).
TIMEZONE = "Asia/Manila"
