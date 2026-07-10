"""
sanity_check_joins.py
---------------------
Quick sanity check to verify Twilio dummy data creates proper matches
when joining conversations + kpi_results + twilio_webhook_events.

Usage:
    python scripts/sanity_check_joins.py
"""

import pandas as pd
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

AGENT_ID = 1060

print("=" * 70)
print("Sanity Check: Join Matches for Agent 1060")
print("=" * 70)

# Load data
print("\n[1/4] Loading CSVs...")
conversations = pd.read_csv(DATA_DIR / "conversations.csv")
kpi_results = pd.read_csv(DATA_DIR / "kpi_results.csv")
twilio_events = pd.read_csv(DATA_DIR / "twilio_webhook_events_with_dummy.csv")

print(f"  Conversations: {len(conversations):,} rows")
print(f"  KPI Results: {len(kpi_results):,} rows")
print(f"  Twilio Events (with dummy): {len(twilio_events):,} rows")

# Filter to agent 1060
print(f"\n[2/4] Filtering to agent_id={AGENT_ID}...")
conv_1060 = conversations[conversations["agent_id"] == AGENT_ID].copy()
kpi_1060 = kpi_results[kpi_results["voiceAgentId"] == AGENT_ID].copy()

print(f"  Conversations (agent {AGENT_ID}): {len(conv_1060):,}")
print(f"  KPI Results (agent {AGENT_ID}): {len(kpi_1060):,}")

# Check join key overlap
print(f"\n[3/4] Checking join key overlap...")

conv_ids = set(conv_1060["conversation_id"].dropna())
kpi_ids = set(kpi_1060["voiceConversationId"].dropna())
twilio_ids = set(twilio_events["conversation_id"].dropna())

print(f"\n  Unique conversation_ids:")
print(f"    - Conversations: {len(conv_ids):,}")
print(f"    - KPI Results: {len(kpi_ids):,}")
print(f"    - Twilio Events: {len(twilio_ids):,}")

# Check overlap with agent 1060
conv_1060_ids = conv_ids
kpi_match = conv_1060_ids & kpi_ids
twilio_match = conv_1060_ids & twilio_ids

print(f"\n  Overlap with Agent {AGENT_ID} conversations:")
print(f"    - Matched in KPI: {len(kpi_match):,} ({len(kpi_match)/len(conv_1060_ids)*100:.1f}%)")
print(f"    - Matched in Twilio: {len(twilio_match):,} ({len(twilio_match)/len(conv_1060_ids)*100:.1f}%)")

# Perform the joins
print(f"\n[4/4] Performing LEFT JOINs (mimicking preprocessing.py)...")

# Join 1: conversations + kpi_results
kpi_for_join = kpi_1060.rename(columns={"voiceConversationId": "conversation_id"})
merged_step1 = conv_1060.merge(
    kpi_for_join,
    on="conversation_id",
    how="left",
    suffixes=("", "_kpi")
)

print(f"\n  Step 1: Conversations LEFT JOIN KPI")
print(f"    - Input rows: {len(conv_1060):,}")
print(f"    - Output rows: {len(merged_step1):,}")
print(f"    - Rows with KPI match: {merged_step1['voiceAgentId'].notna().sum():,} ({merged_step1['voiceAgentId'].notna().sum() / len(merged_step1) * 100:.1f}%)")

if len(merged_step1) != len(conv_1060):
    print(f"    ⚠️  WARNING: Join introduced {len(merged_step1) - len(conv_1060)} duplicate rows!")
else:
    print(f"    ✓ No duplicates introduced")

# Join 2: result + twilio_events
merged_final = merged_step1.merge(
    twilio_events,
    on="conversation_id",
    how="left",
    suffixes=("", "_twilio")
)

print(f"\n  Step 2: (Conversations+KPI) LEFT JOIN Twilio")
print(f"    - Input rows: {len(merged_step1):,}")
print(f"    - Output rows: {len(merged_final):,}")
print(f"    - Rows with Twilio match: {merged_final['event'].notna().sum():,} ({merged_final['event'].notna().sum() / len(merged_final) * 100:.1f}%)")

if len(merged_final) != len(merged_step1):
    print(f"    ⚠️  WARNING: Join introduced {len(merged_final) - len(merged_step1)} duplicate rows!")
else:
    print(f"    ✓ No duplicates introduced")

# Final statistics
print(f"\n{'=' * 70}")
print(f"FINAL JOINED TABLE STATISTICS (Agent {AGENT_ID})")
print(f"{'=' * 70}")
print(f"  Total rows: {len(merged_final):,}")
print(f"\n  Match breakdown:")
print(f"    - Both KPI + Twilio: {((merged_final['voiceAgentId'].notna()) & (merged_final['event'].notna())).sum():,}")
print(f"    - KPI only: {((merged_final['voiceAgentId'].notna()) & (merged_final['event'].isna())).sum():,}")
print(f"    - Twilio only: {((merged_final['voiceAgentId'].isna()) & (merged_final['event'].notna())).sum():,}")
print(f"    - Neither: {((merged_final['voiceAgentId'].isna()) & (merged_final['event'].isna())).sum():,}")

# Sample matched rows
print(f"\n{'=' * 70}")
print(f"SAMPLE: Conversations with ALL 3 sources matched")
print(f"{'=' * 70}")
all_matched = merged_final[
    (merged_final['voiceAgentId'].notna()) &
    (merged_final['event'].notna())
]

if len(all_matched) > 0:
    print(f"\n✓ Found {len(all_matched)} rows with data from all 3 sources!")
    print(f"\nSample conversation_ids with full matches:")
    print(all_matched['conversation_id'].head(10).tolist())
else:
    print(f"\n❌ No rows found with data from all 3 sources")

print(f"\n{'=' * 70}")
print(f"✓ Sanity check complete!")
print(f"{'=' * 70}")
