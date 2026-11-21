\# Pull Request Review: Page report history by scheduled time



\## Description

Show the most recently scheduled deliveries first. The console continues to return an opaque cursor for fetching the next page.



\## Proposed Code Changes (Git Diff)

```diff

diff --git reports.py reports.py

index 7cd951c..e454f5f 100644

\--- reports.py

+++ reports.py

@@ -42,11 +42,11 @@ def history(db, limit, cursor=None):

&#x20;    query = "SELECT id, report, scheduled\_at FROM deliveries"

&#x20;    params = \[]

&#x20;    if cursor is not None:

\-        query += " WHERE id < ?"

\+        query += " WHERE scheduled\_at < ?"

&#x20;        params.append(cursor)

\-    query += " ORDER BY id DESC LIMIT ?"

\+    query += " ORDER BY scheduled\_at DESC, id DESC LIMIT ?"

&#x20;    rows = db.execute(query, (\*params, limit + 1)).fetchall()

\-    next\_cursor = rows\[limit - 1]\[0] if len(rows) > limit else None

\+    next\_cursor = rows\[limit - 1]\[2] if len(rows) > limit else None

&#x20;    return HistoryPage(rows\[:limit], next\_cursor)
ile: reports.py, lines ~44–49 (history)

Bug 1: Rows skipped at page boundaries (data loss)

Cursor is now scheduled_at only. Filter is scheduled_at < ?.
scheduled_at isn’t unique. Many reports can share a timestamp (batch schedules, minute granularity).
If a page ends mid-group of ties, the remaining tied rows are never returned. Next page starts strictly below that timestamp.
Silent omission. Worse than an error.

Bug 2: Sort key and cursor mismatch

Sort is scheduled_at DESC, id DESC. Cursor only carries the first key.
Keyset pagination needs the full sort tuple.

Fix

Cursor must encode both (scheduled_at, id).
Filter: WHERE (scheduled_at, id) < (?, ?). Needs SQLite ≥ 3.15 for row values. Or portable form: WHERE scheduled_at < ? OR (scheduled_at = ? AND id < ?).
next_cursor = (rows[limit-1][2], rows[limit-1][0]).
Keep it opaque: encode as base64 or JSON string.

Regression: Cursor contract change

Old cursor was an id integer. New one is a timestamp.
In-flight cursors from clients or the console (open tabs, bookmarked URLs, retries) will be misread during deploy. id < ? semantics differ entirely from scheduled_at < ?.
Comparing an int id against a timestamp column gives wrong or empty results, with no error.
Version the cursor, or reject old-format cursors explicitly.

Operational risk: Performance

Existing path used primary key order. Cheap.
New ORDER BY scheduled_at DESC, id DESC needs an index on (scheduled_at, id).
Without it: full table scan and sort per page. Degrades as deliveries grows.
Ship the index migration before or with this change. Concurrent index creation if the DB supports it.

Data integrity edge cases

scheduled_at NULL: NULL < ? is never true. NULL rows vanish after page one. Sort position of NULLs also varies by DB. Define the behavior or exclude NULLs explicitly.
Mixed formats or timezones in scheduled_at (strings vs. UTC): lexical comparison breaks ordering. Confirm a single normalized format.
Rows scheduled in the future now sort first. Confirm that’s intended (“most recently scheduled” vs. “most recently delivered”).

Tests missing

Many rows sharing one scheduled_at spanning a page boundary.
Exactly limit and limit + 1 rows.
NULL scheduled_at.
Old-format cursor input.

Verdict: Request changes. Bug 1 is a blocker.




Claude is AI and can make mistakes.
```



\## Instructions

Review the proposed changes above against the application baseline.

Identify any logic bugs, data integrity issues, regressions, operational risks,

or deployment conflicts. State clearly which file and line are affected and explain the issue.

