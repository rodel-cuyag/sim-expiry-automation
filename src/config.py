"""
config.py
---------
Single source of truth for file paths and settings.
Change AGENT_ID here (or via --agent-id CLI flag) to point the whole
EOD pipeline at a different agent without touching any other file.
"""

from pathlib import Path

# ── Project folders ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent      # project root
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

# Each mode gets its own input/output subfolder so the two features
# never collide or get confused about which file is which.
EOD_DATA_DIR = DATA_DIR / "eod"
EOD_OUTPUT_DIR = OUTPUT_DIR / "eod"

CUSTOMER_LIST_DATA_DIR = DATA_DIR / "customer_list"
CUSTOMER_LIST_OUTPUT_DIR = OUTPUT_DIR / "customer_list"

# ── Mode 1: EOD Report — input CSVs ──────────────────────────────
CONVERSATIONS_CSV = EOD_DATA_DIR / "conversations.csv"
KPI_RESULTS_CSV = EOD_DATA_DIR / "kpi_results.csv"
TWILIO_EVENTS_CSV = EOD_DATA_DIR / "twilio_webhook_events.csv"

# ── Mode 2: Priority List — input file ───────────────────────────
# The ONLY line you need to change if the customer list is ever named
# or located differently. Can also be overridden with --input on the CLI.
CUSTOMER_LIST_XLSX = CUSTOMER_LIST_DATA_DIR / "sim_expiry_customer_list.xlsx"

# ── Dynamic agent filter (EOD mode only) ─────────────────────────
# This is the ONLY line you need to change to run the EOD report for a
# different agent. It can also be overridden with --agent-id on the CLI.
AGENT_ID = 1060

# ── Output file naming ────────────────────────────────────────────
# Filled in with the report date(s) at runtime (see main.py).
# Single-day EOD runs (start == end) use the plain template; multi-day
# ranges use the range template so the filename itself shows the span.
OUTPUT_FILENAME_TEMPLATE_SINGLE = "SIM_Expiry_EOD_Report_{agent_id}_{start_date}.xlsx"
OUTPUT_FILENAME_TEMPLATE_RANGE = "SIM_Expiry_EOD_Report_{agent_id}_{start_date}_to_{end_date}.xlsx"

CUSTOMER_LIST_OUTPUT_FILENAME_TEMPLATE = "SIM_Expiry_Priority_List_{date}.xlsx"
VALIDATION_OUTPUT_FILENAME_TEMPLATE = "SIM_Expiry_Validation_Report_{date}.xlsx"

# ── Timezone ──────────────────────────────────────────────────────
# Source timestamps are epoch millis (UTC). Plan requires PHT (UTC+8).
TIMEZONE = "Asia/Manila"