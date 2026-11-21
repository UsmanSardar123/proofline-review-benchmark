# Pull Request Review: Page report history by scheduled time

## Description
Show the most recently scheduled deliveries first. The console continues to return an opaque cursor for fetching the next page.

## Proposed Code Changes (Git Diff)
```diff
diff --git reports.py reports.py
index 7cd951c..e454f5f 100644
--- reports.py
+++ reports.py
@@ -42,11 +42,11 @@ def history(db, limit, cursor=None):
     query = "SELECT id, report, scheduled_at FROM deliveries"
     params = []
     if cursor is not None:
-        query += " WHERE id < ?"
+        query += " WHERE scheduled_at < ?"
         params.append(cursor)
-    query += " ORDER BY id DESC LIMIT ?"
+    query += " ORDER BY scheduled_at DESC, id DESC LIMIT ?"
     rows = db.execute(query, (*params, limit + 1)).fetchall()
-    next_cursor = rows[limit - 1][0] if len(rows) > limit else None
+    next_cursor = rows[limit - 1][2] if len(rows) > limit else None
     return HistoryPage(rows[:limit], next_cursor)
```

## Instructions
Review the proposed changes above against the application baseline.
Identify any logic bugs, data integrity issues, regressions, operational risks,
or deployment conflicts. State clearly which file and line are affected and explain the issue.