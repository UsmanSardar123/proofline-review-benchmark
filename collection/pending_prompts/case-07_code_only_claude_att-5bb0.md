<!--
  METADATA FOR AUTOMATED INGESTION:
  attempt_id: att-5bb0d7133dee
  batch_id: batch-7b358964
  provider_id: claude-web
  case_id: case-07
  context_condition: CODE_ONLY
-->
# BENCHMARK REVIEW PROMPT
- **Case ID:** case-07
- **Attempt ID:** att-5bb0d7133dee
- **Batch ID:** batch-7b358964
- **Provider Target:** claude-web
- **Context Condition:** CODE_ONLY
- **Base Commit:** 9b5ac64
- **Head Commit:** 68ef658

---

# Pull Request Review: Index pending deliveries

## Description
Add a partial index for the worker query that selects due jobs by queue and scheduled time.

## Proposed Code Changes (Git Diff)
```diff
diff --git migrations/002_pending_by_queue.sql migrations/002_pending_by_queue.sql
new file mode 100644
index 0000000..1757bcd
--- /dev/null
+++ migrations/002_pending_by_queue.sql
@@ -0,0 +1,2 @@
+CREATE INDEX deliveries_due_by_queue ON deliveries (queue, scheduled_at, id)
+WHERE delivered_at IS NULL;
```

## Instructions
Review the proposed changes above against the application baseline.
Identify any logic bugs, data integrity issues, regressions, operational risks,
or deployment conflicts. State clearly which file and line are affected and explain the issue.
