"""
main.py
--------
Entry point. Run this file to generate the SIM Expiry EOD Report + Call
Detail Log Excel workbook.

Usage:
    python main.py                                             # most recent date in the data, default agent
    python main.py --start-date 2026-06-25 --end-date 2026-06-29  # a date range
    python main.py --start-date 2026-06-29 --end-date 2026-06-29  # a single day (range of 1)
    python main.py --agent-id 1060 --start-date 2026-06-25 --end-date 2026-06-29
"""

import argparse
import sys

from src import config, preprocessing, call_detail, eod_report, excel_writer, validators
from src.data_loader import MissingInputFileError


def parse_args():
    parser = argparse.ArgumentParser(description="Generate SIM Expiry EOD Report + Call Detail Log.")
    parser.add_argument(
        "--start-date", type=str, default=None,
        help="Start of the report period, format YYYY-MM-DD. Must be given together with --end-date. "
             "Omit both to default to the most recent single day found in the data.",
    )
    parser.add_argument(
        "--end-date", type=str, default=None,
        help="End of the report period, format YYYY-MM-DD (inclusive). Must be given together with --start-date.",
    )
    parser.add_argument("--agent-id", type=int, default=config.AGENT_ID, help="Agent ID to report on (defaults to config.AGENT_ID).")
    return parser.parse_args()


def run(agent_id: int, start_date=None, end_date=None):
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
    #    Call Date (PHT) is kept as a column since a range can span
    #    multiple calling days.
    range_detail_log = detail_log[
        (detail_log["Call Date (PHT)"] >= start_date) & (detail_log["Call Date (PHT)"] <= end_date)
    ].reset_index(drop=True)

    # 6. Write both sheets to a single Excel workbook.
    config.OUTPUT_DIR.mkdir(exist_ok=True)
    if start_date == end_date:
        filename = config.OUTPUT_FILENAME_TEMPLATE_SINGLE.format(agent_id=agent_id, start_date=start_date)
    else:
        filename = config.OUTPUT_FILENAME_TEMPLATE_RANGE.format(agent_id=agent_id, start_date=start_date, end_date=end_date)
    output_path = config.OUTPUT_DIR / filename
    excel_writer.write_report(eod_df, range_detail_log, output_path)

    print(f"Report generated: {output_path}")
    return output_path


if __name__ == "__main__":
    args = parse_args()

    try:
        parsed_start, parsed_end = validators.parse_date_range(args.start_date, args.end_date)
    except validators.InvalidDateRangeError as e:
        print(f"Invalid date range: {e}")
        sys.exit(1)

    try:
        run(agent_id=args.agent_id, start_date=parsed_start, end_date=parsed_end)
    except MissingInputFileError as e:
        print(e)
        sys.exit(1)