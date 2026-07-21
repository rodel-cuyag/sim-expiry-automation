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
    # (see call_detail.py) and is mapped to display-friendly values:
    # "Connected", "Failed", "No Answer", "Busy", etc.
    connected = (range_log["Status"] == "Connected").sum()
    failed = (range_log["Status"] == "Failed").sum()
    no_answer = (range_log["Status"] == "No Answer").sum()
    busy = (range_log["Status"] == "Busy").sum()
    unmatched = range_log["Status"].isna().sum()

    # Count agreements ONLY from connected calls for accurate conversion rate
    connected_calls = range_log[range_log["Status"] == "Connected"]
    agreed = (connected_calls["Agreed to Keep SIM Active"] == "Yes").sum()

    connection_rate = round((connected / dialed) * 100, 1) if dialed else 0.0
    conversion_rate = round((agreed / connected) * 100, 1) if connected else 0.0

    # Calculate durations
    avg_duration_sec = range_log["Call Duration (sec)"].dropna()
    avg_duration = round(avg_duration_sec.mean(), 1) if not avg_duration_sec.empty else None

    total_duration_sec = avg_duration_sec.sum() if not avg_duration_sec.empty else 0
    total_duration_min = round(total_duration_sec / 60, 1) if total_duration_sec else None

    # Calculate retries queued (Failed, No Answer, Busy = need retry)
    retries_queued = failed + no_answer + busy

    metrics = [
        ("Report Period", period_label),
        ("Days in Range", days_in_range),
        ("Agent ID", agent_id),
        ("", ""),  # Blank row for readability

        # Call Volume Metrics
        ("Calls Dialed - Target", "[PLACEHOLDER - Set by team]"),
        ("Calls Dialed - Actual", dialed),
        ("Calls Connected", connected),
        ("No Answer (all retries exhausted)", no_answer),
        ("Busy", busy),
        ("System Errors", "[PLACEHOLDER - Consult team]"),
        ("", ""),  # Blank row

        # Duration Metrics
        ("Total Call Duration (minutes)", total_duration_min),
        ("Avg. Call Duration - Connected (seconds)", avg_duration),
        ("", ""),  # Blank row

        # Conversion Metrics
        ("Connection Rate (Connected / Dialed)", f"{connection_rate}%"),
        ("Agreed to Keep SIM Active (count)", agreed),
        ("Conversion Rate (Agreed / Connected)", f"{conversion_rate}%"),
        ("Retries Queued for Tomorrow", retries_queued),
        ("", ""),  # Blank row

        # FINOPS Section
        ("FINOPS", ""),
        ("LLM Inference Cost (USD)", "[PLACEHOLDER - Consult team]"),
        ("Total Daily Spend (USD)", "[PLACEHOLDER - Consult team]"),
        ("", ""),  # Blank row

        # ISSUES & CHANGES Section
        ("ISSUES & CHANGES", ""),
        ("Open P0 Issues", "[PLACEHOLDER - Consult team]"),
        ("Open P1 Issues", "[PLACEHOLDER - Consult team]"),
        ("Changes Deployed Today", "[PLACEHOLDER - Manual entry]"),
        ("Changes Pending Approval for Tomorrow", "[PLACEHOLDER - Manual entry]"),
        ("", ""),  # Blank row

        # TOMORROW'S PLAN Section
        ("TOMORROW'S PLAN", ""),
        ("Target Call Volume", "[PLACEHOLDER - Manual entry]"),
        ("Expected List from Globe (ETA)", "[PLACEHOLDER - Manual entry]"),
        ("Calling Window", "9:00 AM - 7:00 PM PHT"),
        ("Phase Gate Status", "[PLACEHOLDER - Manual entry]"),
    ]

    return pd.DataFrame(metrics, columns=["Metric", "Value"])