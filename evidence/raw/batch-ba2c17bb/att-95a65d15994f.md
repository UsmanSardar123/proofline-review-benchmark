## Pull Request Review
### Findings
- **File**: `reports.py`
  **Line**: 45
  **Severity**: High
  **Description**: In `history()`, ordering by `scheduled_at DESC, id DESC` while using `WHERE scheduled_at < ?` will cause pagination anomalies or skipped records when multiple deliveries share the exact same `scheduled_at` timestamp. The cursor comparison only checks `scheduled_at` rather than a composite tuple `(scheduled_at, id)`.