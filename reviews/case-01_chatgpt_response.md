## Pull Request Review: Page report history by scheduled time

### Finding 1 — Pagination can skip deliveries with identical scheduled timestamps

**Severity:** High\
**File:** `reports.py`\
**Affected line:** The cursor filter inside `history()`.

The query now uses:

```
WHERE scheduled_at < ?
```

However, the results are ordered using:

```
ORDER BY scheduled_at DESC, id DESC
```

If multiple deliveries have the same `scheduled_at` value, the cursor filter excludes all remaining records with that timestamp on the next page, even when their IDs should place them later in the ordering.

For example, suppose three deliveries have the same scheduled time and the first page ends after the second delivery. The third delivery will be skipped because its timestamp is equal to the cursor, not less than it.

**Suggested fix:**

Use a composite cursor containing both `scheduled_at` and `id`:

```
WHERE scheduled_at < ?
   OR (scheduled_at = ? AND id < ?)
```

The cursor should encode both values, and the next cursor should be generated from the last returned row.

### Overall assessment

The new ordering is reasonable because it displays the most recently scheduled deliveries first, with `id` providing a deterministic tie-breaker.

However, the cursor implementation does not account for that tie-breaker. Pagination can therefore silently omit records.

**Recommendation: Request changes** until composite cursor pagination is implemented and tested with multiple deliveries sharing the same scheduled timestamp.
