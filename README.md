# SIM Expiry Voicebot — Report Automation (EOD Report + Priority List)

Generates one of two reports:

- **EOD Report** — a 2-sheet Excel workbook (**EOD Report** + **Call Detail
  Log**) from 3 raw source CSVs (`conversations`, `kpi_results`,
  `twilio_webhook_events`), filtered to a single agent and a calling-day range.

- **Priority List** — a single-sheet workbook with urgency-tiered phone
  numbers derived from the customer list workbook provided by Globe.

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
   The generated `.xlsx` lands in `output/eod/` (EOD mode) or
   `output/customer_list/` (Priority List mode).

   Or run `.\run_samples.ps1` (Windows PowerShell) to exercise several
   scenarios at once — default run, single day, multi-day range, a
   different agent, and the date-validation error cases.

---

## 2. Tools used

| Tool | Purpose |
|---|---|
| Python 3.10+ | Core language |
| `pandas` | CSV loading, cleaning, joining, aggregation |
| `openpyxl` | Writing formatted Excel workbooks (EOD: 2-sheet / Priority List: single-sheet) |
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
│   ├── customer_list/         → input: sim_expiry_customer_list.xlsx (Priority List mode)
│   └── eod/                   → input: 3 CSVs (EOD mode)
├── output/
│   ├── customer_list/         → generated: SIM_Expiry_Priority_List_{date}.xlsx
│   └── eod/                   → generated: SIM_Expiry_EOD_Report_{agent_id}_{date}.xlsx
├── src/
│   ├── config.py              → all settings in one place (paths, AGENT_ID, timezone, filename templates)
│   ├── validators.py          → validates date CLI args (--start-date/--end-date, --as-of-date)
│   ├── data_loader.py         → reads input files off disk; validates they exist first
│   ├── progress.py            → spinning "loading..." animation in the terminal
│   ├── preprocessing.py       → cleans data, parses JSON, filters to one agent, joins 3 sources (EOD mode)
│   ├── call_detail.py         → builds the "Call Detail Log" sheet (one row per call)
│   ├── eod_report.py          → builds the "EOD Report" sheet (aggregated summary)
│   ├── customer_list.py       → builds the Priority List (phone variants, days_remaining, urgency tiers)
│   └── excel_writer.py        → writes DataFrames to formatted .xlsx (2-sheet or single-sheet)
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
python main.py --mode priority-list --input path/to/other.xlsx    # override input file
```

- `--as-of-date`: reference date in `YYYY-MM-DD` used to compute
  `days_remaining`. Defaults to today in PHT.
- `--input`: override the customer list workbook path
  (default: `data/customer_list/sim_expiry_customer_list.xlsx`).

**Output:** `SIM_Expiry_Priority_List_{date}.xlsx` in `output/customer_list/`.

**Priority Tier definitions** (per the Globe SIM Expiry Scale-Up plan):

| Tier | Days remaining | Meaning |
|------|---------------|---------|
| EXPIRED | < 0 | Past expiry |
| TIER 1 | 0–3 | Urgent |
| TIER 2 | 4–7 | Soon |
| TIER 3 | 8+ | Watch |

The output is sorted by `days_remaining` ascending (most urgent first), with tier as a tiebreaker.

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
- **Priority List mode is only as good as the input workbook.** The
  customer list workbook is a manual/delivered artifact from Globe. If
  `exp_date` is missing, malformed, or out of date, every derived field
  (`days_remaining`, `priority_tier`) will be wrong. The script does not
  validate or sanity-check `exp_date` beyond parsing it as a date.
- **`call_logs` schema varies by agent.** Agent 1060 stores it as
  `{"metrics": {"total_duration_ms": ...}}`. Other agents (confirmed on
  agent 37, among others) store it as a list of turn-by-turn bot/user
  events instead — a different shape entirely. Duration extraction
  handles this defensively (returns blank rather than crashing) but
  doesn't currently parse that alternate schema for duration; that's a
  known gap if/when this pipeline is pointed at those agents.
- **LLM Inference Cost, P0/P1 issue counts** are shown as `N/A` — no
  source data currently supports them.