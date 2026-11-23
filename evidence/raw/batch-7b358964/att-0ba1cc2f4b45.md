# Pull Request Review: Stream the report export

### Finding 1 — Manual CSV serialization corrupts fields containing commas, quotes, or newlines

**Severity:** High\
**File:** `reports.py`\
**Affected function:** `write_export()`\
**Affected lines:** The `output.write(",".join(map(str, row)) + "\n")` statement.

The change replaces `csv.writer()` with manual string concatenation. This does not correctly escape CSV values.

For example, if a report name contains a comma, such as `"Daily, Operations Report"`, the generated output will contain an extra column instead of preserving the report name as one field.

Values containing quotation marks or newline characters can also produce malformed CSV records. This can cause downstream CSV consumers to interpret exported data incorrectly.

**Suggested fix:**

Keep `csv.writer()` and iterate over the database cursor directly:

```
writer = csv.writer(output)
writer.writerow(["id", "report", "scheduled_at"])

rows = db.execute(
    "SELECT id, report, scheduled_at FROM deliveries ORDER BY id"
)

for row in rows:
    writer.writerow(row)
```

This preserves proper CSV escaping while still avoiding `fetchall()`, allowing rows to be processed incrementally.

### Finding 2 — NULL values are serialized differently

**Severity:** Medium\
**File:** `reports.py`\
**Affected function:** `write_export()`

The previous implementation uses `csv.writer()`, which serializes `None` values as empty fields by default.

The new implementation uses `map(str, row)`, which converts `None` into the literal string `"None"`.

This changes the exported data format and may break downstream consumers that expect empty CSV fields for missing values.

**Suggested fix:**

Retain `csv.writer()` rather than manually converting database values to strings.

### Overall assessment

The intention to stream database results is good. Removing `fetchall()` allows the database cursor to be iterated incrementally.

However, replacing the CSV library with manual string concatenation introduces data-corruption risks and changes NULL-value handling.

**Recommendation: Request changes.** Preserve `csv.writer()` while retaining cursor-based iteration.