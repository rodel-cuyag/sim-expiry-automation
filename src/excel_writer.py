"""
excel_writer.py
-----------------
Writes the EOD Report and Call Detail Log DataFrames into a single
formatted .xlsx workbook with 2 sheets, using openpyxl.

Note: values here are pre-computed in Python (not live Excel formulas).
This is an operational snapshot report generated fresh each run from
source CSVs, rather than a financial model meant to be edited live in
Excel — so static, correct values are the right choice here.
"""

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
import pandas as pd

HEADER_FILL = PatternFill("solid", start_color="1F4E78", end_color="1F4E78")
HEADER_FONT = Font(name="Arial", bold=True, color="FFFFFF")
BODY_FONT = Font(name="Arial")


def _write_dataframe(ws, df: pd.DataFrame):
    """Writes a DataFrame to a worksheet with a styled header row and auto-width columns."""
    ws.append(list(df.columns))
    for cell in ws[1]:
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")

    for row in df.itertuples(index=False):
        ws.append(list(row))

    for i, col in enumerate(df.columns, start=1):
        max_len = max(df[col].astype(str).str.len().max() if not df.empty else 0, len(str(col)))
        ws.column_dimensions[get_column_letter(i)].width = min(max_len + 4, 45)

    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.font = BODY_FONT

    ws.freeze_panes = "A2"


def write_report(eod_df: pd.DataFrame, call_detail_df: pd.DataFrame, output_path):
    """Creates the final 2-sheet workbook: 'EOD Report' and 'Call Detail Log'."""
    wb = Workbook()

    eod_sheet = wb.active
    eod_sheet.title = "EOD Report"
    _write_dataframe(eod_sheet, eod_df)

    detail_sheet = wb.create_sheet("Call Detail Log")
    _write_dataframe(detail_sheet, call_detail_df)

    wb.save(output_path)
    return output_path
