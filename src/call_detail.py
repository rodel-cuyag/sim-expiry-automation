"""
call_detail.py
----------------
Builds the "Call Detail Log" sheet: one row per individual call, matching
the columns from the Globe SIM Expiry plan's call detail log template.
"""

import pandas as pd

# Priority tiers for picking the "best" record among same-day duplicate
# dials to the same number. "Connected" always wins outright. Busy/No
# Answer/Failed are no longer ranked against each other - among those (or
# any other non-blank status), the latest Call Time wins instead. A blank/
# unmatched status is always lowest priority.
_STATUS_PRIORITY = {"Connected": 0}
_NON_BLANK_STATUS_PRIORITY = 1
_BLANK_STATUS_PRIORITY = 2


def _blank_if_missing(value):
    """Turns NaN into a real Python None so openpyxl writes a blank cell
    instead of the literal string 'nan'."""
    return None if pd.isna(value) else value


def _call_completed_display(value):
    """Yes/No based on the KPI-derived call_completed flag; blank if missing."""
    if pd.isna(value):
        return None
    return "Yes" if bool(value) else "No"


def _agreed_to_keep_sim(row):
    """Yes/No/N/A based on the KPI-derived sim_retention_success flag."""
    value = row.get("sim_retention_success")
    if pd.isna(value):
        return "N/A"
    return "Yes" if bool(value) else "No"


def _format_question_topics(value):
    """Joins a list of topic strings into a comma-separated display string.
    Empty lists and missing values both render as a blank cell."""
    if not isinstance(value, list) or not value:
        return None
    return ", ".join(value)


def _map_status(twilio_status):
    """
    Maps Twilio call stages to display-friendly status labels.

    Mapping:
        completed, in-progress -> Connected
        no-answer -> No Answer
        busy -> Busy
        failed -> Failed
        ringing -> No Answer
    """
    if pd.isna(twilio_status):
        return None

    status_map = {
        "completed": "Connected",
        "in-progress": "Connected",
        "no-answer": "No Answer",
        "busy": "Busy",
        "failed": "Failed",
        "ringing": "No Answer",
    }

    return status_map.get(twilio_status, twilio_status)


def _dedupe_duplicate_calls(log: pd.DataFrame) -> pd.DataFrame:
    """
    Collapses repeat same-day dials to the same Contact Number down to one
    record per (Contact Number, Call Date (PHT)):

      - "Connected" always wins outright if present among the duplicates.
      - Otherwise (including ties among Busy/No Answer/Failed, or repeats
        of the same status), keep the latest record by Call Time.

    Rows with a blank Contact Number are never collapsed against each
    other (no reliable way to confirm they're the same customer).
    """
    has_number = log["Contact Number"].notna()
    dedupable = log[has_number].copy()
    passthrough = log[~has_number]

    if dedupable.empty:
        return log

    dedupable["_priority"] = dedupable["Status"].apply(
        lambda s: _BLANK_STATUS_PRIORITY if pd.isna(s)
        else _STATUS_PRIORITY.get(s, _NON_BLANK_STATUS_PRIORITY)
    )
    dedupable = dedupable.sort_values(
        ["Contact Number", "Call Date (PHT)", "_priority", "Call Time (PHT)"],
        ascending=[True, True, True, False],
    )
    deduped = dedupable.drop_duplicates(
        subset=["Contact Number", "Call Date (PHT)"], keep="first"
    ).drop(columns="_priority")

    return pd.concat([deduped, passthrough], ignore_index=True)


def build_raw_call_rows(working_table: pd.DataFrame) -> pd.DataFrame:
    """
    Transforms the merged working table into one row per individual call,
    before same-day duplicate-number collapsing. Exposed separately from
    build_call_detail_log so callers (e.g. the validation report) can audit
    which rows got collapsed as duplicates.

    Status: sourced exclusively from the Twilio call-progress journey
    (twilio_final_status, derived in preprocessing.extract_twilio_details
    from twilio_webhook_events.csv). Mapped to display-friendly values:
    "Connected", "No Answer", "Busy", "Failed". If a conversation_id has no
    matching Twilio events, Status is left blank.
    """
    df = working_table.copy()

    return pd.DataFrame({
        "Conversation ID": df["conversation_id"],
        "Contact Number": df["contact_number_clean"],
        "Status": df["twilio_final_status"].apply(_map_status).apply(_blank_if_missing),
        "Call Duration (sec)": df["call_duration_sec"],
        "Agreed to Keep SIM Active": df.apply(_agreed_to_keep_sim, axis=1),
        "Customer Disposition": df.get("customer_disposition", pd.Series(dtype=object)),
        "Non-Retention Reason": df.get("non_retention_reason", pd.Series(dtype=object)),
        "Question Topics": df.get("question_topics", pd.Series(dtype=object)).apply(_format_question_topics),
        "Call Date (PHT)": df["start_dt_pht"].dt.date,
        "Call Time (PHT)": df["start_dt_pht"].dt.strftime("%H:%M:%S"),
        # Extra column beyond the reference format's 10 columns — appended
        # trailing so columns A-J still match the reference exactly.
        "Call Completed": df.get("call_completed", pd.Series(dtype=object)).apply(_call_completed_display),
    })


def build_call_detail_log(working_table: pd.DataFrame) -> pd.DataFrame:
    """
    Transforms the merged working table into the final Call Detail Log
    DataFrame, ready to write to Excel (one row per Contact Number per
    Call Date - see _dedupe_duplicate_calls).
    """
    log = build_raw_call_rows(working_table)
    log = _dedupe_duplicate_calls(log)
    return log.sort_values(["Call Date (PHT)", "Call Time (PHT)"]).reset_index(drop=True)