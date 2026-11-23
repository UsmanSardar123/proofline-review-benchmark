# 01 — Executive Summary

**Project:** Proofline AI Pull Request Review Benchmark  
**Local Repository:** `c:\Users\FA22-BSE-018.CUIWAH\Downloads\proofline-review-benchmark\proofline-review-benchmark`  
**GitHub Repository:** `https://github.com/UsmanSardar123/proofline-review-benchmark`  
**Working Branch:** `feature/benchmark-engine` (clean working tree, HEAD `9d37732`)  
**Open Pull Request:** `https://github.com/UsmanSardar123/proofline-review-benchmark/pull/1`  
**Assessment Date:** November 22, 2026  

---

## 1. What We Have Built

The **Proofline AI Pull Request Review Benchmark** is a zero-external-dependency Python CLI application and evaluation platform built on top of a small starter target application (`reports.py` + `console.py` + `migrations/001_initial.sql`, pinned at baseline commit `9b5ac64`).

It solves a core engineering problem: **how do you objectively, reproducibly, and fairly measure whether an AI code reviewer (LLM or PR bot) actually catches real bugs without hallucinating false alarms?**

Instead of relying on subjective "vibe checks," the platform:
1. Takes **8 standardized pull request benchmark cases** (`cases/01` through `cases/08`) derived from the starter report-scheduling app.
2. Generates **leak-free review prompts** (and isolated Git repositories) that never expose ground-truth answers or rubric keywords.
3. Supports **both automated API/CLI providers** (`openai`, `anthropic`, `coderabbit`, `greptile`, `mock`) and **zero-cost manual/web ingestion** (`chatgpt-web`, `claude-web`, `proofline`, `greptile-web`, `manual`).
4. Persists every experiment, batch, attempt, raw response, extracted finding, evaluation, score, and state-transition event in **SQLite (`benchmark.sqlite`, WAL mode)** plus a filesystem mirror under `evidence/raw/`.
5. Scores reviewers deterministically using **Precision, Recall, F1, VUF (Valid Unexpected Findings)**, **duplicate suppression**, **context ablation** (`CODE_ONLY` vs `CODE_AND_SNAPSHOT`), and **Calibration vs Held-Out generalization**.

---

## 2. Is It a CLI, Web App, or Backend Service?

It is **primarily a Python CLI application and local evaluation engine** (`python -m benchmark ...`), paired with:
- A **target sample application** (`reports.py`, `console.py`) that the benchmark cases modify.
- An **AWS serverless deployment fixture** (`aws/handler.py`, `aws/deploy.py`, `aws/stack.json`, `aws/github-roles.yaml`) that packages `reports.py` + `migrations/` into a CloudFormation-managed AWS Lambda function (note: the *benchmark engine itself* does not run on AWS; the *sample report app* is what deploys to AWS).
- **GitHub Actions CI/CD workflows** (`.github/workflows/check.yml`, `.github/workflows/aws.yml`).

There is **no web UI or HTTP server** for the benchmark platform.

---

## 3. Honest Current Position (At a Glance)

| Dimension | Actual Verified State |
| :--- | :--- |
| **Core Benchmark Engine** | **Strong & Working.** 11 CLI commands, SQLite WAL schema (11 domain tables + `schema_migrations`), Git isolation, prompt safety, finding extractor/matcher, scoring, calibration, and reporting are all implemented. |
| **Automated Tests** | **113 tests total:** 111 passed, 2 skipped (live `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` checks), 0 failed, in 14.246s (`python -m unittest discover -s tests -v`). All tests use mocks/dry-runs/temp DBs. |
| **Benchmark Cases (01–08)** | **All 8 valid.** Verified via `CaseValidator`: all 8 patches apply cleanly to `9b5ac64`, and cases 04–06 have valid `evidence.md` JSON snapshots. *Note: `README.md` contains inaccurate descriptions for cases 02–06 that do not match the actual patches/ground truths.* |
| **Real External Reviews** | **Only 1 of 22 manual/web attempts completed.** Only `reviews/claude_case01.md` (`batch-7b358964`, `claude-web`, `case-01`, `CODE_ONLY`, `F1=1.0000`) is a genuine external review. The other 21 `chatgpt-web` / `claude-web` attempts are `PENDING` (their `reviews/*.md` files are empty HTML comment placeholders). |
| **Fixture / Smoke Runs in DB** | **4 synthetic attempts** in `batch-3cee82d4` (`coderabbit` x2, `greptile` x2 on `case-01`) are marked `COMPLETED` in `benchmark.sqlite`, but they came from offline fixture fallback mode (no API keys), **not** genuine external CodeRabbit/Greptile reviews. |
| **Proofline GitHub Integration** | **NOT COMPLETED.** `ManualProviderAdapter` supports `proofline` ingestion, but the Proofline GitHub App has not been installed/triggered on PR #1 and no genuine Proofline review comments exist. *Warning: `docs/proofline-review-audit.md` Section 4 contains pre-populated/fabricated findings (`PL-01`..`PL-07`) referencing non-existent files.* |
| **AWS Readiness** | **Locally packaged & smoke-tested only.** `aws/deploy.py package` + `smoke` pass locally (`commit: 9d37732...`, `receipt_at: 101`). Live AWS CloudFormation deployment, Lambda invocation, CloudWatch verification, and teardown have **NOT been performed**. |
| **Submission Deliverables** | **Pending.** Missing: remaining genuine reviews, Proofline GitHub App review & real audit, live AWS verification (if required by assignment), 2-minute walkthrough video, and application email. |

---

## 4. Key Risks & Discrepancies Found

1. **Documentation vs Reality Drift:**
   - `README.md` (lines 25–32, 77–84) describes Cases 02–06 inaccurately (e.g., calling Case 02 a "Buffer Memory Leak" when the actual patch is an unescaped CSV string-join bug; calling Case 03 a "Transaction Boundary" bug when the actual patch drops remainder jobs in `range()`).
   - `docs/proofline-review-audit.md` Section 4 presents `PL-01`..`PL-07` as if Proofline already reviewed PR #1, citing files that do not exist (`benchmark/db/engine.py`, `scripts/package_lambda.py`, `delivery.py`, `benchmark/eval/scorer.py`).
2. **Fixture Runs Counted Alongside Real Reviews:**
   - `batch-3cee82d4` (4 fixture responses) is counted in `benchmark.sqlite` as `COMPLETED` without a `is_dry_run` or `execution_mode` column distinguishing fixture responses from live API responses.
3. **Orphaned Test Artifacts:**
   - `evidence/raw/` contains **53** `batch-*` directories, **51** of which (including `batch-crash-test`) are leftover test artifacts not present in `benchmark.sqlite`.
4. **Hardcoded Machine Path:**
   - `ingest_batch.ps1` hardcodes `C:\Users\hp\AppData\Local\Programs\Python\Python314\python.exe`.
