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


def build_call_detail_log(working_table: pd.DataFrame) -> pd.DataFrame:
    """
    Transforms the merged working table into the final Call Detail Log
    DataFrame, ready to write to Excel.

    Status: sourced ONLY from the Twilio call-progress journey
    (twilio_final_status, derived in preprocessing.extract_twilio_details
    from twilio_webhook_events.csv). There is intentionally no fallback
    to conversations.status anymore — if a conversation_id has no
    matching Twilio events, Status is left blank rather than guessed.
    """
    df = working_table.copy()

    log = pd.DataFrame({
        "Conversation ID": df["conversation_id"],
        "Contact Number": df["contact_number_clean"],
        "Contact Number Reliability": df["contact_number_reliability"],
        "Status": df["twilio_final_status"].apply(_blank_if_missing),
        "Call Duration (sec)": df["call_duration_sec"],
        "Agreed to Keep SIM Active": df.apply(_agreed_to_keep_sim, axis=1),
        "Customer Disposition": df.get("customer_disposition", pd.Series(dtype=object)),
        "Non-Retention Reason": df.get("non_retention_reason", pd.Series(dtype=object)),
        "User Sentiment": df.get("user_sentiment", pd.Series(dtype=object)),
        # Tier is left blank on purpose: call_config carries no
        # days_remaining data for this agent, so there's nothing to
        # derive urgency from. Fill this in once that field is populated.
        "Priority Tier": None,
        "Call Date (PHT)": df["start_dt_pht"].dt.date,
        "Call Time (PHT)": df["start_dt_pht"].dt.strftime("%H:%M:%S"),
    })

    return log.sort_values(["Call Date (PHT)", "Call Time (PHT)"]).reset_index(drop=True)