"""
generate_dummy_twilio_data.py
------------------------------
Creates dummy Twilio webhook events for agent 1060 conversations to enable
full pipeline testing. Uses actual conversation_ids and contact_numbers from
conversations.csv.

Output: twilio_webhook_events_with_dummy.csv (original + dummy data combined)

Usage:
    python scripts/generate_dummy_twilio_data.py
"""

import pandas as pd
import json
import random
import hashlib
from pathlib import Path
from datetime import datetime, timedelta


# Configuration
AGENT_ID = 1060
SAMPLE_SIZE = 100  # Number of conversations to create dummy data for
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Call status distribution (realistic mix)
STATUS_DISTRIBUTION = {
    "completed": 0.60,
    "no-answer": 0.20,
    "busy": 0.10,
    "failed": 0.10,
}

# Fixed Twilio fields (matching existing data)
FROM_NUMBER = "+639272797345"
ACCOUNT_SID = "AC303f8edc4d3a765f5efb64db7c7afb8d"
API_VERSION = "2010-04-01"
DIRECTION = "outbound-api"
COUNTRY = "PH"


def generate_call_sid():
    """Generate a unique Twilio-style CallSid."""
    random_hash = hashlib.md5(str(random.random()).encode()).hexdigest()[:32]
    return f"CA{random_hash}"


def generate_timestamp_sequence(base_time, status):
    """
    Generate realistic timestamp sequence based on call status.
    Returns list of (stage, timestamp, duration_offset) tuples.
    """
    timestamps = []
    current = base_time

    # All calls start with initiated
    timestamps.append(("initiated", current, 0))

    if status == "failed":
        # Failed calls: initiated -> failed (immediate)
        current += timedelta(seconds=random.randint(1, 3))
        timestamps.append(("failed", current, 0))

    elif status == "busy":
        # Busy calls: initiated -> ringing -> busy
        current += timedelta(seconds=random.randint(2, 5))
        timestamps.append(("ringing", current, 0))
        current += timedelta(seconds=random.randint(1, 3))
        timestamps.append(("busy", current, 0))

    elif status == "no-answer":
        # No-answer calls: initiated -> ringing -> no-answer
        current += timedelta(seconds=random.randint(2, 5))
        timestamps.append(("ringing", current, 0))
        current += timedelta(seconds=random.randint(15, 30))
        timestamps.append(("no-answer", current, 0))

    elif status == "completed":
        # Completed calls: initiated -> ringing -> in-progress -> completed
        current += timedelta(seconds=random.randint(2, 5))
        timestamps.append(("ringing", current, 0))
        current += timedelta(seconds=random.randint(5, 15))
        timestamps.append(("in-progress", current, 0))
        call_duration = random.randint(10, 180)  # 10s to 3min
        current += timedelta(seconds=call_duration)
        timestamps.append(("completed", current, call_duration))

    return timestamps


def create_stage_event(stage, timestamp, to_number, call_sid, seq_num, duration=0):
    """Create a single stage event dictionary matching Twilio format."""
    event = {
        "To": to_number,
        "From": FROM_NUMBER,
        "ToZip": "",
        "Called": to_number,
        "Caller": FROM_NUMBER,
        "ToCity": "",
        "CallSid": call_sid,
        "FromZip": "",
        "ToState": "",
        "FromCity": "",
        "CalledZip": "",
        "CallerZip": "",
        "Direction": DIRECTION,
        "FromState": "",
        "Timestamp": timestamp.strftime("%a, %d %b %Y %H:%M:%S +0000"),
        "ToCountry": COUNTRY,
        "AccountSid": ACCOUNT_SID,
        "ApiVersion": API_VERSION,
        "CallStatus": stage,
        "CalledCity": "",
        "CallerCity": "",
        "CalledState": "",
        "CallerState": "",
        "FromCountry": COUNTRY,
        "CalledCountry": COUNTRY,
        "CallerCountry": COUNTRY,
        "CallbackSource": "call-progress-events",
        "SequenceNumber": str(seq_num),
    }

    # Add duration fields for completed calls
    if stage == "completed":
        event["Duration"] = str(duration)
        event["CallDuration"] = str(duration)
        # Add dummy recording info
        recording_sid = f"RE{hashlib.md5(call_sid.encode()).hexdigest()[:32]}"
        event["RecordingSid"] = recording_sid
        event["RecordingUrl"] = f"https://api.twilio.com/2010-04-01/Accounts/{ACCOUNT_SID}/Recordings/{recording_sid}"
        event["RecordingDuration"] = str(duration + 1)

    # Add duration=0 for failed calls
    if stage in ["failed", "busy", "no-answer"]:
        event["Duration"] = "0"
        event["CallDuration"] = "0"

    return event


def create_event_json(conversation, status):
    """
    Create the full event JSON blob for a conversation, matching the
    multi-stage structure from the original Twilio data.
    """
    call_sid = generate_call_sid()
    to_number = conversation["contact_number"]

    # Ensure phone number is in +63 format
    if pd.notna(to_number):
        to_number = str(to_number).replace(".0", "")
        if not to_number.startswith("+"):
            if to_number.startswith("63"):
                to_number = "+" + to_number
            elif to_number.startswith("0"):
                to_number = "+63" + to_number[1:]
            elif to_number.startswith("9"):
                to_number = "+63" + to_number
            else:
                to_number = "+63" + to_number
    else:
        # Fallback if contact_number is missing
        to_number = f"+639{random.randint(100000000, 999999999)}"

    # Generate timestamp sequence based on status
    base_time = pd.to_datetime(conversation["start_timestamp"], unit="ms", utc=True)
    stages = generate_timestamp_sequence(base_time, status)

    # Build the event JSON as a nested dict (stage_name: event_dict)
    event_json = {}
    for seq_num, (stage, timestamp, duration) in enumerate(stages):
        event_json[stage] = create_stage_event(
            stage, timestamp, to_number, call_sid, seq_num, duration
        )

    return json.dumps(event_json), call_sid, to_number


def determine_sip_code(status):
    """Return appropriate SIP response code for the call status."""
    if status == "completed":
        return 200
    elif status in ["busy", "no-answer", "failed"]:
        return 480
    else:
        return 200


def main():
    print("=" * 60)
    print("Generating Dummy Twilio Webhook Data for Agent 1060")
    print("=" * 60)

    # Load conversations
    print("\n[1/6] Loading conversations.csv...")
    conversations = pd.read_csv(DATA_DIR / "conversations.csv")
    print(f"      Total conversations: {len(conversations):,}")

    # Filter to agent 1060
    agent_convs = conversations[conversations["agent_id"] == AGENT_ID].copy()
    print(f"      Agent {AGENT_ID} conversations: {len(agent_convs):,}")

    if len(agent_convs) == 0:
        print(f"\n❌ ERROR: No conversations found for agent_id={AGENT_ID}")
        return

    # Sample conversations for dummy data
    print(f"\n[2/6] Sampling {SAMPLE_SIZE} conversations for dummy data...")
    sample_size = min(SAMPLE_SIZE, len(agent_convs))
    sampled = agent_convs.sample(n=sample_size, random_state=42)
    print(f"      Sampled: {len(sampled)} conversations")

    # Generate dummy webhook events
    print(f"\n[3/6] Generating dummy Twilio events...")
    dummy_rows = []
    status_counts = {s: 0 for s in STATUS_DISTRIBUTION.keys()}

    for idx, row in sampled.iterrows():
        # Randomly assign status based on distribution
        status = random.choices(
            list(STATUS_DISTRIBUTION.keys()),
            weights=list(STATUS_DISTRIBUTION.values()),
            k=1
        )[0]
        status_counts[status] += 1

        # Generate event JSON
        event_json, call_sid, to_number = create_event_json(row, status)
        sip_code = determine_sip_code(status)

        dummy_rows.append({
            "id": None,  # Will be filled after combining
            "call_sid": call_sid,
            "sip_code": sip_code,
            "event": event_json,
            "conversation_id": row["conversation_id"]
        })

    print(f"      Generated {len(dummy_rows)} dummy events")
    print(f"      Status distribution:")
    for status, count in status_counts.items():
        print(f"        - {status}: {count} ({count/len(dummy_rows)*100:.1f}%)")

    # Load existing Twilio data
    print(f"\n[4/6] Loading existing twilio_webhook_events.csv...")
    existing = pd.read_csv(DATA_DIR / "twilio_webhook_events.csv")
    print(f"      Existing rows: {len(existing):,}")

    # Combine original + dummy
    print(f"\n[5/6] Combining original + dummy data...")
    dummy_df = pd.DataFrame(dummy_rows)
    combined = pd.concat([existing, dummy_df], ignore_index=True)

    # Reassign sequential IDs
    combined["id"] = range(1, len(combined) + 1)

    print(f"      Combined rows: {len(combined):,}")
    print(f"        - Original: {len(existing):,}")
    print(f"        - Dummy: {len(dummy_df):,}")

    # Save to new file
    output_path = DATA_DIR / "twilio_webhook_events_with_dummy.csv"
    print(f"\n[6/6] Saving to {output_path.name}...")
    combined.to_csv(output_path, index=False)

    print(f"\n✓ SUCCESS! Created {output_path}")
    print(f"\nTo use this data, copy the file into data/eod/ — it will be")
    print(f"auto-detected by its column headers (call_sid + event).")
    print("=" * 60)


if __name__ == "__main__":
    main()
