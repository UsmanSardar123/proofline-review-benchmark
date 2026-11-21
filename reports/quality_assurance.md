# Proofline AI Review Benchmark — Quality Assurance & Test Audit Report

**Date:** November 21, 2026  
**Test Runner:** Python standard `unittest` via `python -m unittest discover -s tests -p "test_*.py"`  
**Python Executable:** `C:\Users\hp\AppData\Local\Programs\Python\Python314\python.exe` (Python 3.14.0)  
**Platform:** Windows 11 (PowerShell)  
**Overall Result:** **104 tests total — 102 PASSED, 2 SKIPPED, 0 FAILED, 0 ERRORS**  

---

## 1. Test Execution Summary

```
Ran 104 tests in 8.177s

OK (skipped=2)
```

### Breakdown by Test Module

| Test Module | Tests | Status | Scope / Component Tested |
| :--- | :---: | :---: | :--- |
| `tests/test_database.py` | 5 | **PASS** | SQLite connection, WAL mode, foreign keys, schema migrations |
| `tests/test_starter_compat.py` | 4 | **PASS** | Starter app baseline imports, reports module, console execution |
| `tests/test_repositories.py` | 11 | **PASS** | CRUD operations on experiments, batches, providers, attempts, responses |
| `tests/test_case_registry.py` | 6 | **PASS** | BenchmarkCase loading, commit hash mapping, patch file resolution |
| `tests/test_git_isolation.py` | 5 | **PASS** | Temporary branch isolation, patch application, clean workspace restoration |
| `tests/test_context_manager.py` | 6 | **PASS** | `CODE_ONLY` vs `CODE_AND_SNAPSHOT`, prompt generation, anti-leakage checks |
| `tests/test_provider_architecture.py` | 7 | **PASS** | Base provider interface, registration, dry-run fixtures, error mapping |
| `tests/test_coderabbit_adapter.py` | 5 | **PASS** | CodeRabbit payload formatting, authentication checks, dry-run simulation |
| `tests/test_llm_adapters.py` | 6 | **PASS (2 skipped)** | Anthropic & OpenAI adapters (live network tests skipped offline) |
| `tests/test_collector.py` | 6 | **PASS** | ReviewCollector response normalization, SQLite persistence, evidence mirror |
| `tests/test_finding_extractor.py` | 8 | **PASS** | Markdown parsing, bullet point extraction, line regex detection, severity |
| `tests/test_lifecycle.py` | 7 | **PASS** | Attempt state machine: `PENDING -> RUNNING -> COMPLETED / FAILED` |
| `tests/test_reporting_matrix.py` | 8 | **PASS** | Confusion matrix aggregation, Markdown table generation, CSV/JSON export |
| `tests/test_phase2_e2e.py` | 5 | **PASS** | End-to-end review lifecycle with mock adapter |
| `tests/test_provider_integration_phase3.py` | 8 | **PASS** | Multi-provider dispatch, error handling, rate-limit backoff simulation |
| `tests/test_scoring_calibration_phase4.py` | 10 | **PASS** | Ground-truth matching, TP/FP/FN calculation, calibration profile hashes |
| `tests/test_cli_automation_phase5.py` | 13 | **PASS** | CLI subcommands: `run`, `resume`, `report`, `show-attempt`, `calibrate` |
| `tests/test_manual_ingest.py` | 15 | **PASS** | Manual review prompt generation, batch scheduling, review file ingestion, duplicate attempt rejection, force overwrite, audit traceability |

---

## 2. Explanation of Skipped Tests

Two tests in `tests/test_llm_adapters.py` were skipped:
1. `test_anthropic_live_api_call`: Skipped because `ANTHROPIC_API_KEY` is not set in the environment.
2. `test_openai_live_api_call`: Skipped because `OPENAI_API_KEY` is not set in the environment.

*Note:* Both adapters gracefully fall back to deterministic mock fixtures when running with `--dry-run` or when API keys are absent, preventing runtime crashes.

---

## 3. AWS Local Smoke Verification

Execution of `aws/deploy.py smoke` on the generated CloudFormation template:

```powershell
& "C:\Users\hp\AppData\Local\Programs\Python\Python314\python.exe" aws/deploy.py package --output aws_package_test.json
& "C:\Users\hp\AppData\Local\Programs\Python\Python314\python.exe" aws/deploy.py smoke --template aws_package_test.json
```

**Output:**
```json
{
  "commit": "79b3839abbfef580547f336b619008069b81254a",
  "request_id": "local-smoke",
  "report": "Weekly orders",
  "delivered_this_run": 1,
  "receipt_at": 101,
  "summary": {
    "delivered": 1,
    "pending": 0
  }
}
```
**Result:** **PASS**. The starter application deploys into an in-memory SQLite database, runs migrations, executes the worker, and returns a valid delivery receipt.

---

## 4. Known Technical Limitations & Boundaries

1. **Local vs Cloud Execution:** The local smoke check uses `request_id: local-smoke`. It proves code compatibility but does not prove live AWS IAM, CloudWatch, or API Gateway configuration until executed in a real AWS account.
2. **Offline Manual Providers:** Zero-cost manual providers (`chatgpt-web`, `claude-web`) depend on accurate file ingestion by the user. If an empty or whitespace file is provided, `benchmark ingest` rejects the input with an error code to protect data integrity.
3. **Partition Generalization:** All calibration profiles are fingerprinted with SHA-256 hashes (`standard-v1`: `2ed6acdcc4b69504`). Modifying parameters invalidates the hash, preventing unrecorded tuning on the held-out partition.
