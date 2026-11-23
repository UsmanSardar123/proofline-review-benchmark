# 04 — Feature Completion Matrix

Every feature below was verified directly against source files, database records, CLI execution, or automated tests.

**Status Definitions:**
- `COMPLETE AND VERIFIED` — Implemented and verified via running tests/CLI/artifacts.
- `IMPLEMENTED BUT NOT FULLY VERIFIED` — Code exists and unit/mock tests pass, but live external behavior or edge cases are unverified.
- `PARTIALLY IMPLEMENTED` — Core scaffolding exists, but key parts or genuine data are missing.
- `NOT IMPLEMENTED` — Missing.
- `BLOCKED BY EXTERNAL ACTION` — Waiting on manual user action, external service, or credentials.
- `NOT APPLICABLE` — Outside system scope.

---

| Feature | Status | Verified Evidence & Honest Notes |
| :--- | :--- | :--- |
| **Database and migrations** | `COMPLETE AND VERIFIED` | `benchmark/db/connection.py`, `migrations.py`, `001_initial_benchmark.sql`. WAL mode, FK enforcement, idempotent migrations verified by `test_database.py` and live `benchmark.sqlite` inspection. |
| **Benchmark cases (01–08)** | `COMPLETE AND VERIFIED` | All 8 cases in `cases/01..08/` validated via `CaseRegistry().validate_all()`: 8/8 `is_valid=True`, `patch_applies_cleanly=True`, 04–06 `snapshot_json_valid=True`. |
| **Git worktree / repo isolation** | `IMPLEMENTED BUT NOT FULLY VERIFIED` | `GitIsolationManager` (`benchmark/git/isolation.py`) tested in `test_git_isolation.py`; extracts `9b5ac64` via `git archive` and checks `FORBIDDEN_NAMES`. However, `BenchmarkOrchestrator` does not use it during `run`/`ingest`. |
| **Prompt generation** | `COMPLETE AND VERIFIED` | `ContextManager.format_review_prompt()` & `cmd_prompt` verified; 11 clean prompts exist in `prompts/`. |
| **Prompt leakage protection** | `IMPLEMENTED BUT NOT FULLY VERIFIED` | `ContextManager.verify_context_safety()` blocks 6 `FORBIDDEN_KEYWORDS` and is tested in `test_context_manager.py`. However, `BenchmarkOrchestrator.execute_attempt()` builds `ReviewContext` directly without calling `ContextManager.build_context()`. |
| **Provider adapters** | `IMPLEMENTED BUT NOT FULLY VERIFIED` | 6 adapter classes (`Mock`, `Manual`, `OpenAI`, `Anthropic`, `CodeRabbit`, `Greptile`) pass 111 offline tests, **but** live `OpenAI`/`Anthropic` tests are skipped (`PROOFLINE_LIVE_*` unset) and `CodeRabbit`/`Greptile` silently fall back to synthetic fixtures without API keys. |
| **Manual review ingestion** | `COMPLETE AND VERIFIED` | `cmd_ingest` + `BenchmarkOrchestrator.ingest_review()` verified in `test_manual_ingest.py` and used to ingest `reviews/claude_case01.md` into `batch-7b358964`. |
| **Finding extraction** | `COMPLETE AND VERIFIED` | `FindingExtractor` (`benchmark/eval/extractor.py`) supports JSON and Markdown heuristics; verified in `test_finding_extractor.py` and `test_engine_hardening_sprint1.py`. Hardcodes `KNOWN_FILES`. |
| **Finding matching** | `COMPLETE AND VERIFIED` | `FindingMatcher` (`benchmark/scoring/matcher.py`) combines line-window proximity ($\pm 5$ lines default) and keyword matching; verified in `test_scoring_calibration_phase4.py`. |
| **Duplicate suppression** | `COMPLETE AND VERIFIED` | `ScoringService.evaluate_attempt()` marks first matching finding `TRUE_POSITIVE` and subsequent matches `DUPLICATE`; verified in DB for `claude-web` `case-01` (1 TP, 5 DUPLICATE) and `test_engine_hardening_sprint1.py`. |
| **Scoring metrics** | `COMPLETE AND VERIFIED` | `ScoringCalculator` computes TP, FP, FN, VUF, Precision, Recall, F1, clean-case handling (07–08), and micro/macro rollups; verified in `test_scoring_calibration_phase4.py`. |
| **Calibration** | `COMPLETE AND VERIFIED` | `standard-v1`, `strict-v1`, `lenient-v1` profiles with SHA-256 hashes + `benchmark calibrate` CLI verified in `test_scoring_calibration_phase4.py` and `test_cli_automation_phase5.py`. |
| **Held-out evaluation** | `IMPLEMENTED BUT NOT FULLY VERIFIED` | `PartitionManager` enforces Calibration (`01,02,03,07`) vs Held-Out (`04,05,06,08`) and anti-leakage checks in unit tests, **but** 0 held-out attempts are completed in `benchmark.sqlite` yet (and `is_overfitted` triggers falsely when `heldout_count == 0`). |
| **CLI** | `COMPLETE AND VERIFIED` | 11 subcommands in `benchmark/cli/main.py` verified via `test_cli_automation_phase5.py` and live `list-cases` / `list-providers` runs. |
| **Report generation** | `COMPLETE AND VERIFIED` | Markdown, JSON, and 4 CSV outputs verified in `test_reporting_matrix.py` and `reports/batch-7b358964/`. Minor display bug: `✓ TR` instead of `✓ TP` in Markdown matrix. |
| **Raw evidence storage** | `COMPLETE AND VERIFIED` | `RawEvidenceStore` dual-writes `.md` + `.meta.json` under `evidence/raw/`. Note: 51 orphaned test batch folders exist on disk. |
| **AWS Lambda** | `IMPLEMENTED BUT NOT FULLY VERIFIED` | `aws/handler.py` works locally via `aws/deploy.py smoke` (in-memory SQLite), **not** deployed or invoked in live AWS Lambda. |
| **API Gateway** | `NOT APPLICABLE` | Not part of the architecture; `aws/stack.json` defines only a Lambda Function and CloudWatch LogGroup (invoked via AWS CLI `lambda invoke`). |
| **CloudFormation** | `IMPLEMENTED BUT NOT FULLY VERIFIED` | `aws/stack.json` and `aws/github-roles.yaml` exist and `aws/deploy.py package` validates inline template size (< 51,200 bytes), **not** deployed to AWS. |
| **IAM configuration** | `IMPLEMENTED BUT NOT FULLY VERIFIED` | `aws/github-roles.yaml` defines OIDC `DeploymentRole` + `RuntimeRole`, **not** deployed in an AWS account. |
| **GitHub Actions** | `IMPLEMENTED BUT NOT FULLY VERIFIED` | `.github/workflows/check.yml` and `aws.yml` are well-structured; `aws.yml` requires `AWS_REGION`, `AWS_DEPLOY_ROLE_ARN`, `AWS_LAMBDA_ROLE_ARN` repo variables and `main` branch. |
| **Proofline GitHub integration** | `BLOCKED BY EXTERNAL ACTION` | `ManualProviderAdapter` supports `proofline` ingestion, **but** Proofline GitHub App is not installed/triggered on PR #1 and no genuine Proofline comments exist. |
| **Security** | `IMPLEMENTED BUT NOT FULLY VERIFIED` | API keys are read from env vars and masked via `mask_secret()`; parameterized SQL queries used in repositories; GitHub Actions pin SHAs with `persist-credentials: false`. |
| **Documentation** | `PARTIALLY IMPLEMENTED` | Extensive `docs/` and `reports/`, **but** `README.md` has wrong bug summaries for Cases 02–06 and `docs/proofline-review-audit.md` has fabricated `PL-01`..`PL-07` findings. |
| **Reproducibility** | `COMPLETE AND VERIFIED` | Zero external dependencies (Python stdlib only), pinned `9b5ac64` baseline, SHA-256 `context_hash` and `profile_hash`, deterministic dry-run fixtures, and `tests/__init__.py` temp isolation. |
