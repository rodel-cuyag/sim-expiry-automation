"""
validation_report.py
--------------------
Builds a multi-sheet validation workbook that audits the EOD report
pipeline: source-data join coverage, per-row field completeness, a
step-by-step calculation trace, and a consolidated data-quality issues
register.

Generated automatically alongside every EOD report run.
"""

import json

import pandas as pd
from src import data_loader


# ── Sheet 1: Join Summary ─────────────────────────────────────────

def _build_join_summary(working_table, agent_id, start_date, end_date):
    raw = data_loader.load_all()

    conv = raw["conversations"]
    conv_agt = conv[conv["agent_id"] == agent_id] if agent_id else conv
    conv_ids = set(conv_agt["conversation_id"].unique())

    kpi = raw["kpi_results"]
    kpi_agt = kpi[kpi["voiceAgentId"] == agent_id] if agent_id else kpi
    kpi_ids = set(kpi_agt["voiceConversationId"].unique())

    tw = raw["twilio_events"]
    tw_ids = set(tw["conversation_id"].unique())

    rows = []
    for _, row_ in working_table.iterrows():
        cid = row_["conversation_id"]
        in_conv = cid in conv_ids
        in_kpi = cid in kpi_ids
        in_tw = cid in tw_ids

        if in_conv and in_kpi and in_tw:
            status = "All Sources Complete"
        elif in_conv and in_kpi:
            status = "Missing Twilio"
        elif in_conv and in_tw:
            status = "Missing KPI"
        else:
            status = "Missing KPI and Twilio"

        call_date = row_.get("start_dt_pht")
        if pd.notna(call_date):
            call_date = call_date.date()

        rows.append({
            "Conversation ID": cid,
            "In Conversations": "Yes" if in_conv else "No",
            "In KPI Results": "Yes" if in_kpi else "No",
            "In Twilio Events": "Yes" if in_tw else "No",
            "Join Status": status,
            "Agent ID": agent_id,
            "Call Date (PHT)": call_date,
        })

    df = pd.DataFrame(rows)

    # Filter to the report's date range
    if start_date and end_date:
        df = df[
            (df["Call Date (PHT)"] >= start_date)
            & (df["Call Date (PHT)"] <= end_date)
        ]

    return df.sort_values(["Call Date (PHT)", "Conversation ID"]).reset_index(drop=True)


# ── Sheet 2: Field Completeness ───────────────────────────────────

def _build_field_completeness(detail_log, start_date=None, end_date=None):
    if start_date and end_date:
        detail_log = detail_log[
            (detail_log["Call Date (PHT)"] >= start_date)
            & (detail_log["Call Date (PHT)"] <= end_date)
        ]

    rows = []

    for _, row_ in detail_log.iterrows():
        cid = row_["Conversation ID"]

        cn = row_.get("Contact Number")
        cn_status = _populated_status(cn, "Populated", "MISSING")

        st = row_.get("Status")
        if _is_blank(st):
            st_status = "MISSING (No Twilio data)"
        else:
            st_status = f"Populated ({st})"

        cd = row_.get("Call Duration (sec)")
        if _is_blank(cd):
            cd_status = "MISSING (No call_logs data)"
        else:
            cd_status = f"Populated ({cd}s)"

        ag = row_.get("Agreed to Keep SIM Active")
        if _is_blank(ag):
            ag_status = "MISSING (No KPI data)"
        else:
            ag_status = f"Populated ({ag})"

        cdisp = row_.get("Customer Disposition")
        if _is_blank(cdisp):
            cdisp_status = "MISSING (No KPI data)"
        else:
            cdisp_status = f"Populated ({cdisp})"

        nrr = row_.get("Non-Retention Reason")
        if _is_blank(nrr):
            nrr_status = "MISSING (No KPI data)"
        else:
            nrr_status = f"Populated ({nrr})"

        cdt = row_.get("Call Date (PHT)")
        cdt_status = _populated_status(cdt, "Populated", "MISSING")

        ctm = row_.get("Call Time (PHT)")
        ctm_status = _populated_status(ctm, "Populated", "MISSING")

        # Score: count non-blank fields
        fields = [cn, st, cd, ag, cdisp, nrr, cdt, ctm]
        score = sum(1 for f in fields if not _is_blank(f))

        rows.append({
            "Conversation ID": cid,
            "Contact Number": cn_status,
            "Status": st_status,
            "Call Duration (sec)": cd_status,
            "Agreed to Keep SIM Active": ag_status,
            "Customer Disposition": cdisp_status,
            "Non-Retention Reason": nrr_status,
            "Call Date (PHT)": cdt_status,
            "Call Time (PHT)": ctm_status,
            "Completeness Score": f"{score}/8",
        })

    return pd.DataFrame(rows)


def _is_blank(val):
    """True when a cell is NaN, None, empty-string, or pd.NA."""
    if val is None:
        return True
    if isinstance(val, float) and pd.isna(val):
        return True
    if isinstance(val, str) and val.strip() == "":
        return True
    return False


def _populated_status(val, ok_label, missing_label):
    return ok_label if not _is_blank(val) else missing_label


# ── Sheet 3: Calculation Audit ────────────────────────────────────

def _build_calculation_audit(detail_log, eod_df, start_date, end_date):
    range_log = detail_log[
        (detail_log["Call Date (PHT)"] >= start_date)
        & (detail_log["Call Date (PHT)"] <= end_date)
    ]

    eod_lookup = dict(zip(eod_df["Metric"].astype(str), eod_df["Value"]))

    dialed = len(range_log)
    connected = int((range_log["Status"] == "Connected").sum())
    failed = int((range_log["Status"] == "Failed").sum())
    no_answer = int((range_log["Status"] == "No Answer").sum())
    busy = int((range_log["Status"] == "Busy").sum())
    unmatched = int(range_log["Status"].isna().sum())

    connected_calls = range_log[range_log["Status"] == "Connected"]
    agreed = int((connected_calls["Agreed to Keep SIM Active"] == "Yes").sum())

    conn_rate_val = round((connected / dialed) * 100, 1) if dialed else 0.0
    conv_rate_val = round((agreed / connected) * 100, 1) if connected else 0.0

    dur = range_log["Call Duration (sec)"].dropna()
    total_sec = int(dur.sum()) if not dur.empty else 0
    total_min = round(total_sec / 60, 1) if total_sec else None
    avg_dur = round(dur.mean(), 1) if not dur.empty else None

    retries = failed + no_answer + busy

    rows = []

    _sentinel = object()

    def add_step(step, metric, formula, operands, computed, report_key):
        expected = eod_lookup.get(report_key, _sentinel)
        if expected is _sentinel:
            match = "(not in EOD report)"
            display_expected = "(not in report)"
        else:
            display_expected = expected
            try:
                if str(computed) != str(expected):
                    match = f"MISMATCH (expected {expected})"
                else:
                    match = "PASS"
            except (ValueError, TypeError):
                match = f"MISMATCH (expected {expected})"
        rows.append({
            "Step": step,
            "Metric": metric,
            "Formula / Derivation": formula,
            "Operands / Intermediate Values": operands,
            "Computed Value": computed,
            "EOD Report Value": display_expected,
            "Match": match,
        })

    add_step(1, "Calls Dialed - Actual",
             "COUNT(Call Detail Log rows)", f"{dialed} rows", dialed,
             "Calls Dialed - Actual")
    add_step(2, "Calls Connected",
             "COUNTIF(Status = 'Connected')", f"{connected} rows", connected,
             "Calls Connected")
    add_step(3, "No Answer",
             "COUNTIF(Status = 'No Answer')", f"{no_answer} rows", no_answer,
             "No Answer (all retries exhausted)")
    add_step(4, "Busy",
             "COUNTIF(Status = 'Busy')", f"{busy} rows", busy,
             "Busy")
    add_step(5, "Failed",
             "COUNTIF(Status = 'Failed')", f"{failed} rows", failed,
             "Failed")  # not in report but useful
    add_step(6, "Unmatched (blank Status)",
             "COUNTIF(Status = blank)", f"{unmatched} rows", unmatched,
             "Unmatched")  # not in report
    add_step(7, "Agreed to Keep SIM Active (count)",
             "COUNTIFS(Status='Connected', Agreed='Yes')",
             f"{connected} connected, {agreed} Yes", agreed,
             "Agreed to Keep SIM Active (count)")
    add_step(8, "Connection Rate",
             "(Connected / Dialed) x 100",
             f"{connected} / {dialed} = {connected/dialed:.4f}" if dialed else "N/A",
             f"{conn_rate_val}%",
             "Connection Rate (Connected / Dialed)")
    add_step(9, "Conversion Rate",
             "(Agreed / Connected) x 100",
             f"{agreed} / {connected} = {agreed/connected:.4f}" if connected else "N/A",
             f"{conv_rate_val}%",
             "Conversion Rate (Agreed / Connected)")
    add_step(10, "Total Call Duration (minutes)",
             "SUM(Call Duration (sec)) / 60",
             f"{total_sec} sec / 60", total_min,
             "Total Call Duration (minutes)")
    add_step(11, "Avg. Call Duration - Connected",
             "AVERAGE(Call Duration (sec) WHERE Status='Connected')",
             f"{len(dur)} rows, sum={total_sec} sec", avg_dur,
             "Avg. Call Duration - Connected (seconds)")
    add_step(12, "Retries Queued for Tomorrow",
             "Failed + No Answer + Busy",
             f"{failed} + {no_answer} + {busy} = {retries}", retries,
             "Retries Queued for Tomorrow")

    return pd.DataFrame(rows)


# ── Sheet 4: Data Quality Issues ──────────────────────────────────

def _build_data_quality_issues(working_table, detail_log,
                                start_date=None, end_date=None):
    if start_date and end_date:
        detail_log = detail_log[
            (detail_log["Call Date (PHT)"] >= start_date)
            & (detail_log["Call Date (PHT)"] <= end_date)
        ]
        keep_ids = set(detail_log["Conversation ID"])
        working_table = working_table[working_table["conversation_id"].isin(keep_ids)]

    issues = []

    # Issues from the detail log rows
    for _, row_ in detail_log.iterrows():
        cid = row_["Conversation ID"]

        if _is_blank(row_.get("Status")):
            issues.append({
                "Conversation ID": cid,
                "Issue": "Missing Twilio Event Data",
                "Detail": (
                    "No matching twilio_webhook_events found for this "
                    "conversation. Status is blank."
                ),
                "Severity": "Medium",
            })

        # Check for missing KPI data by looking at Customer Disposition
        # (Agreed to Keep SIM Active is never blank; it returns "N/A" when
        # KPI data is absent, so it can't serve as the missingness signal.)
        if _is_blank(row_.get("Customer Disposition")):
            issues.append({
                "Conversation ID": cid,
                "Issue": "Missing KPI Results Data",
                "Detail": (
                    "No matching kpi_results found for this conversation. "
                    "All KPI-derived fields (Customer Disposition, "
                    "Non-Retention Reason) are blank; Agreed is 'N/A'."
                ),
                "Severity": "High",
            })

        if _is_blank(row_.get("Call Duration (sec)")):
            issues.append({
                "Conversation ID": cid,
                "Issue": "Missing Call Duration",
                "Detail": (
                    "call_logs field is null or in an unparseable format. "
                    "Duration cannot be extracted."
                ),
                "Severity": "Medium",
            })

    # Contact-number reliability issues from the working table
    for _, row_ in working_table.iterrows():
        cid = row_["conversation_id"]
        reliability = row_.get("contact_number_reliability")
        if pd.notna(reliability) and "TRUNCATED" in str(reliability):
            issues.append({
                "Conversation ID": cid,
                "Issue": "Truncated Contact Number",
                "Detail": str(reliability),
                "Severity": "Medium",
            })

    if not issues:
        return pd.DataFrame(columns=[
            "Conversation ID", "Issue", "Detail", "Severity",
        ])

    return pd.DataFrame(issues)


# ── Public entry point ────────────────────────────────────────────

def build_validation_report(working_table, detail_log, eod_df,
                             start_date, end_date, agent_id):
    """
    Build all 4 validation-report sheets and return them as a
    {sheet_key: DataFrame} dict ready for write_validation_report().
    """
    return {
        "join_summary": _build_join_summary(working_table, agent_id,
                                            start_date, end_date),
        "field_completeness": _build_field_completeness(detail_log,
                                                        start_date, end_date),
        "calculation_audit": _build_calculation_audit(detail_log, eod_df,
                                                      start_date, end_date),
        "data_quality_issues": _build_data_quality_issues(working_table,
                                                          detail_log,
                                                          start_date, end_date),
    }
