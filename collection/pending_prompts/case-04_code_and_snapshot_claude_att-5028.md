<!--
  METADATA FOR AUTOMATED INGESTION:
  attempt_id: att-5028cc3f12e0
  batch_id: batch-8aca4c4d
  provider_id: claude-web
  case_id: case-04
  context_condition: CODE_AND_SNAPSHOT
-->
# BENCHMARK REVIEW PROMPT
- **Case ID:** case-04
- **Attempt ID:** att-5028cc3f12e0
- **Batch ID:** batch-8aca4c4d
- **Provider Target:** claude-web
- **Context Condition:** CODE_AND_SNAPSHOT
- **Base Commit:** 9b5ac64
- **Head Commit:** 420baea

---

# Pull Request Review: Retire the legacy delivery column

## Description
Remove the legacy report format column from the deliveries table. New exports use the CSV writer.

## Operational & Deployment Context
Deployment inventory from the report service simulator, recorded immediately before the proposed migration. Each entry lists every active worker revision, its replica count, and the prepared read it issues when polling the deliveries table. Each site has its own database. The migration runs online while the listed workers continue polling.

```json
{
  "observation": "inventory-204",
  "observed_at": "2026-10-21T09:00:00Z",
  "sites": {
    "elm": [
      {"revision": "workers-17", "replicas": 2, "poll_sql": "SELECT id, legacy_format FROM deliveries WHERE delivered_at IS NULL"},
      {"revision": "workers-18", "replicas": 3, "poll_sql": "SELECT id, report FROM deliveries WHERE delivered_at IS NULL"}
    ],
    "cedar": [
      {"revision": "workers-18", "replicas": 4, "poll_sql": "SELECT id, report FROM deliveries WHERE delivered_at IS NULL"}
    ]
  }
}
```

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
