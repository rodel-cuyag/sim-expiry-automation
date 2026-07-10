# Event & Disposition Mapping Logic

## Confirmed Event Stages (7 unique values)

✓ **Verified from actual data:**
1. `initiated`
2. `ringing`
3. `in-progress`
4. `completed`
5. `no-answer`
6. `busy`
7. `failed`

## Call Journey Sequences (from data)

| Final Status | Journey Pattern | Max Seq # |
|--------------|-----------------|-----------|
| **failed** | initiated(0) → failed(1) | 1 |
| **busy** | initiated(0) → ringing(1) → busy(2) | 2 |
| **no-answer** | initiated(0) → ringing(1) → no-answer(2) | 2 |
| **completed** | initiated(0) → ringing(1) → in-progress(2) → completed(3) | 3 |

---

## Proposed Mapping for "Status" Column

**From `twilio_final_status` (highest priority stage reached):**

| Twilio Stage | Display Status | Notes |
|--------------|----------------|-------|
| `completed` | **Connected** | Call was successfully connected and completed |
| `in-progress` | **Connected** | Call was connected (shouldn't be final stage, but still means connected) |
| `ringing` | **Ringing** | Call reached ringing but didn't progress further |
| `no-answer` | **No Answer** | Call rang but no one answered |
| `busy` | **Busy** | Recipient line was busy |
| `failed` | **Failed** | Call failed to connect (network/technical issue) |
| `initiated` | **Initiated** | Call started but didn't progress (shouldn't be final, but keep for safety) |

**Note:** You'll clarify with the team how to differentiate busy/no-answer/failed in business terms.

---

## Proposed Mapping for "Disposition Code" Column

**From KPI `call_completed` field:**

| Condition | Disposition Code | Logic |
|-----------|------------------|-------|
| `call_completed == True` | **COMPLETED** | Call was successfully completed (regardless of retention outcome) |
| `call_completed == False` AND Twilio status = `completed` or `in-progress` | **PARTIAL** | Call connected but ended abruptly/incomplete |
| `call_completed == False` AND Twilio status = `no-answer` | **NO_ANSWER** | Matches Twilio status |
| `call_completed == False` AND Twilio status = `busy` | **BUSY** | Matches Twilio status |
| `call_completed == False` AND Twilio status = `failed` | **FAILED** | Call failed to connect |
| No KPI match | **N/A** | No KPI data available |

**Note:** Retention success has its own column ("Agreed to Keep SIM Active"), so disposition focuses on call completion, not retention outcome.

---

## New Fields to Add

### 1. **Latest Sequence Number**
- **Source:** `event` column in `twilio_webhook_events`
- **Logic:** Find the stage with the highest `SequenceNumber` value
- **Purpose:** Track which stage the call reached in its journey

### 2. **Status** (Updated mapping)
- **Source:** `twilio_final_status` 
- **Logic:** Map using table above
- **Current:** Uses raw Twilio stage names (completed, no-answer, etc.)
- **Proposed:** Uses display-friendly names (Connected, No Answer, etc.)

### 3. **Disposition Code** (New field)
- **Source:** Combination of KPI `call_completed` + Twilio `twilio_final_status`
- **Logic:** Use mapping table above
- **Purpose:** Standardized call outcome code for reporting

---

## Data Availability (Agent 1060)

- **Conversations:** 388 rows
- **KPI matches:** 279 (71.9%)
- **Twilio matches:** 100 (25.8%)
- **Both KPI + Twilio:** 69 (17.8%)

**call_completed distribution (from KPI):**
- `True`: 258 (92.5%)
- `False`: 21 (7.5%)

---

## Implementation Plan

### Files to Update:

1. **`src/preprocessing.py`**
   - Update `extract_twilio_details()` to also extract `latest_sequence_number`
   - Keep existing `twilio_final_status` logic

2. **`src/call_detail.py`**
   - Add `Latest Sequence Number` column
   - Update `Status` column with display-friendly mapping
   - Add new `Disposition Code` column with logic above

### Backward Compatibility:
- Original `twilio_final_status` field stays unchanged for internal use
- Display mapping only affects the Excel output columns
