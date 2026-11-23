# 05 — Benchmark Experiment Status

This report audits all **8 benchmark cases**, all **4 experiment batches** in `benchmark.sqlite`, and all **review files** in `reviews/`.

---

## 1. Audit of All 8 Benchmark Cases

All 8 cases were verified by inspecting `cases/01..08/{title.txt, body.md, change.patch, evidence.md}`, `benchmark/scoring/service.py` (`STANDARD_GROUND_TRUTHS`), and running `CaseRegistry().validate_all()`.

| Case | Title | Changed File(s) | Actual Bug / Issue (from `change.patch`) | Expected Reviewer Detection & Ground Truth | Reproducible? | Ground Truth Valid? | Prompt Isolated? |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| **01** | Page report history by scheduled time | `reports.py` | `history()` changes `WHERE id < ?` to `WHERE scheduled_at < ?` while sorting `ORDER BY scheduled_at DESC, id DESC`. | Detect keyset cursor bug: identical `scheduled_at` timestamps cause skipped/dropped rows at page boundaries (`LOGIC_BUG`, lines `42-50`, `BLOCK_PR`). | Yes | Yes | Yes (`prompts/case01.md`) |
| **02** | Stream the report export | `reports.py` | Removes `import csv` and `csv.writer`, replacing it with `",".join(map(str, row)) + "\n"`. | Detect unescaped CSV concatenation corrupting report names with commas/quotes (`DATA_INTEGRITY`, lines `50-57`, `BLOCK_PR`). *Note: `README.md` wrongly calls this a buffer memory leak.* | Yes | Yes | Yes (`prompts/case02.md`) |
| **03** | Batch queued deliveries | `reports.py` | `deliver_due()` loops `range(0, len(jobs) - batch_size + 1, batch_size)` with `batch_size = 20`. | Detect off-by-one/remainder bug: drops remaining jobs when `len(jobs) < 20` or not a multiple of 20 (`LOGIC_BUG`, lines `73-90`, `BLOCK_PR`). *Note: `README.md` wrongly calls this a transaction boundary bug.* | Yes | Yes | Yes (`prompts/case03.md`) |
| **04** | Retire the legacy delivery column | `migrations/002_retire_format.sql` | `ALTER TABLE deliveries DROP COLUMN legacy_format;` | **With `evidence.md` (`inventory-204`):** Detect that `elm` site still has 2 replicas of `workers-17` polling `SELECT id, legacy_format FROM deliveries...` (`DEPLOYMENT_CONFLICT`, line `1`, `BLOCK_PR`). | Yes | Yes | Yes (`prompts/case04.md`, `case04_snapshot.md`) |
| **05** | Increase export batch size | `reports.py` | Changes `EXPORT_BATCH_SIZE = 25` to `50`. | **With `evidence.md` (`archive-318`):** Detect that `cedar` receiver has `max_rows_per_request: 40`, so 50-row batches will be rejected in full (`CONFIG_LIMIT`, line `10`, `BLOCK_PR`). | Yes | Yes | Yes (`prompts/case05.md`, `case05_snapshot.md`) |
| **06** | Use the new delivery queue | `reports.py` | Changes `DELIVERY_QUEUE = "reports"` to `"report-dispatch"`. | **With `evidence.md` (`subscriptions-416`):** Detect that `elm` workers only subscribe to `["reports"]`, starving newly scheduled jobs (`DEPLOYMENT_CONFLICT`, line `9`, `BLOCK_PR`). | Yes | Yes | Yes (`prompts/case06.md`, `case06_snapshot.md`) |
| **07** | Index pending deliveries | `migrations/002_pending_by_queue.sql` | Adds partial index `CREATE INDEX deliveries_due_by_queue ON deliveries (queue, scheduled_at, id) WHERE delivered_at IS NULL;` | Benign optimization (`PERFORMANCE`, lines `1-2`, expected action `APPROVE`). | Yes | Yes | Yes (`prompts/case07.md`) |
| **08** | Include a total in the activity summary | `reports.py` | Adds `"total": sent + waiting` to `summary()` return dict. | Benign additive change (`CONTRACT_CHANGE`, line `86`, expected action `APPROVE`). | Yes | Yes | Yes (`prompts/case08.md`) |

---

## 2. Database Experiment Batches (`benchmark.sqlite`)

Queried directly from `benchmark.sqlite` in read-only mode:

| Batch ID | Experiment ID | Batch Name | Status | Planned | Completed | Pending | Failed | Genuine External? |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `batch-7b358964` | `zero-cost-eval` | Initial Free AI Reviewer Experiment | `pending` | 6 | 1 | 5 | 0 | **1 genuine** (`claude-web` Case 01) |
| `batch-8e1fac6e` | `full-8case-eval` | Full 8-Case Extension | `pending` | 10 | 0 | 10 | 0 | 0 |
| `batch-8aca4c4d` | `snapshot-ablation` | Deployment Snapshot Experiment | `pending` | 6 | 0 | 6 | 0 | 0 |
| `batch-3cee82d4` | `exp-20261121` | Additional Reviewer Smoke | `completed` | 4 | 4 | 0 | 0 | **0 genuine** (all 4 are synthetic fixture fallbacks) |
| **TOTAL** | **4 experiments** | | | **26** | **5** | **21** | **0** | **1 genuine / 4 fixture** |

- **Invalid / Contaminated Attempts:** `0` currently in DB. Previously contaminated `chatgpt-web` Case 01 response was archived to `reviews/chatgpt_case01_existing_raw.md` and the attempt (`att-c0ff417e95fb`) was reset to `PENDING` (confirmed in `reviews/collection_metadata.json`).

---

## 3. Provider Breakdown (Genuine vs Fixture vs Pending)

| Provider | Genuine External Reviews | Fixture / Mock Results | Pending Attempts | Current Genuine Score |
| :--- | :---: | :---: | :---: | :--- |
| **Claude (`claude-web`)** | **1** (`case-01`, `CODE_ONLY`) | 0 | 10 | `TP=1, FP=0, FN=0, P=1.0, R=1.0, F1=1.0` |
| **ChatGPT (`chatgpt-web`)** | **0** | 0 | 11 | None yet |
| **CodeRabbit (`coderabbit`)** | **0** | 2 (`case-01`, `CODE_ONLY` & `CODE_AND_SNAPSHOT`) | 0 | *Fixture only (`TP=0, FN=1, F1=0.0`)* |
| **Greptile (`greptile`)** | **0** | 2 (`case-01`, `CODE_ONLY` & `CODE_AND_SNAPSHOT`) | 0 | *Fixture only (`TP=0, FN=1, F1=0.0`)* |
| **Proofline (`proofline`)** | **0** | 0 | 0 | Not scheduled in `benchmark.sqlite` yet |

---

## 4. Every Missing Review & Exact Expected Output File

All **21** pending attempts in `benchmark.sqlite` map to placeholder files in `reviews/` (currently 1–8 line HTML comments):

- **Batch `batch-7b358964` (5 missing):**
  1. `chatgpt-web`, Case 01 (`CODE_ONLY`) → `reviews/chatgpt_case01.md`
  2. `chatgpt-web`, Case 02 (`CODE_ONLY`) → `reviews/chatgpt_case02.md`
  3. `claude-web`, Case 02 (`CODE_ONLY`) → `reviews/claude_case02.md`
  4. `chatgpt-web`, Case 07 (`CODE_ONLY`) → `reviews/chatgpt_case07.md`
  5. `claude-web`, Case 07 (`CODE_ONLY`) → `reviews/claude_case07.md`
- **Batch `batch-8e1fac6e` (10 missing):**
  6. `chatgpt-web`, Case 03 (`CODE_ONLY`) → `reviews/chatgpt_case03.md`
  7. `claude-web`, Case 03 (`CODE_ONLY`) → `reviews/claude_case03.md`
  8. `chatgpt-web`, Case 04 (`CODE_ONLY`) → `reviews/chatgpt_case04.md`
  9. `claude-web`, Case 04 (`CODE_ONLY`) → `reviews/claude_case04.md`
  10. `chatgpt-web`, Case 05 (`CODE_ONLY`) → `reviews/chatgpt_case05.md`
  11. `claude-web`, Case 05 (`CODE_ONLY`) → `reviews/claude_case05.md`
  12. `chatgpt-web`, Case 06 (`CODE_ONLY`) → `reviews/chatgpt_case06.md`
  13. `claude-web`, Case 06 (`CODE_ONLY`) → `reviews/claude_case06.md`
  14. `chatgpt-web`, Case 08 (`CODE_ONLY`) → `reviews/chatgpt_case08.md`
  15. `claude-web`, Case 08 (`CODE_ONLY`) → `reviews/claude_case08.md`
- **Batch `batch-8aca4c4d` (6 missing):**
  16. `chatgpt-web`, Case 04 (`CODE_AND_SNAPSHOT`) → `reviews/chatgpt_case04_snapshot.md`
  17. `claude-web`, Case 04 (`CODE_AND_SNAPSHOT`) → `reviews/claude_case04_snapshot.md`
  18. `chatgpt-web`, Case 05 (`CODE_AND_SNAPSHOT`) → `reviews/chatgpt_case05_snapshot.md`
  19. `claude-web`, Case 05 (`CODE_AND_SNAPSHOT`) → `reviews/claude_case05_snapshot.md`
  20. `chatgpt-web`, Case 06 (`CODE_AND_SNAPSHOT`) → `reviews/chatgpt_case06_snapshot.md`
  21. `claude-web`, Case 06 (`CODE_AND_SNAPSHOT`) → `reviews/claude_case06_snapshot.md`
- **Proofline PR #1 Review (not yet in DB):**
  - Expected output file per `reports/human_action_checklist.md`: `reviews/proofline_pr_review.md` (or `reviews/proofline_pr1.md` per `docs/proofline-review-audit.md`).
