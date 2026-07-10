# Call Duration Analysis Summary

## Question: Which duration calculation method should we use?

### Three Methods Investigated:

1. **Timestamp Difference**: `end_timestamp - start_timestamp`
2. **Metrics Duration**: `call_logs.metrics.total_duration_ms` ⭐ CURRENT
3. **Twilio Recording Duration**: From Twilio webhook events (completed calls only)

---

## Findings

### Method 1: Timestamp Difference ❌ UNRELIABLE

**Agent 1060 Results:**
- Total with both timestamps: 281/388 (72.5%)
- **Negative durations: 195/281 (69.4%)** ❌
- Zero durations: 0/281
- Positive durations: 86/281 (30.6%)

**Problem:**
- end_timestamp appears to be a placeholder or corrupted value
- 69% of calls show end_timestamp BEFORE start_timestamp
- Mean difference: -19,891 seconds (calls "ending" 5.5 hours before they start!)

**Sample:**
```
start_timestamp: 1781057506586 (2026-06-10 10:45:06 UTC)
end_timestamp:   1781029000000 (2026-06-10 02:50:00 UTC) ← 8 hours earlier!
difference: -28,744 seconds
```

**Conclusion:** ❌ **DO NOT USE** - end_timestamp is fundamentally unreliable for agent 1060

---

### Method 2: Metrics Duration ✅ CURRENT (KEEP)

**Source:** `call_logs.metrics.total_duration_ms`

**Agent 1060 Results:**
- Coverage: 280/388 (72.2%)
- Range: 12 to 390 seconds
- Mean: 87 seconds
- Median: 78 seconds

**Availability by Agent:**
- Agent 1060: 72.2% coverage ✓
- Agent 1189: 82.8% coverage ✓
- Agent 826: 8.6% coverage
- Agent 628: 36.1% coverage
- **14 agents total** have at least some metrics data
- Newer agents (ID > 1000) tend to have better coverage

**Conclusion:** ✅ **KEEP THIS METHOD** - Reliable and good coverage for agent 1060

---

### Method 3: Twilio Recording Duration

**Source:** Twilio webhook `event.completed.RecordingDuration`

**Limitations:**
- Only available for **completed** calls with recordings
- Original Twilio data: only 106/1834 conversations have this (5.8%)
- Agent 1060: **0 matches** in original Twilio data
- After dummy data: 65 matches (but these are synthetic)

**Comparison with Timestamp Duration (other agents):**
- Used agents with Twilio matches: 37, 628, 595, etc.
- Mean absolute difference vs timestamp: 14.7 seconds
- Median difference: 11.0 seconds
- Within 10 seconds: 46.2%

**Note:** Timestamp durations for these other agents ARE positive (unlike agent 1060), suggesting end_timestamp quality varies by agent.

**Conclusion:** ⚠️ **LIMITED USE** - Only available for small subset; can't rely on it as primary source

---

## Recommendation

### ✅ **KEEP CURRENT IMPLEMENTATION**

**Use:** `call_logs.metrics.total_duration_ms`

**Reasoning:**
1. **Most reliable** for agent 1060 (72% coverage with sensible values)
2. **Timestamp method is broken** for agent 1060 (69% negative durations)
3. **Twilio method has no coverage** for agent 1060 in real data
4. Already implemented and working correctly

**Current Code (preprocessing.py:68-89):**
```python
def extract_call_duration(conversations: pd.DataFrame) -> pd.Series:
    """
    Derives call duration (seconds) from call_logs.metrics.total_duration_ms.
    
    NOTE: end_timestamp in conversations.csv is unreliable for this purpose —
    many rows share identical/placeholder end_timestamp values that land
    *before* start_timestamp, producing nonsense negative durations.
    """
    def duration_seconds(call_logs_json):
        logs = _safe_json_loads(call_logs_json)
        if not isinstance(logs, dict):
            return None
        ms = logs.get("metrics", {}).get("total_duration_ms")
        return round(ms / 1000) if ms is not None else None
    
    return conversations["call_logs"].apply(duration_seconds)
```

✅ **NO CHANGES NEEDED**

---

## Data Quality Notes

### Agent 1060 Timestamp Quality:
- ❌ end_timestamp: Unreliable (mostly negative durations)
- ✅ start_timestamp: Reliable (used for Call Date/Time)
- ✅ metrics.total_duration_ms: Reliable (used for duration)

### Coverage Gaps:
- ~28% of agent 1060 calls have no metrics_duration (shows as blank in reports)
- This is expected and acceptable - better to show blank than wrong data

### Future Improvements:
- If Twilio coverage improves, could use it as fallback for calls missing metrics_duration
- For now, metrics_duration is the best single source
