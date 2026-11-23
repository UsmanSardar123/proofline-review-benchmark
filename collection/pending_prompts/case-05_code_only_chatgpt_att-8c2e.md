<!--
  METADATA FOR AUTOMATED INGESTION:
  attempt_id: att-8c2e145b504b
  batch_id: batch-8e1fac6e
  provider_id: chatgpt-web
  case_id: case-05
  context_condition: CODE_ONLY
-->
# BENCHMARK REVIEW PROMPT
- **Case ID:** case-05
- **Attempt ID:** att-8c2e145b504b
- **Batch ID:** batch-8e1fac6e
- **Provider Target:** chatgpt-web
- **Context Condition:** CODE_ONLY
- **Base Commit:** 9b5ac64
- **Head Commit:** 1f6f2a4

---

# Pull Request Review: Increase export batch size

## Description
Group up to fifty records per archive request to reduce the number of calls for a full export.

## Proposed Code Changes (Git Diff)
```diff
diff --git reports.py reports.py
index 7cd951c..43e70d8 100644
--- reports.py
+++ reports.py
@@ -7,7 +7,7 @@ from pathlib import Path
 
 
 DELIVERY_QUEUE = "reports"
-EXPORT_BATCH_SIZE = 25
+EXPORT_BATCH_SIZE = 50
 
 
 def migrate(db):
```

## Instructions
Review the proposed changes above against the application baseline.
Identify any logic bugs, data integrity issues, regressions, operational risks,
or deployment conflicts. State clearly which file and line are affected and explain the issue.
