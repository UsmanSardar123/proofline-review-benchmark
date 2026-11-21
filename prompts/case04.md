# Pull Request Review: Retire the legacy delivery column

## Description
Remove the legacy report format column from the deliveries table. New exports use the CSV writer.

## Proposed Code Changes (Git Diff)
```diff
diff --git migrations/002_retire_format.sql migrations/002_retire_format.sql
new file mode 100644
index 0000000..05e5c5a
--- /dev/null
+++ migrations/002_retire_format.sql
@@ -0,0 +1 @@
+ALTER TABLE deliveries DROP COLUMN legacy_format;
```

## Instructions
Review the proposed changes above against the application baseline.
Identify any logic bugs, data integrity issues, regressions, operational risks,
or deployment conflicts. State clearly which file and line are affected and explain the issue.