"""
main.py
--------
Entry point. Run this file to generate the SIM Expiry EOD Report + Call
Detail Log Excel workbook.

Usage:
    python main.py                       # most recent date in the data, default agent
    python main.py --date 2026-06-11     # specific date
    python main.py --agent-id 1060       # override the agent (still dynamic)
"""

import argparse
import datetime
import sys

from src import config, preprocessing, call_detail, eod_report, excel_writer
from src.data_loader import MissingInputFileError


def parse_args():
    parser = argparse.ArgumentParser(description="Generate SIM Expiry EOD Report + Call Detail Log.")
    parser.add_argument("--date", type=str, default=None, help="Report date, format YYYY-MM-DD. Defaults to the most recent date found in the data.")
    parser.add_argument("--agent-id", type=int, default=config.AGENT_ID, help="Agent ID to report on (defaults to config.AGENT_ID).")
    return parser.parse_args()


def run(agent_id: int, report_date: datetime.date = None):
    # 1. Load + clean + merge the 3 source files, filtered to this agent.
    working_table = preprocessing.build_working_table(agent_id=agent_id)

    if working_table.empty:
        print(f"No conversations found for agent_id={agent_id}. Nothing to report.")
        sys.exit(1)

    # 2. Build the Call Detail Log (all calls, not date-filtered yet).
    detail_log = call_detail.build_call_detail_log(working_table)

    # 3. Default to the most recent date present, if none was given.
    if report_date is None:
        report_date = detail_log["Call Date (PHT)"].max()
        print(f"No --date given, defaulting to most recent date in data: {report_date}")

    # 4. Build the EOD summary for that single date.
    eod_df = eod_report.build_eod_report(detail_log, report_date, agent_id)

    # 5. Slice the detail log down to just that date for the sheet.
    day_detail_log = detail_log[detail_log["Call Date (PHT)"] == report_date].drop(columns=["Call Date (PHT)"])

    # 6. Write both sheets to a single Excel workbook.
    config.OUTPUT_DIR.mkdir(exist_ok=True)
    filename = config.OUTPUT_FILENAME_TEMPLATE.format(agent_id=agent_id, date=report_date)
    output_path = config.OUTPUT_DIR / filename
    excel_writer.write_report(eod_df, day_detail_log, output_path)

    print(f"Report generated: {output_path}")
    return output_path


if __name__ == "__main__":
    args = parse_args()
    parsed_date = datetime.datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else None
    try:
        run(agent_id=args.agent_id, report_date=parsed_date)
    except MissingInputFileError as e:
        print(e)
        sys.exit(1)