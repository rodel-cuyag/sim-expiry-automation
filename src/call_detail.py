"""
call_detail.py
----------------
Builds the "Call Detail Log" sheet: one row per individual call, matching
the columns from the Globe SIM Expiry plan's call detail log template.
"""

import pandas as pd


def _blank_if_missing(value):
    """Turns NaN into a real Python None so openpyxl writes a blank cell
    instead of the literal string 'nan'."""
    return None if pd.isna(value) else value


def _agreed_to_keep_sim(row):
    """Yes/No/N/A based on the KPI-derived sim_retention_success flag."""
    value = row.get("sim_retention_success")
    if pd.isna(value):
        return "N/A"
    return "Yes" if bool(value) else "No"


def _map_status(twilio_status):
    """
    Maps Twilio call stages to display-friendly status labels.

    Mapping:
        completed, in-progress -> Connected
        no-answer -> No Answer
        busy -> Busy
        failed -> Failed
        ringing -> Ringing
        initiated -> Initiated
    """
    if pd.isna(twilio_status):
        return None

    status_map = {
        "completed": "Connected",
        "in-progress": "Connected",
        "no-answer": "No Answer",
        "busy": "Busy",
        "failed": "Failed",
        "ringing": "Ringing",
        "initiated": "Initiated",
    }

    return status_map.get(twilio_status, twilio_status)


def _disposition_code(row):
    """
    Derives disposition code from KPI call_completed AND Twilio status.

    Logic:
        - call_completed == True AND Twilio connected -> COMPLETED
        - call_completed == True BUT Twilio not connected -> PARTIAL
        - call_completed == False + Twilio connected -> PARTIAL
        - call_completed == False + Twilio no-answer -> NO_ANSWER
        - call_completed == False + Twilio busy -> BUSY
        - call_completed == False + Twilio failed -> FAILED
        - No KPI data -> N/A

    This prevents the bug where KPI says "completed" but Twilio shows "failed",
    which would incorrectly report COMPLETED when the call never connected.
    """
    call_completed = row.get("call_completed")
    twilio_status = row.get("twilio_final_status")

    # No KPI data available
    if pd.isna(call_completed):
        return "N/A"

    # Call completed in KPI - must also verify Twilio connection
    if call_completed:
        if pd.isna(twilio_status):
            return "N/A"  # Can't verify without Twilio

        if twilio_status in ["completed", "in-progress"]:
            return "COMPLETED"  # Both KPI and Twilio confirm success
        else:
            return "PARTIAL"  # KPI thinks complete but Twilio shows disconnect

    # Call not completed in KPI - check Twilio for reason
    if pd.isna(twilio_status):
        return "N/A"

    if twilio_status in ["completed", "in-progress"]:
        return "PARTIAL"  # Connected but ended abruptly
    elif twilio_status == "no-answer":
        return "NO_ANSWER"
    elif twilio_status == "busy":
        return "BUSY"
    elif twilio_status == "failed":
        return "FAILED"
    else:
        return "N/A"


def build_call_detail_log(working_table: pd.DataFrame) -> pd.DataFrame:
    """
    Transforms the merged working table into the final Call Detail Log
    DataFrame, ready to write to Excel.

    Status: sourced ONLY from the Twilio call-progress journey
    (twilio_final_status, derived in preprocessing.extract_twilio_details
    from twilio_webhook_events.csv). Mapped to display-friendly values:
    "Connected", "No Answer", "Busy", "Failed", etc. If a conversation_id
    has no matching Twilio events, Status is left blank.

    Disposition Code: derived from BOTH KPI call_completed AND Twilio status
    to determine the outcome. Both must confirm success for COMPLETED;
    otherwise returns PARTIAL, NO_ANSWER, BUSY, FAILED, or N/A.
    """
    df = working_table.copy()

    log = pd.DataFrame({
        "Conversation ID": df["conversation_id"],
        "Contact Number": df["contact_number_clean"],
        "Status": df["twilio_final_status"].apply(_map_status).apply(_blank_if_missing),
        "Disposition Code": df.apply(_disposition_code, axis=1),
        "Call Duration (sec)": df["call_duration_sec"],
        "Agreed to Keep SIM Active": df.apply(_agreed_to_keep_sim, axis=1),
        "Customer Disposition": df.get("customer_disposition", pd.Series(dtype=object)),
        "Non-Retention Reason": df.get("non_retention_reason", pd.Series(dtype=object)),
        "Call Date (PHT)": df["start_dt_pht"].dt.date,
        "Call Time (PHT)": df["start_dt_pht"].dt.strftime("%H:%M:%S"),
    })

    return log.sort_values(["Call Date (PHT)", "Call Time (PHT)"]).reset_index(drop=True)