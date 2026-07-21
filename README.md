# SIM Expiry Voicebot — Report Automation (EOD Report + Priority List + Validation Report)

Generates one of two reports:

- **EOD Report** — a 2-sheet Excel workbook (**EOD Report** + **Call Detail
  Log**) from 3 raw source CSVs (`conversations`, `kpi_results`,
  `twilio_webhook_events`), filtered to a single agent and a calling-day range.

- **Priority List** — produces two CSVs and one Excel workbook from the customer
  list file provided by Globe: a **Priority List CSV** (valid, urgency-tiered
  numbers), a **Priority List CSV without tier column**, and a **Validation
   Report** (3-sheet data quality report with invalid/expired records).

---

## 1. Step-by-step: setting this up in VS Code (from scratch)

1. **Install prerequisites** (skip if already installed):
   - [Python 3.10+](https://www.python.org/downloads/)
   - [VS Code](https://code.visualstudio.com/)
   - In VS Code, install the **Python extension** (Microsoft) from the Extensions panel (`Ctrl+Shift+X` / `Cmd+Shift+X`, search "Python").

2. **Open the project folder in VS Code**
   `File → Open Folder...` → select the `sim_expiry_automation` folder.

3. **Open a terminal inside VS Code**
   `Terminal → New Terminal` (or `` Ctrl+` ``).

4. **Create a virtual environment** (see "Do we need venv?" below for why):
```bash
   python -m venv venv
```

5. **Activate it**
   - Windows (PowerShell): `venv\Scripts\Activate.ps1`
   - Mac/Linux: `source venv/bin/activate`

   VS Code may also prompt "Select Interpreter" — pick the one inside
   `./venv`. Do this via `Ctrl+Shift+P` → "Python: Select Interpreter" if it
   doesn't prompt automatically.

6. **Install dependencies**
```bash
   pip install -r requirements.txt
```

7. **Add your input files** into the appropriate subdirectories under `data/`:

   **EOD mode** (3 CSVs in `data/eod/`):
   - `data/eod/conversations.csv`
   - `data/eod/kpi_results.csv`
   - `data/eod/twilio_webhook_events.csv`

   **Priority List mode** (single workbook in `data/customer_list/`):
   - `data/customer_list/sim_expiry_customer_list.xlsx`

8. **Run it**
```bash
   python main.py                                                       # EOD mode (default), most recent date, config AGENT_ID
   python main.py --mode priority-list                                   # Priority List mode, as-of today (PHT)
   python main.py --mode priority-list --as-of-date 2026-07-10           # Priority List, specific date
    python main.py --mode priority-list --input path/to/other.xlsx        # Priority List, override input file
```
   The generated files land in `output/eod/` (EOD mode) or
   `output/customer_list/{date}/` (Priority List mode, date-stamped subfolder).

   Or run `.\run_samples.ps1` (Windows PowerShell) to exercise several
   scenarios at once — default run, single day, multi-day range, a
   different agent, and the date-validation error cases.

---

## 2. Tools used

| Tool | Purpose |
|---|---|
| Python 3.10+ | Core language |
| `pandas` | CSV loading, cleaning, joining, aggregation |
| `openpyxl` | Writing formatted Excel workbooks (EOD: 2-sheet / Validation Report: 4-sheet) |
| `pandas.to_csv` | Writing Priority List CSVs (with and without tier column) |
| VS Code + Python extension | Editor / debugger |
| `venv` (built into Python, no separate install) | Isolated dependency environment |

## Do we need venv?

**Yes, recommended.** It keeps `pandas`/`openpyxl` versions for this project
separate from anything else on your machine, so upgrading a package for a
different project later can't silently break this script (or vice versa).
It's a couple of extra terminal commands (steps 4–5 above) for meaningfully
safer long-term maintenance — worth it even for a small script like this.

---

## 3. Project structure (modular by design)

```
sim_expiry_automation/
├── data/
│   ├── customer_list/         → input: sim_expiry_customer_list.xlsx or .csv (Priority List mode)
│   └── eod/                   → input: 3 CSVs (EOD mode)
├── output/
│   ├── customer_list/
│   │   └── {date}/            → generated: SIM_Expiry_Priority_List_{date}.csv
│   │                           + SIM_Expiry_Priority_List_{date}_no_tier.csv
│   │                           + SIM_Expiry_Validation_Report_{date}.xlsx
│   └── eod/                   → generated: SIM_Expiry_EOD_Report_{agent_id}_{date}.xlsx
├── src/
│   ├── config.py              → all settings in one place (paths, AGENT_ID, timezone, filename templates, required headers)
│   ├── validators.py          → validates date CLI args (--start-date/--end-date, --as-of-date)
│   ├── data_loader.py         → reads input files off disk; validates they exist and have required headers
│   ├── progress.py            → spinning "loading..." animation in the terminal
│   ├── preprocessing.py       → cleans data, parses JSON, filters to one agent, joins 3 sources (EOD mode)
│   ├── call_detail.py         → builds the "Call Detail Log" sheet (one row per call)
│   ├── eod_report.py          → builds the "EOD Report" sheet (aggregated summary)
│   ├── customer_list.py       → builds the Priority List + validates/categorizes records (valid, invalid, expired, beyond 14 days); normalizes phone numbers to +63XXXXXXXXXX
│   └── excel_writer.py        → writes DataFrames to formatted .xlsx (2-sheet EOD, multi-sheet validation report) and to .csv (priority list, no-tier priority list)
├── main.py                    → entry point; dispatches to run_eod() or run_priority_list() based on --mode
├── run_samples.ps1            → optional: runs several scenarios in one go
├── requirements.txt           → pandas, openpyxl
└── README.md                  → this file
```

Each module has exactly one job, so you can swap any piece (e.g. point
`data_loader.py` at a database instead of CSVs later) without touching the
others.

---

## 4. Usage

Choose a mode with `--mode` (`eod` is the default):

### Mode 1: EOD Report (`--mode eod`)

```bash
python main.py                                                   # most recent date, agent from config.py
python main.py --start-date 2026-06-25 --end-date 2026-06-29     # a date range
python main.py --start-date 2026-06-29 --end-date 2026-06-29     # a single day (range of 1)
python main.py --agent-id 1060 --start-date 2026-06-25 --end-date 2026-06-29
```

- `--start-date` / `--end-date`: inclusive range in `YYYY-MM-DD`. Must be
  given together (or both omitted — defaults to the most recent single day
  in the data). Start cannot be after end.
- `--agent-id`: override `config.AGENT_ID` (defaults to `1060`).

**Output naming:** single-day → `SIM_Expiry_EOD_Report_{agent_id}_{date}.xlsx`;
multi-day → `SIM_Expiry_EOD_Report_{agent_id}_{start}_to_{end}.xlsx`.
Lands in `output/eod/`.

**Report structure:** the EOD Report sheet is **one aggregated row** for the
whole period (not one row per day), with a `Report Period` and `Days in Range`
field. The Call Detail Log sheet lists every call in that period with a
`Call Date (PHT)` column so you can still see which day each row belongs to.

### Mode 2: Priority List (`--mode priority-list`)

```bash
python main.py --mode priority-list                               # as-of today (PHT)
python main.py --mode priority-list --as-of-date 2026-07-10       # specific reference date
python main.py --mode priority-list --input path/to/other.csv     # override input file (CSV or Excel)
```

- `--as-of-date`: reference date in `YYYY-MM-DD` used to compute
  `days_remaining`. Defaults to today in PHT.
- `--input`: override the customer list file path
  (default: `data/customer_list/sim_expiry_customer_list.xlsx`).
  Supports both `.xlsx` and `.csv`.

**Header validation:** before any processing, the script checks that the input
file contains the required columns `customer_phone` and `exp_date`. If either is
missing, processing stops immediately with a clear error message.

**Phone normalization:** valid phone numbers in all outputs are formatted as
`+63XXXXXXXXXX` (no spaces, consistent prefix) regardless of the input format
(e.g. `+63 998 766 5432` → `+639987665432`, `639212223242` → `+639212223242`).

**Output:** three files in `output/customer_list/{date}/` (date-stamped subfolder):

- `SIM_Expiry_Priority_List_{date}.csv` — all valid records (0–14 days + beyond-14-day),
  with `customer_phone` normalized to `+63XXXXXXXXXX`, all columns including `priority_tier`
- `SIM_Expiry_Priority_List_{date}_no_tier.csv` — same records, same headers,
  without the `priority_tier` column
- `SIM_Expiry_Validation_Report_{date}.xlsx` — data validation + categorization
  (3 sheets: Summary, Invalid Data, Expired Numbers)

**Validation rules** (applied to every record in order):

| # | Check | Fails when... |
|---|---|---|
| 1 | Missing phone | `customer_phone` is blank |
| 2 | Missing date | `exp_date` is blank |
| 3 | Invalid date | `exp_date` cannot be parsed |
| 4 | Duplicate phone | Same `customer_phone` appears more than once |
| 5 | Invalid PH code | Number doesn't start with `+63` or `63` |
| 6 | Invalid length | Not exactly 12 digits after stripping non-digits |

Phone and date chains are independent (both are reported). Duplicate check always
runs. Cascading errors are suppressed (e.g. invalid PH code does not also report
invalid length). Multiple reasons are joined with `"; "`.

**Validation Report — 3 sheets:**

| Sheet | Content |
|---|---|
| Summary | Record counts per category with percentages |
| Invalid Data | Rows that failed validation with concatenated `reason` column |
| Expired Numbers | Already-expired records (`days_remaining < 0`) |

**Priority Tier definitions** (per the Globe SIM Expiry Scale-Up plan):

| Tier | Days remaining | Meaning |
|------|---------------|---------|
| EXPIRED | < 0 | Past expiry |
| TIER 1 | 0–3 | Urgent |
| TIER 2 | 4–7 | Soon |
| TIER 3 | 8–14 | Watch |

Records with `days_remaining > 14` are included in both CSV outputs alongside
0–14-day records (they appear together sorted by urgency).

Both CSV output files are sorted by `days_remaining` ascending (most urgent
first), with tier as a tiebreaker.

---

## 5. Known data caveats (read before trusting the numbers)

- **Status is sourced exclusively from the Twilio call-progress journey**
  (`twilio_webhook_events.csv`'s `event` column), never from
  `conversations.status`. If a conversation's `conversation_id` has no
  matching row in `twilio_webhook_events.csv`, **Status is left blank** —
  it is not guessed or backfilled from anything else.
  `twilio_webhook_events.csv` only has 128 rows and covers a handful of
  agents; **agent 1060 currently has zero matches**, so running the
  report for 1060 today will produce an entirely blank Status column.
  That's expected, not a bug — it'll start populating automatically, no
  code changes needed, once Twilio coverage exists for that agent.
- **Call duration is sourced from `call_logs.metrics.total_duration_ms`,
  not `end_timestamp`.** Re-verified against the fuller dataset:
  `end_timestamp` is frequently identical to `start_timestamp` (zero
  duration) or earlier than it (negative duration), and doesn't
  correlate with the real call length recorded in `call_logs`. It's
  epoch-millisecond UTC like `start_timestamp` and converts to a
  technically valid date, but the *value itself* isn't a trustworthy
  call-end moment — so it's still excluded from duration math.
  (`start_timestamp` is reliable, and is what drives the Call Date /
  `--start-date`/`--end-date` filtering.)
- **Contact Number is partially recoverable, not fully.** ~95% of rows
  arrive as Excel scientific notation (e.g. `"6.39178E+11"`), which only
  keeps 5-6 significant digits — the real trailing digits were lost
  *upstream*, before this script ever sees the data, and can't be
  reconstructed from this file alone. The Call Detail Log now has a
  **Contact Number Reliability** column that's explicit about this:
  - `Complete` — the number arrived uncorrupted and was normalized to
    `63XXXXXXXXXX`.
  - `Complete (recovered from Twilio)` — the number was corrupted in
    `conversations.csv`, but `twilio_webhook_events.csv` had a matching
    call with the true number in its `To` field, so that was used
    instead.
  - `TRUNCATED - only first N digits are real, rest lost upstream` — no
    Twilio match existed to recover it, so the (zero-padded, incomplete)
    number is shown as-is rather than presented as if it were complete.
    Don't use these for actual outreach without going back to Globe's
    source system.
- **Priority Tier is blank in EOD mode.** `call_config` is `"{}"` (empty)
  for every agent-1060 row in the EOD data, so there's no `days_remaining`
  to derive urgency from in that mode. Wire this up once that field is
  populated for this agent. The standalone Priority List mode
  (`--mode priority-list`) does not have this limitation — it computes
  tiers directly from the `exp_date` column in the customer list workbook.
- **Priority List mode now validates every record.** Invalid records
  (bad phone format, unparseable date, duplicates) are written to the
  **Invalid Data** sheet of the Validation Report with a specific reason.
  The Priority List workbook itself contains only validated records
  (0–14 days remaining). The Validation Report also captures expired and
  beyond-window records in separate sheets.
- **`call_logs` schema varies by agent.** Agent 1060 stores it as
  `{"metrics": {"total_duration_ms": ...}}`. Other agents (confirmed on
  agent 37, among others) store it as a list of turn-by-turn bot/user
  events instead — a different shape entirely. Duration extraction
  handles this defensively (returns blank rather than crashing) but
  doesn't currently parse that alternate schema for duration; that's a
  known gap if/when this pipeline is pointed at those agents.
- **LLM Inference Cost, P0/P1 issue counts** are shown as `N/A` — no
  source data currently supports them.