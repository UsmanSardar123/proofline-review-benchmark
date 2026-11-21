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