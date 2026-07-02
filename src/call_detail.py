"""
call_detail.py
----------------
Builds the "Call Detail Log" sheet: one row per individual call, matching
the columns from the Globe SIM Expiry plan's call detail log template.
"""

import pandas as pd


def _resolve_status(row) -> str:
    """
    Status priority: Twilio's detailed event status wins when present,
    otherwise fall back to the coarse conversations.status field.

    For agent_id = 1060 specifically, Twilio has 0 matching records today,
    so this will fall back to conversations.status for ~100% of rows.
    That's shown as-is (completed / in_progress / failed) rather than
    guessed/remapped into Busy/No Answer/etc, since we have no data to
    back that remap. Once Twilio coverage improves for this agent, this
    function will automatically start using it with no code changes needed.
    """
    if pd.notna(row.get("twilio_final_status")):
        return row["twilio_final_status"]
    return row.get("status", "unknown")


def _clean_contact_number(value):
    """
    contact_number arrives pre-corrupted in the source CSV as scientific
    notation text (e.g. "6.39178E+11") — an artifact from being opened/
    saved in Excel upstream before export. Parse through float -> int to
    recover the real digits, since directly int()'ing the string fails.
    """
    if pd.isna(value):
        return None
    try:
        return str(int(float(value)))
    except (ValueError, TypeError):
        return str(value)  # fallback: leave as-is if truly unparseable


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
    """
    df = working_table.copy()

    log = pd.DataFrame({
        "Conversation ID": df["conversation_id"],
        "Contact Number": df["contact_number"].apply(_clean_contact_number),
        "Status": df.apply(_resolve_status, axis=1),
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

    return log.sort_values("Call Time (PHT)").reset_index(drop=True)
