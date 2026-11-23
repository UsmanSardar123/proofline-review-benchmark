<!--
  METADATA FOR AUTOMATED INGESTION:
  attempt_id: att-470ea9a28633
  batch_id: batch-8e1fac6e
  provider_id: claude-web
  case_id: case-06
  context_condition: CODE_ONLY
-->
# BENCHMARK REVIEW PROMPT
- **Case ID:** case-06
- **Attempt ID:** att-470ea9a28633
- **Batch ID:** batch-8e1fac6e
- **Provider Target:** claude-web
- **Context Condition:** CODE_ONLY
- **Base Commit:** 9b5ac64
- **Head Commit:** fcb0c2a

---

# Pull Request Review: Use the new delivery queue

## Description
Route newly scheduled deliveries to the dedicated dispatch queue. Existing jobs keep their assigned queue.

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
