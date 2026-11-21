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