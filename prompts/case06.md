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