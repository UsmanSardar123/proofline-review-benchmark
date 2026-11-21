# Pull Request Review: Stream the report export

## Description
Write each delivery to the CSV output as it is read from the database so a large export can start immediately.

## Proposed Code Changes (Git Diff)
```diff
diff --git reports.py reports.py
index 7cd951c..45945d5 100644
--- reports.py
+++ reports.py
@@ -1,6 +1,5 @@
 """Report scheduling, delivery, and export for the operations console."""
 
-import csv
 from dataclasses import dataclass
 from itertools import islice
 from pathlib import Path
@@ -51,11 +50,10 @@ def history(db, limit, cursor=None):
 
 
 def write_export(db, output):
-    writer = csv.writer(output)
-    writer.writerow(["id", "report", "scheduled_at"])
-    rows = db.execute("SELECT id, report, scheduled_at FROM deliveries ORDER BY id").fetchall()
+    output.write("id,report,scheduled_at\n")
+    rows = db.execute("SELECT id, report, scheduled_at FROM deliveries ORDER BY id")
     for row in rows:
-        writer.writerow(row)
+        output.write(",".join(map(str, row)) + "\n")
 
 
 def export_to_sink(db, send):
```

## Instructions
Review the proposed changes above against the application baseline.
Identify any logic bugs, data integrity issues, regressions, operational risks,
or deployment conflicts. State clearly which file and line are affected and explain the issue.