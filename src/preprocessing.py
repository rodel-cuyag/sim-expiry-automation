"""
preprocessing.py
------------------
Cleans and joins the 3 raw tables into a single "working" DataFrame,
one row per conversation, filtered to the target agent_id.

Join logic:
  conversations.conversation_id  <-> kpi_results.voiceConversationId
  conversations.conversation_id  <-> twilio_webhook_events.conversation_id
  agent filter uses conversations.agent_id AND kpi_results.voiceAgentId
"""

import json
import pandas as pd
from src import config


def _safe_json_loads(value):
    """Parse a JSON string safely; return {} if null/invalid/empty."""
    if pd.isna(value) or value in ("", "{}"):
        return {}
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {}


def filter_conversations_by_agent(conversations: pd.DataFrame, agent_id: int) -> pd.DataFrame:
    """Keep only conversations belonging to the target agent_id."""
    return conversations[conversations["agent_id"] == agent_id].copy()


def add_local_timestamps(conversations: pd.DataFrame) -> pd.DataFrame:
    """
    Convert epoch-millisecond UTC timestamps into PHT datetime columns.
    Adds: start_dt_pht, end_dt_pht, call_date (date-only, used for EOD grouping).
    """
    df = conversations.copy()
    df["start_dt_pht"] = (
        pd.to_datetime(df["start_timestamp"], unit="ms", utc=True)
        .dt.tz_convert(config.TIMEZONE)
    )
    df["end_dt_pht"] = (
        pd.to_datetime(df["end_timestamp"], unit="ms", utc=True)
        .dt.tz_convert(config.TIMEZONE)
    )
    df["call_date"] = df["start_dt_pht"].dt.date
    df["call_duration_sec"] = extract_call_duration(df)
    return df


def extract_call_duration(conversations: pd.DataFrame) -> pd.Series:
    """
    Derives call duration (seconds) from call_logs.metrics.total_duration_ms.

    NOTE: end_timestamp in conversations.csv is unreliable for this purpose —
    many rows share identical/placeholder end_timestamp values that land
    *before* start_timestamp, producing nonsense negative durations. The
    per-call metrics embedded in call_logs are the trustworthy source, so
    we use that instead and ignore end_timestamp entirely.
    """
    def duration_seconds(call_logs_json):
        logs = _safe_json_loads(call_logs_json)
        ms = logs.get("metrics", {}).get("total_duration_ms")
        return round(ms / 1000) if ms is not None else None

    return conversations["call_logs"].apply(duration_seconds)


def extract_kpi_fields(kpi_results: pd.DataFrame, agent_id: int) -> pd.DataFrame:
    """
    Filter KPI rows to the target agent (voiceAgentId) and flatten the
    outputJson blob into real columns we can merge on conversation_id.
    """
    kpi = kpi_results[kpi_results["voiceAgentId"] == agent_id].copy()
    parsed = kpi["outputJson"].apply(_safe_json_loads).apply(pd.Series)

    flat = pd.concat(
        [kpi[["voiceConversationId"]].reset_index(drop=True), parsed.reset_index(drop=True)],
        axis=1,
    )
    flat = flat.rename(columns={"voiceConversationId": "conversation_id"})

    # Only keep the fields relevant to the SIM-expiry retention use case.
    # (Other agent types may populate different keys in outputJson —
    # missing columns are simply absent after this filter, handled downstream.)
    keep_cols = [
        "conversation_id",
        "call_completed",
        "customer_disposition",
        "sim_retention_success",
        "non_retention_reason",
        "user_sentiment",
    ]
    existing_cols = [c for c in keep_cols if c in flat.columns]
    return flat[existing_cols]


def extract_twilio_status(twilio_events: pd.DataFrame) -> pd.DataFrame:
    """
    Flatten the Twilio 'event' JSON blob and derive the FINAL call status
    per conversation_id (e.g. completed / no-answer / busy / failed).

    NOTE: For some agents, twilio_webhook_events.csv may have zero matching
    conversation_ids (Twilio callbacks not wired up / not exported yet for
    that agent). In that case this returns an empty-but-correctly-shaped
    DataFrame, and downstream code falls back to conversations.status —
    see call_detail.py.
    """
    if twilio_events.empty:
        return pd.DataFrame(columns=["conversation_id", "twilio_final_status"])

    def final_status(event_json: str) -> str:
        events = _safe_json_loads(event_json)
        if not events:
            return None
        # event_json is a dict of {event_name: {...details}}; use the last
        # meaningful lifecycle event as the "final" status.
        priority = ["completed", "no-answer", "busy", "failed", "in-progress", "ringing", "initiated"]
        for status in priority:
            if status in events:
                return status
        return None

    result = twilio_events[["conversation_id"]].copy()
    result["twilio_final_status"] = twilio_events["event"].apply(final_status)
    return result.drop_duplicates(subset="conversation_id")


def build_working_table(agent_id: int = None) -> pd.DataFrame:
    """
    Main entry point: loads all 3 CSVs, filters to agent_id, and merges
    them into one row-per-conversation DataFrame ready for reporting.
    """
    from src import data_loader  # local import avoids circular import

    agent_id = agent_id or config.AGENT_ID

    raw = data_loader.load_all()

    conversations = filter_conversations_by_agent(raw["conversations"], agent_id)
    conversations = add_local_timestamps(conversations)

    kpi_flat = extract_kpi_fields(raw["kpi_results"], agent_id)
    twilio_flat = extract_twilio_status(raw["twilio_events"])

    merged = conversations.merge(kpi_flat, on="conversation_id", how="left")
    merged = merged.merge(twilio_flat, on="conversation_id", how="left")

    return merged
