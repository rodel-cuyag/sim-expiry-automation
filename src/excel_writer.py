"""
excel_writer.py
-----------------
Writes report DataFrames into formatted .xlsx workbooks using openpyxl.

Note: values here are pre-computed in Python (not live Excel formulas).
These are operational snapshot reports generated fresh each run from
source data, rather than financial models meant to be edited live in
Excel — so static, correct values are the right choice here.
"""

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
import pandas as pd

HEADER_FILL = PatternFill("solid", start_color="1F4E78", end_color="1F4E78")
HEADER_FONT = Font(name="Arial", bold=True, color="FFFFFF")
BODY_FONT = Font(name="Arial")


def resolve_output_path(path: Path) -> Path:
    """
    If *path* already exists, append *(1)*, *(2)*, etc. before the
    extension so the existing file is never silently overwritten.
    """
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    n = 1
    while True:
        candidate = parent / f"{stem} ({n}){suffix}"
        if not candidate.exists():
            return candidate
        n += 1


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
        if not df.empty:
            col_len = df[col].astype(str).str.len().max()
            col_len = 0 if pd.isna(col_len) else col_len
        else:
            col_len = 0
        max_len = max(col_len, len(str(col)))
        ws.column_dimensions[get_column_letter(i)].width = min(max_len + 4, 45)

    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.font = BODY_FONT

    ws.freeze_panes = "A2"


def write_report(eod_df: pd.DataFrame, call_detail_df: pd.DataFrame, output_path):
    """Creates the EOD-mode 2-sheet workbook: 'EOD Report' and 'Call Detail Log'."""
    wb = Workbook()

    eod_sheet = wb.active
    eod_sheet.title = "EOD Report"
    _write_dataframe(eod_sheet, eod_df)

    detail_sheet = wb.create_sheet("Call Detail Log")
    _write_dataframe(detail_sheet, call_detail_df)

    wb.save(output_path)
    return output_path


def write_priority_list_sheet(df: pd.DataFrame, output_path, sheet_name: str, date_columns=None):
    """
    Creates a single-sheet workbook for the valid Priority List.
    date_columns: optional list of column names to format as plain
    dates (YYYY-MM-DD) instead of openpyxl's default datetime display.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    _write_dataframe(ws, df)
    _apply_date_format(ws, list(df.columns), date_columns)
    wb.save(output_path)
    return output_path


_SHEET_TITLES = {
    "summary": "Summary",
    "invalid": "Invalid Data",
    "expired": "Expired Numbers",
    # EOD validation sheet titles
    "join_summary": "Join Summary",
    "field_completeness": "Field Completeness",
    "calculation_audit": "Calculation Audit",
    "data_quality_issues": "Data Quality Issues",
}


def write_validation_report(sheets: dict, output_path, date_columns=None):
    """
    Creates a multi-sheet validation report workbook.
    Each key in *sheets* is a sheet identifier; the value is a DataFrame.
    The first key determines the first (active) sheet; subsequent keys become
    additional sheets in iteration order.
    """
    keys = list(sheets.keys())
    if not keys:
        raise ValueError("At least one sheet is required")

    wb = Workbook()
    first_key = keys[0]
    wb.active.title = _SHEET_TITLES.get(first_key, first_key.replace("_", " ").title())
    _write_dataframe(wb.active, sheets[first_key])
    if date_columns:
        _apply_date_format(wb.active, list(sheets[first_key].columns), date_columns)

    for key in keys[1:]:
        title = _SHEET_TITLES.get(key, key.replace("_", " ").title())
        ws = wb.create_sheet(title)
        _write_dataframe(ws, sheets[key])
        if date_columns:
            _apply_date_format(ws, list(sheets[key].columns), date_columns)

    wb.save(output_path)
    return output_path


# ── CSV writers (Priority List) ───────────────────────────────────


def write_priority_list_csv(df: pd.DataFrame, output_path):
    """Write the Priority List (valid records) to a CSV file."""
    df.to_csv(output_path, index=False)
    return output_path


# ── Excel helpers ─────────────────────────────────────────────────


def _apply_date_format(ws, column_names, date_columns):
    """Apply YYYY-MM-DD formatting to cells in date_columns (skip header row)."""
    if not date_columns:
        return
    for col_name in date_columns:
        if col_name not in column_names:
            continue
        col_letter = get_column_letter(column_names.index(col_name) + 1)
        for cell in ws[col_letter][1:]:
            cell.number_format = "YYYY-MM-DD"