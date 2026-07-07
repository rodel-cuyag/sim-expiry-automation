"""
eod_report.py
--------------
Builds the "EOD Report" sheet: aggregate KPIs for a calling-day RANGE
(start_date..end_date, inclusive — a single day is just a range of 1),
following the funnel/metric definitions in the Globe SIM Expiry plan.

Only metrics that can be honestly derived from the available data are
computed. Metrics the source data can't support (e.g. LLM inference
cost) are left blank with a comment, rather than guessed.
"""

import pandas as pd


def build_eod_report(call_detail_log: pd.DataFrame, start_date, end_date, agent_id: int) -> pd.DataFrame:
    """
    Filters the call detail log to [start_date, end_date] (inclusive) and
    returns a single aggregated key/value summary DataFrame covering the
    whole period.
    """
    range_log = call_detail_log[
        (call_detail_log["Call Date (PHT)"] >= start_date)
        & (call_detail_log["Call Date (PHT)"] <= end_date)
    ]

    days_in_range = (end_date - start_date).days + 1
    period_label = str(start_date) if start_date == end_date else f"{start_date} to {end_date}"

    dialed = len(range_log)

    # Status now comes exclusively from the Twilio call-progress journey
    # (see call_detail.py) — completed / failed / no-answer / busy, or
    # blank when no Twilio event matched the conversation_id at all.
    connected = (range_log["Status"] == "completed").sum()
    failed = (range_log["Status"] == "failed").sum()
    no_answer = (range_log["Status"] == "no-answer").sum()
    busy = (range_log["Status"] == "busy").sum()
    unmatched = range_log["Status"].isna().sum()

    agreed = (range_log["Agreed to Keep SIM Active"] == "Yes").sum()

    connection_rate = round((connected / dialed) * 100, 1) if dialed else 0.0
    conversion_rate = round((agreed / connected) * 100, 1) if connected else 0.0

    avg_duration = range_log["Call Duration (sec)"].dropna()
    avg_duration = round(avg_duration.mean(), 1) if not avg_duration.empty else None

    metrics = [
        ("Report Period", period_label),
        ("Days in Range", days_in_range),
        ("Agent ID", agent_id),
        ("Calls Dialed - Actual", dialed),
        ("Calls Connected (Twilio status = completed)", connected),
        ("Calls Failed (Twilio status = failed)", failed),
        ("Calls No Answer (Twilio status = no-answer)", no_answer),
        ("Calls Busy (Twilio status = busy)", busy),
        ("Calls with No Twilio Match (Status blank)", unmatched),
        ("Connection Rate (Connected / Dialed)", f"{connection_rate}%"),
        ("Agreed to Keep SIM Active (count)", agreed),
        ("Conversion Rate (Agreed / Connected)", f"{conversion_rate}%"),
        ("Avg. Call Duration - Connected (sec)", avg_duration),
        # Left blank: no reliable source data yet for these plan-template rows.
        ("LLM Inference Cost (USD)", "N/A - not in source data"),
        ("Open P0 Issues", "N/A - not in source data"),
        ("Open P1 Issues", "N/A - not in source data"),
    ]

    return pd.DataFrame(metrics, columns=["Metric", "Value"])