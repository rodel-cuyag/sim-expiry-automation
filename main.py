"""
main.py
--------
Entry point. Run this file to generate either:
  - Mode 1 "eod": SIM Expiry EOD Report + Call Detail Log workbook
  - Mode 2 "priority-list": SIM Expiry Priority List workbook

Usage:
    python main.py                                                       # EOD mode (default), most recent date, default agent
    python main.py --start-date 2026-06-25 --end-date 2026-06-29         # EOD mode, a date range
    python main.py --agent-id 1060 --start-date 2026-06-25 --end-date 2026-06-29

    python main.py --mode priority-list                                  # Priority List mode, as-of today (PHT)
    python main.py --mode priority-list --as-of-date 2026-07-10          # Priority List mode, as-of a specific date
    python main.py --mode priority-list --input path/to/other_list.xlsx  # override the input file
"""

import argparse
import sys
from datetime import datetime

import pandas as pd

from src import config, preprocessing, call_detail, eod_report, excel_writer, validators, customer_list, data_loader
from src.data_loader import MissingInputFileError


def parse_args():
    parser = argparse.ArgumentParser(description="Generate SIM Expiry reports.")
    parser.add_argument(
        "--mode", choices=["eod", "priority-list"], default="eod",
        help="Which report to generate: 'eod' (EOD Report + Call Detail Log, default) "
             "or 'priority-list' (SIM Expiry Priority List from the customer list workbook).",
    )

    # --- Mode 1 (eod) args ---
    parser.add_argument(
        "--start-date", type=str, default=None,
        help="[eod mode] Start of the report period, format YYYY-MM-DD. Must be given together with --end-date. "
             "Omit both to default to the most recent single day found in the data.",
    )
    parser.add_argument(
        "--end-date", type=str, default=None,
        help="[eod mode] End of the report period, format YYYY-MM-DD (inclusive). Must be given together with --start-date.",
    )
    parser.add_argument(
        "--agent-id", type=int, default=config.AGENT_ID,
        help="[eod mode] Agent ID to report on (defaults to config.AGENT_ID).",
    )

    # --- Mode 2 (priority-list) args ---
    parser.add_argument(
        "--as-of-date", type=str, default=None,
        help="[priority-list mode] Reference date (YYYY-MM-DD) used to compute days_remaining. "
             "Defaults to today in PHT.",
    )
    parser.add_argument(
        "--input", type=str, default=None,
        help="[priority-list mode] Path to the customer list workbook, overriding config.CUSTOMER_LIST_XLSX.",
    )

    return parser.parse_args()


# ── Mode 1: EOD Report ────────────────────────────────────────────

def run_eod(agent_id: int, start_date=None, end_date=None):
    # 1. Load + clean + merge the 3 source files, filtered to this agent.
    working_table = preprocessing.build_working_table(agent_id=agent_id)

    if working_table.empty:
        print(f"No conversations found for agent_id={agent_id}. Nothing to report.")
        sys.exit(1)

    # 2. Build the Call Detail Log (all calls, not date-filtered yet).
    detail_log = call_detail.build_call_detail_log(working_table)

    # 3. Default to the most recent single day present, if no range was given.
    if start_date is None:
        start_date = end_date = detail_log["Call Date (PHT)"].max()
        print(f"No --start-date/--end-date given, defaulting to most recent date in data: {start_date}")

    # 4. Build the aggregated EOD summary covering the whole period.
    eod_df = eod_report.build_eod_report(detail_log, start_date, end_date, agent_id)

    # 5. Slice the detail log down to the report period for the sheet.
    range_detail_log = detail_log[
        (detail_log["Call Date (PHT)"] >= start_date) & (detail_log["Call Date (PHT)"] <= end_date)
    ].reset_index(drop=True)

    # 6. Write both sheets to a single Excel workbook, into output/eod/.
    config.EOD_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if start_date == end_date:
        filename = config.OUTPUT_FILENAME_TEMPLATE_SINGLE.format(agent_id=agent_id, start_date=start_date)
    else:
        filename = config.OUTPUT_FILENAME_TEMPLATE_RANGE.format(agent_id=agent_id, start_date=start_date, end_date=end_date)
    output_path = excel_writer.resolve_output_path(config.EOD_OUTPUT_DIR / filename)
    excel_writer.write_report(eod_df, range_detail_log, output_path)

    print(f"EOD report generated: {output_path}")
    return output_path


# ── Mode 2: Priority List ─────────────────────────────────────────

def run_priority_list(as_of_date=None, input_path=None):
    from pathlib import Path
    input_path = Path(input_path) if input_path else None

    # 1. Validate + load the customer list workbook.
    data_loader.validate_customer_list_file(input_path)
    raw_df = data_loader.load_customer_list(input_path)

    if raw_df.empty:
        print("Customer list is empty. Nothing to report.")
        sys.exit(1)

    # 2. Default as-of-date to today in PHT if not given.
    if as_of_date is None:
        as_of_date = pd.Timestamp.now(tz=config.TIMEZONE).date()
        print(f"No --as-of-date given, defaulting to today (PHT): {as_of_date}")

    # 3. Validate and categorize every record.
    categories = customer_list.categorize_records(raw_df, as_of_date)

    # 4. Build summary statistics.
    total = len(raw_df)
    valid_count = len(categories["valid"])
    invalid_count = len(categories["invalid"])
    expired_count = len(categories["expired"])
    beyond_14_count = len(categories["beyond_14"])

    def pct(n):
        return round(n / total * 100, 1) if total else 0.0

    summary_df = pd.DataFrame({
        "Metric": [
            "Total Records",
            "Valid",
            "Invalid",
            "Expired Numbers",
            "Outside 14-Day Window",
        ],
        "Count": [total, valid_count, invalid_count, expired_count, beyond_14_count],
        "% of Total": [
            100.0,
            pct(valid_count),
            pct(invalid_count),
            pct(expired_count),
            pct(beyond_14_count),
        ],
    })

    # 5. Write Priority List (valid records only).
    config.CUSTOMER_LIST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now_date = datetime.now().date()
    filename = config.CUSTOMER_LIST_OUTPUT_FILENAME_TEMPLATE.format(date=now_date)
    priority_path = excel_writer.resolve_output_path(config.CUSTOMER_LIST_OUTPUT_DIR / filename)

    if categories["valid"].empty:
        print("No valid records found. Priority list not generated.")
    else:
        excel_writer.write_priority_list_sheet(
            categories["valid"],
            priority_path,
            sheet_name="Priority List",
            date_columns=["exp_date"],
        )
        print(f"Priority list generated: {priority_path}")

    # 6. Write Validation Report (4‑sheet workbook).
    validation_filename = config.VALIDATION_OUTPUT_FILENAME_TEMPLATE.format(date=now_date)
    validation_path = excel_writer.resolve_output_path(config.CUSTOMER_LIST_OUTPUT_DIR / validation_filename)

    sheets = {
        "summary": summary_df,
        "invalid": categories["invalid"],
        "expired": categories["expired"],
        "beyond_14": categories["beyond_14"],
    }
    excel_writer.write_validation_report(sheets, validation_path, date_columns=["exp_date"])
    print(f"Validation report generated: {validation_path}")

    return priority_path if not categories["valid"].empty else None


if __name__ == "__main__":
    args = parse_args()

    if args.mode == "priority-list":
        try:
            as_of = validators.parse_single_date(args.as_of_date) if args.as_of_date else None
        except validators.InvalidDateRangeError as e:
            print(f"Invalid --as-of-date: {e}")
            sys.exit(1)

        try:
            run_priority_list(as_of_date=as_of, input_path=args.input)
        except MissingInputFileError as e:
            print(e)
            sys.exit(1)

    else:  # args.mode == "eod"
        try:
            parsed_start, parsed_end = validators.parse_date_range(args.start_date, args.end_date)
        except validators.InvalidDateRangeError as e:
            print(f"Invalid date range: {e}")
            sys.exit(1)

        try:
            run_eod(agent_id=args.agent_id, start_date=parsed_start, end_date=parsed_end)
        except MissingInputFileError as e:
            print(e)
            sys.exit(1)