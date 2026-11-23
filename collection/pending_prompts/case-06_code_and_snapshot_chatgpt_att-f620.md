<!--
  METADATA FOR AUTOMATED INGESTION:
  attempt_id: att-f620d60e5076
  batch_id: batch-8aca4c4d
  provider_id: chatgpt-web
  case_id: case-06
  context_condition: CODE_AND_SNAPSHOT
-->
# BENCHMARK REVIEW PROMPT
- **Case ID:** case-06
- **Attempt ID:** att-f620d60e5076
- **Batch ID:** batch-8aca4c4d
- **Provider Target:** chatgpt-web
- **Context Condition:** CODE_AND_SNAPSHOT
- **Base Commit:** 9b5ac64
- **Head Commit:** fcb0c2a

---

# Pull Request Review: Use the new delivery queue

## Description
Route newly scheduled deliveries to the dedicated dispatch queue. Existing jobs keep their assigned queue.

## Operational & Deployment Context
Queue subscription inventory from the report service simulator at the scheduled routing cutover. The inventory covers every consumer of reporting jobs at each site. Each worker subscription is an exact queue name. Existing subscriptions stay in place throughout the observation window.

```json
{
  "observation": "subscriptions-416",
  "observed_at": "2026-10-21T09:00:00Z",
  "window_end": "2026-10-21T09:30:00Z",
  "sites": {
    "elm": {"subscribed_queues": ["reports"], "new_jobs_due_in_window": 8},
    "cedar": {"subscribed_queues": ["reports", "report-dispatch"], "new_jobs_due_in_window": 8}
  }
}
```

## Proposed Code Changes (Git Diff)
```diff
diff --git reports.py reports.py
index 7cd951c..ca2eddb 100644
--- reports.py
+++ reports.py
@@ -6,7 +6,7 @@ from itertools import islice
 from pathlib import Path
 
 
-DELIVERY_QUEUE = "reports"
+DELIVERY_QUEUE = "report-dispatch"
 EXPORT_BATCH_SIZE = 25
```

## Instructions
Review the proposed changes above against the application baseline.
Identify any logic bugs, data integrity issues, regressions, operational risks,
or deployment conflicts. State clearly which file and line are affected and explain the issue.
