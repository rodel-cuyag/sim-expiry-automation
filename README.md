# SIM Expiry Voicebot — EOD Report Automation

Generates a 2-sheet Excel workbook (**EOD Report** + **Call Detail Log**) from
the 3 raw source CSVs (`conversations`, `kpi_results`, `twilio_webhook_events`),
filtered to a single agent and a single calling-day **range** (a single day is
just a range of 1).

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

7. **Add your input CSVs** into the `data/` folder, named exactly:
   - `data/conversations.csv`
   - `data/kpi_results.csv`
   - `data/twilio_webhook_events.csv`

8. **Run it**
```bash
   python main.py
```
   The generated `.xlsx` lands in `output/`.

   Or run `.\run_samples.ps1` (Windows PowerShell) to exercise several
   scenarios at once — default run, single day, multi-day range, a
   different agent, and the date-validation error cases.

---

## 2. Tools used

| Tool | Purpose |
|---|---|
| Python 3.10+ | Core language |
| `pandas` | CSV loading, cleaning, joining, aggregation |
| `openpyxl` | Writing the formatted 2-sheet Excel workbook |
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
├── data/                    → drop your 3 input CSVs here
├── output/                  → generated Excel reports land here
├── src/
│   ├── config.py             → all settings in one place (AGENT_ID, file paths, timezone, output filename templates)
│   ├── validators.py         → validates --start-date/--end-date (format, both-or-neither, start <= end)
│   ├── data_loader.py        → reads the 3 CSVs off disk; checks they exist first and gives a clear error if not
│   ├── progress.py           → shows a spinning "loading..." animation in the terminal while CSVs load
│   ├── preprocessing.py      → cleans the data (contact numbers, durations), parses the JSON columns, filters to one agent, joins the 3 sources together
│   ├── call_detail.py        → builds the "Call Detail Log" sheet (one row per call)
│   └── eod_report.py         → builds the "EOD Report" sheet (aggregated summary for the whole date range)
│   └── excel_writer.py       → takes those two tables and writes the final formatted .xlsx
├── main.py                   → the file you actually run; it calls everything above in order
├── run_samples.ps1           → optional: runs several scenarios in one go (see script comments)
├── requirements.txt          → the 2 packages needed (pandas, openpyxl)
└── README.md                 → setup instructions and known data caveats
```

Each module has exactly one job, so you can swap any piece (e.g. point
`data_loader.py` at a database instead of CSVs later) without touching the
others.

---

## 4. Usage

```bash
python main.py                                                # most recent date in the data, agent from config.py
python main.py --start-date 2026-06-25 --end-date 2026-06-29  # a date range -> one aggregated EOD Report row for the whole period
python main.py --start-date 2026-06-29 --end-date 2026-06-29  # a single day (range of 1)
python main.py --agent-id 1060 --start-date 2026-06-25 --end-date 2026-06-29
```

`--start-date` and `--end-date` must be given together (or both omitted).
Both must be valid `YYYY-MM-DD` dates, and `--start-date` must be on or
before `--end-date` — otherwise the script prints a clear error and exits
without writing a file.

**Output naming:** single-day runs produce
`SIM_Expiry_EOD_Report_{agent_id}_{date}.xlsx`; multi-day ranges produce
`SIM_Expiry_EOD_Report_{agent_id}_{start_date}_to_{end_date}.xlsx`.

**EOD Report for a range:** the EOD Report sheet is **one aggregated row**
covering the entire `--start-date`/`--end-date` period (not one row per
day), with a `Report Period` field showing the date span and a
`Days in Range` field showing its length. The Call Detail Log sheet lists
every call in that period and keeps a `Call Date (PHT)` column so you can
still tell which day each row belongs to.

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
- **Priority Tier is blank.** `call_config` is `"{}"` (empty) for every
  agent-1060 row, so there's no `days_remaining` to derive urgency from.
  Wire this up once that field is populated for this agent.
- **`call_logs` schema varies by agent.** Agent 1060 stores it as
  `{"metrics": {"total_duration_ms": ...}}`. Other agents (confirmed on
  agent 37, among others) store it as a list of turn-by-turn bot/user
  events instead — a different shape entirely. Duration extraction
  handles this defensively (returns blank rather than crashing) but
  doesn't currently parse that alternate schema for duration; that's a
  known gap if/when this pipeline is pointed at those agents.
- **LLM Inference Cost, P0/P1 issue counts** are shown as `N/A` — no
  source data currently supports them.