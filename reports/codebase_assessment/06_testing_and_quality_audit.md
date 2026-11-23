# 06 — Testing and Quality Audit

## 1. Automated Test Suite Execution Results

Executed without modifying any code or database:
```powershell
python -m unittest discover -s tests -v
```
- **Total Tests Discovered:** `113`
- **Passed:** `111`
- **Skipped:** `2`
  - `test_optional_live_anthropic_api` (`PROOFLINE_LIVE_ANTHROPIC` not set)
  - `test_optional_live_openai_api` (`PROOFLINE_LIVE_OPENAI` not set)
- **Failed:** `0`
- **Errors:** `0`
- **Execution Time:** `14.246s`
- **Coverage:** Not measured (stdlib-only repo; `coverage.py` is not installed).

**Important Distinction:** All 111 passing tests are **local/offline** tests using `MockProviderAdapter`, `dry_run=True` fixtures, `unittest.mock`, or temporary SQLite databases. **Zero** live external API or AWS cloud integrations were verified by this test run.

---

## 2. Test Suite Inventory (19 Test Files)

- `test_database.py`, `test_repositories.py` — SQLite WAL, FKs, migrations, repository CRUD.
- `test_case_registry.py`, `test_context_manager.py`, `test_git_isolation.py` — 8 cases, prompt formatting, keyword safety, isolated temp Git repos.
- `test_provider_architecture.py`, `test_llm_adapters.py`, `test_coderabbit_adapter.py`, `test_greptile_adapter.py`, `test_provider_integration_phase3.py` — adapter registry, secret masking, HTTP error mapping (`urllib` mocked), dry-run/fixture modes, plus 2 skipped live API tests.
- `test_collector.py`, `test_finding_extractor.py`, `test_lifecycle.py`, `test_phase2_e2e.py` — dual storage, Markdown/JSON extraction, retries/quota/crash recovery.
- `test_scoring_calibration_phase4.py`, `test_reporting_matrix.py`, `test_cli_automation_phase5.py`, `test_manual_ingest.py`, `test_engine_hardening_sprint1.py`, `test_starter_compat.py` — matching, calibration profiles, held-out isolation, matrices, CLI parsing, `ingest`, `reports.py` compatibility.

---

## 3. Untested Modules & Coverage Gaps

1. **`aws/deploy.py` & `aws/handler.py`:** Zero unit tests in `tests/`. Verified only via `aws/deploy.py package` + `smoke` (which runs in `.github/workflows/check.yml`). `deploy`, `verify`, and `delete` against real AWS are untested.
2. **`benchmark/__main__.py`:** Not directly tested as a subprocess (`python -m benchmark`), though `cli.main.main()` is tested.
3. **Live HTTP parsing for `CodeRabbitAdapter` & `GreptileAdapter`:** Only mocked/fixture paths are tested; real CodeRabbit/Greptile API response schemas are unverified.
4. **PowerShell script (`ingest_batch.ps1`):** Untested on this machine (hardcoded `C:\Users\hp\...` path).

---

## 4. Code Quality, Weaknesses & Security Findings

1. **Silent Fixture Fallback in `CodeRabbitAdapter` and `GreptileAdapter`:**
   - In `mode="auto"`, missing `CODERABBIT_API_KEY` / `GREPTILE_API_KEY` silently returns a canned fixture instead of raising `ProviderAuthenticationError`. This caused `batch-3cee82d4` to record synthetic responses as `COMPLETED` in `benchmark.sqlite`.
2. **Prompt Safety Check Bypassed in `BenchmarkOrchestrator.execute_attempt()`:**
   - `execute_attempt()` (in `benchmark/orchestrator/engine.py:193`) constructs `ReviewContext(...)` directly instead of calling `ContextManager.build_context()`, skipping `verify_context_safety()`.
3. **Matrix Key Collision (`benchmark/reporting/matrix.py:161-218`):**
   - `matrix[p_id][c_id]` is keyed only by `(provider_id, case_id)`, so if a batch includes both `CODE_ONLY` and `CODE_AND_SNAPSHOT`, one overwrites the other in the main matrix table.
4. **Markdown Legend Mismatch (`benchmark/reporting/formatters.py:45`):**
   - `cell.outcome[:2]` prints `✓ TR` for `TRUE_POSITIVE` while the legend states `✓ TP`.
5. **False Overfitting Alert (`benchmark/scoring/heldout.py:64-65`):**
   - When `heldout_count == 0`, `held_f1` defaults to `0.0`, so any `cal_f1 > 0.25` triggers `is_overfitted = True` (`⚠️ Overfitting Risk`).
6. **Security Posture:**
   - **Good:** API keys are read from env vars, masked via `BaseProviderAdapter.mask_secret()`, SQL queries use `?` placeholders, and GitHub Actions pin action SHAs with `persist-credentials: false`.
   - **Minor:** `benchmark/db/migrations.py:71` uses an f-string for `PRAGMA user_version = {version};` (safe here because `version` is cast to `int`, though worth noting).
