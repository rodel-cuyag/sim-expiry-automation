# SIM Expiry Voicebot — EOD Report Automation

Generates a 2-sheet Excel workbook (**EOD Report** + **Call Detail Log**) from
the 3 raw source CSVs (`conversations`, `kpi_results`, `twilio_webhook_events`),
filtered to a single agent and a single calling day.

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
├── data/                       # input CSVs go here
│   ├── conversations.csv
│   ├── kpi_results.csv
│   └── twilio_webhook_events.csv
├── output/                     # generated .xlsx reports land here
├── src/
│   ├── config.py                # all constants/paths — AGENT_ID lives here
│   ├── data_loader.py           # reads raw CSVs, nothing else
│   ├── preprocessing.py         # cleans, parses JSON, filters agent, joins 3 sources
│   ├── call_detail.py           # builds the Call Detail Log sheet
│   ├── eod_report.py            # builds the EOD Report sheet
│   └── excel_writer.py          # writes both sheets to one formatted .xlsx
├── main.py                      # CLI entry point — orchestrates the pipeline
├── requirements.txt
└── README.md
```

Each module has exactly one job, so you can swap any piece (e.g. point
`data_loader.py` at a database instead of CSVs later) without touching the
others.

---

## 4. Usage

```bash
python main.py                       # most recent date in the data, agent from config.py
python main.py --date 2026-06-11     # a specific calling day
python main.py --agent-id 1060       # override the agent without editing code
```

---

## 5. Known data caveats (read before trusting the numbers)

- **Twilio has 0 matching records for agent_id 1060.** `twilio_webhook_events.csv`
  only has 128 rows total and none belong to this agent today. The script is
  built to *prefer* Twilio's detailed status when a match exists (useful for
  other agents / future data), but for 1060 it falls back to the raw
  `conversations.status` (`completed` / `in_progress` / `failed`) for 100%
  of rows — shown as-is, not guessed/remapped into Busy/No Answer.
- **Priority Tier is blank.** `call_config` is `"{}"` (empty) for every
  agent-1060 row, so there's no `days_remaining` to derive urgency from.
  Wire this up once that field is populated for this agent.
- **Call duration is sourced from `call_logs.metrics.total_duration_ms`,
  not `end_timestamp`.** The `end_timestamp` column in the source CSV is
  unreliable — many rows share identical placeholder values that land
  *before* `start_timestamp`, which produced nonsense negative durations
  during testing.
- **Contact Number is pre-corrupted upstream.** The source CSV already
  stores phone numbers as scientific-notation text (e.g. `"6.39178E+11"`),
  which only preserves 6 significant figures — the real trailing digits
  are permanently lost before this script ever sees the data. The script
  cleans up the *display* (no more `E+11` formatting) but cannot recover
  the missing digits. Don't use this column for actual outreach without
  going back to Globe's source system for the real numbers.
- **LLM Inference Cost, P0/P1 issue counts, No Answer / Busy breakdown**
  are shown as `N/A` — no source data currently supports them.
