# 03 — Codebase File Guide

This guide catalogs the repository's files, their responsibilities, and flags any **unused, duplicated, outdated, incomplete, or inconsistent** files discovered during inspection.

---

## 1. Root Files

| File | Responsibility | Status / Notes |
| :--- | :--- | :--- |
| [README.md](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/README.md) | Main project overview, quickstart, case table, results | **Outdated / Inconsistent:** Case 02–06 descriptions do not match actual `cases/*/change.patch` or `STANDARD_GROUND_TRUTHS`. |
| [reports.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/reports.py) | Target starter application (report scheduling, history, CSV export, archive, delivery, summary) | Clean baseline (`9b5ac64`). |
| [console.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/console.py) | CLI wrapper for `reports.py` | Clean baseline. |
| [migrations/001_initial.sql](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/migrations/001_initial.sql) | Target app SQLite schema (`deliveries`, `receipts`) | Clean baseline. |
| [benchmark.sqlite](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark.sqlite) | Active benchmark SQLite database (WAL mode) | Contains 4 batches, 26 attempts (5 completed: 1 real + 4 fixture; 21 pending). |
| [ingest_batch.ps1](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/ingest_batch.ps1) | PowerShell batch ingestion script for 22 manual attempts | **Machine-specific:** Hardcodes `C:\Users\hp\AppData\Local\Programs\Python\Python314\python.exe`. |
| [LICENSE](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/LICENSE) | Project license | Standard. |
| [.gitignore](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/.gitignore) | Git ignore rules | Standard. |

---

## 2. Benchmark Package (`benchmark/`)

| Module | Responsibility | Notes |
| :--- | :--- | :--- |
| [benchmark/__init__.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/__init__.py) | Package marker | Minimal. |
| [benchmark/__main__.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/__main__.py) | `python -m benchmark` entrypoint | Delegates to `benchmark.cli.main.main()`. |
| [benchmark/config.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/config.py) | Path resolution, `BASELINE_COMMIT = "9b5ac64"`, env overrides (`BENCHMARK_DB_PATH`, `BENCHMARK_EVIDENCE_DIR`) | Clean. |
| **CLI (`benchmark/cli/`)** | | |
| [benchmark/cli/main.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/cli/main.py) | `argparse` parser for 11 subcommands | Clean. |
| [benchmark/cli/commands.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/cli/commands.py) | Subcommand handlers (`cmd_init_db` .. `cmd_ingest`) | `cmd_run` with `--providers all` only runs `["mock", "anthropic", "openai", "coderabbit"]` (omits `greptile`). |
| **Domain & DB (`benchmark/domain/`, `benchmark/db/`, `benchmark/migrations/`)** | | |
| [benchmark/domain/enums.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/domain/enums.py) | `AttemptStatus`, `ContextCondition`, `AttemptType`, `EvaluationClass`, `DefectCategory` | Clean. |
| [benchmark/domain/models.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/domain/models.py) | 11 domain dataclasses + `now_utc_iso()` | Clean. |
| [benchmark/db/connection.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/db/connection.py) | SQLite connection factory (`PRAGMA foreign_keys=ON`, `busy_timeout=5000`, `journal_mode=WAL`) | Clean. |
| [benchmark/db/migrations.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/db/migrations.py) | Idempotent numbered SQL migration runner | Clean. |
| [benchmark/db/repositories.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/db/repositories.py) | 11 repository classes wrapping SQL CRUD | Clean (872 lines). |
| [benchmark/migrations/001_initial_benchmark.sql](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/migrations/001_initial_benchmark.sql) | 12 tables + 5 indexes | Clean. |
| **Cases & Git (`benchmark/cases/`, `benchmark/git/`)** | | |
| [benchmark/cases/registry.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/cases/registry.py) | Loads & caches cases 01–08 from `cases/` | Clean. |
| [benchmark/cases/validator.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/cases/validator.py) | Validates metadata, `git apply --check`, and JSON blocks in `evidence.md` | Clean. |
| [benchmark/cases/context.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/cases/context.py) | Builds `ReviewContext`, formats prompts, checks `FORBIDDEN_KEYWORDS` | Clean; note `ContextSafetyError` only checks 6 keywords. |
| [benchmark/git/repo.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/git/repo.py) | Git subprocess helpers | Clean. |
| [benchmark/git/isolation.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/git/isolation.py) | Extracts `9b5ac64` via `git archive`, applies patch in temp repo, checks `FORBIDDEN_NAMES` | Implemented & tested, though not invoked by `BenchmarkOrchestrator` during API/manual runs. |
| **Orchestrator & Collector (`benchmark/orchestrator/`, `benchmark/collector/`)** | | |
| [benchmark/orchestrator/engine.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/orchestrator/engine.py) | `BenchmarkOrchestrator`: scheduling, execution, retries, crash recovery, repeats, `ingest_review` | Note: `execute_attempt()` constructs `ReviewContext` directly without calling `ContextManager.build_context()` (bypasses `verify_context_safety` during `run`). |
| [benchmark/collector/collector.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/collector/collector.py) | Validates non-empty response, saves to DB and `RawEvidenceStore` | Clean. |
| [benchmark/collector/storage.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/collector/storage.py) | Writes `<attempt_id>.md` + `<attempt_id>.meta.json` under `evidence/raw/` | Clean. |
| **Providers (`benchmark/providers/`)** | | |
| [benchmark/providers/base.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/providers/base.py) | `BaseProviderAdapter`, `ProviderConfig`, error hierarchy, `mask_secret()`, `handle_http_error()` | Clean. |
| [benchmark/providers/registry.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/providers/registry.py) | Registers 11 provider aliases across 6 adapter classes | Clean. |
| [benchmark/providers/openai.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/providers/openai.py) | `OpenAIAdapter` (HTTP `urllib` + `dry_run` fixture) | Live HTTP untested without `OPENAI_API_KEY`. |
| [benchmark/providers/anthropic.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/providers/anthropic.py) | `AnthropicAdapter` (HTTP `urllib` + `dry_run` fixture) | Live HTTP untested without `ANTHROPIC_API_KEY`. |
| [benchmark/providers/coderabbit.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/providers/coderabbit.py) | `CodeRabbitAdapter` (`auto`/`api`/`cli`/`fixture`) | **Risk:** `auto` silently falls back to synthetic fixture when no key/CLI is present. |
| [benchmark/providers/greptile.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/providers/greptile.py) | `GreptileAdapter` (`auto`/`api`/`fixture`) | **Risk:** `auto` silently falls back to synthetic fixture when no key is present. |
| [benchmark/providers/manual.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/providers/manual.py) | `ManualProviderAdapter` for `chatgpt-web`, `claude-web`, `proofline`, `greptile-web`, `manual` | Raises `ProviderFatalError` if run directly without `dry_run=True` (expects `ingest`). |
| [benchmark/providers/mock.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/providers/mock.py) | `MockProviderAdapter` (`success`, `quota`, `fatal`, `retry_once`) | Clean test double. |
| **Evaluation, Scoring & Reporting (`benchmark/eval/`, `benchmark/scoring/`, `benchmark/reporting/`)** | | |
| [benchmark/eval/extractor.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/eval/extractor.py) | `FindingExtractor`: JSON + Markdown heuristic extraction | Has `KNOWN_FILES` hardcoded to 6 filenames. |
| [benchmark/scoring/matcher.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/scoring/matcher.py) | `FindingMatcher`: location + keyword semantic matching | Clean. |
| [benchmark/scoring/metrics.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/scoring/metrics.py) | `ScoringCalculator`: Precision, Recall, F1, clean-case handling, micro/macro rollups | Clean. |
| [benchmark/scoring/calibration.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/scoring/calibration.py) | `standard-v1`, `strict-v1`, `lenient-v1` profiles with SHA-256 hash | Clean. |
| [benchmark/scoring/heldout.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/scoring/heldout.py) | `PartitionManager`: Calibration (`01,02,03,07`) vs Held-Out (`04,05,06,08`) | Clean; flags `is_overfitted` if `heldout_count == 0` and `cal_f1 > 0.25`. |
| [benchmark/scoring/quality.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/scoring/quality.py) | `FindingQualityEvaluator`: specificity, evidence, actionability, severity | Clean. |
| [benchmark/scoring/service.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/scoring/service.py) | `ScoringService` + `STANDARD_GROUND_TRUTHS` | Clean. |
| [benchmark/reporting/matrix.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/reporting/matrix.py) | `BenchmarkMatrixGenerator` | Minor bug: `matrix[p_id][c_id]` overwrites if a batch has both `CODE_ONLY` and `CODE_AND_SNAPSHOT`. |
| [benchmark/reporting/formatters.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/reporting/formatters.py) | `MarkdownFormatter`, `CSVFormatter`, `JSONFormatter`, `BenchmarkReportGenerator` | Minor bug: `cell.outcome[:2]` renders `TRUE_POSITIVE` as `✓ TR` instead of `✓ TP`. |

---

## 3. Cases, Prompts, Reviews, Evidence, Docs, Reports, AWS, CI, Tests

- **`cases/01..08/`:** All 8 cases are complete, valid, and consistent with `STANDARD_GROUND_TRUTHS`.
- **`prompts/`:** 11 pre-generated Markdown prompts (`case01.md`..`case08.md`, plus `case04_snapshot.md`, `case05_snapshot.md`, `case06_snapshot.md`).
- **`reviews/`:**
  - `claude_case01.md` (2,519 bytes): **Genuine** Claude 3.5 Sonnet review.
  - `chatgpt_case01_existing_raw.md` (3,774 bytes): **Archived/Contaminated** prompt-echo/duplicate file (not ingested).
  - Remaining 21 `*.md` files: **Empty HTML comment placeholders** awaiting manual paste.
  - `collection_metadata.json`: Slightly stale (`"vuf": 2` for `claude-web` `case-01`, while DB has `vuf_count: 0`).
- **`evidence/raw/`:** 53 `batch-*` directories; **51 are orphaned test artifacts** (e.g., `batch-crash-test`) not in `benchmark.sqlite`.
- **`docs/`:** 12 documentation files. `docs/proofline-review-audit.md` Section 4 contains **pre-populated/fabricated findings** referencing non-existent files.
- **`reports/`:** 15 Markdown reports + `reports/batch-7b358964/` (6 exported report files). Some reports (`final_submission_report.md`, `master_execution_status.md`) contain slightly stale test counts (`108` vs actual `113`) or overstate completion readiness.
- **`aws/` & `.github/workflows/`:** 4 AWS files (`deploy.py`, `handler.py`, `stack.json`, `github-roles.yaml`) + 2 workflows (`check.yml`, `aws.yml`).
- **`tests/`:** 19 test files + `__init__.py` totaling 113 tests.
