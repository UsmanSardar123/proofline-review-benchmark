<!--
  METADATA FOR AUTOMATED INGESTION:
  attempt_id: att-8a22c53c514b
  batch_id: batch-8e1fac6e
  provider_id: chatgpt-web
  case_id: case-08
  context_condition: CODE_ONLY
-->
# BENCHMARK REVIEW PROMPT
- **Case ID:** case-08
- **Attempt ID:** att-8a22c53c514b
- **Batch ID:** batch-8e1fac6e
- **Provider Target:** chatgpt-web
- **Context Condition:** CODE_ONLY
- **Base Commit:** 9b5ac64
- **Head Commit:** f869d7c

---

# Pull Request Review: Include a total in the activity summary

## Description
Expose the total number of deliveries in the summary response alongside the pending and delivered counts.

## Proposed Code Changes (Git Diff)
```diff
diff --git reports.py reports.py
index 7cd951c..1d46858 100644
--- reports.py
+++ reports.py
@@ -83,4 +83,4 @@ def summary(db):
     sent, waiting = db.execute(
         "SELECT count(delivered_at), count(*) - count(delivered_at) FROM deliveries"
     ).fetchone()
-    return {"delivered": sent, "pending": waiting}
+    return {"delivered": sent, "pending": waiting, "total": sent + waiting}
```

## Instructions
Review the proposed changes above against the application baseline.
Identify any logic bugs, data integrity issues, regressions, operational risks,
or deployment conflicts. State clearly which file and line are affected and explain the issue.
