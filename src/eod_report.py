"""
eod_report.py
--------------
Builds the "End-of-Day Report" sheet: aggregate KPIs for one calling day,
following the funnel/metric definitions in the Globe SIM Expiry plan.

Only metrics that can be honestly derived from the available data are
computed. Metrics the source data can't support (e.g. Busy / No Answer
breakdown, LLM inference cost) are left blank with a comment, rather
than guessed.
"""

import pandas as pd


def build_eod_report(call_detail_log: pd.DataFrame, report_date, agent_id: int) -> pd.DataFrame:
    """
    Filters the call detail log to `report_date` and returns a single-row
    (well, key/value pair layout) summary DataFrame for that day.
    """
    day_log = call_detail_log[call_detail_log["Call Date (PHT)"] == report_date]

    dialed = len(day_log)
    connected = (day_log["Status"] == "completed").sum()
    failed = (day_log["Status"] == "failed").sum()
    in_progress = (day_log["Status"] == "in_progress").sum()
    agreed = (day_log["Agreed to Keep SIM Active"] == "Yes").sum()

    connection_rate = round((connected / dialed) * 100, 1) if dialed else 0.0
    conversion_rate = round((agreed / connected) * 100, 1) if connected else 0.0

    avg_duration = day_log["Call Duration (sec)"].dropna()
    avg_duration = round(avg_duration.mean(), 1) if not avg_duration.empty else None

    metrics = [
        ("Report Date", report_date),
        ("Agent ID", agent_id),
        ("Calls Dialed - Actual", dialed),
        ("Calls Connected (status = completed)", connected),
        ("Calls Failed", failed),
        ("Calls In Progress", in_progress),
        ("Connection Rate (Connected / Dialed)", f"{connection_rate}%"),
        ("Agreed to Keep SIM Active (count)", agreed),
        ("Conversion Rate (Agreed / Connected)", f"{conversion_rate}%"),
        ("Avg. Call Duration - Connected (sec)", avg_duration),
        # Left blank: no reliable source data yet for these plan-template rows.
        ("No Answer (retries exhausted)", "N/A - not derivable from current data"),
        ("Busy", "N/A - not derivable from current data"),
        ("LLM Inference Cost (USD)", "N/A - not in source data"),
        ("Open P0 Issues", "N/A - not in source data"),
        ("Open P1 Issues", "N/A - not in source data"),
    ]

    return pd.DataFrame(metrics, columns=["Metric", "Value"])
