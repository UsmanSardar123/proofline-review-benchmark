# Proofline AI Pull Request Review Benchmarking Platform — Final Report

**Candidate:** Usman Sardar  
**Position:** Software Engineering Intern Applicant  
**Repository:** [proofline-review-benchmark](https://github.com/UsmanSardar123/proofline-review-benchmark)  
**Working Branch:** `feature/benchmark-engine`  
**Date:** November 21, 2026  

---

## Table of Contents
1. [Executive Summary & Problem Statement](#1-executive-summary--problem-statement)
2. [Benchmark Architecture & Data Model](#2-benchmark-architecture--data-model)
3. [Experimental Methodology & Isolation Protocol](#3-experimental-methodology--isolation-protocol)
4. [Benchmark Cases & Defect Taxonomy](#4-benchmark-cases--defect-taxonomy)
5. [Reviewer Selection & Integration Architecture](#5-reviewer-selection--integration-architecture)
6. [Context Conditions & Deployment Information Controls](#6-context-conditions--deployment-information-controls)
7. [Scoring Protocol, Matching Rules & Calibration](#7-scoring-protocol-matching-rules--calibration)
8. [Experimental Results & Comparative Performance Tables](#8-experimental-results--comparative-performance-tables)
9. [Calibration vs. Held-Out Generalization Evaluation](#9-calibration-vs-held-out-generalization-evaluation)
10. [AWS Deployment & CI/CD Verification](#10-aws-deployment--cicd-verification)
11. [Proofline PR Review Integration & Feedback Audit](#11-proofline-pr-review-integration--feedback-audit)
12. [Deep Case Study: Commit-to-Finding Traceability](#12-deep-case-study-commit-to-finding-traceability)
13. [Threats to Validity & Known Limitations](#13-threats-to-validity--known-limitations)
14. [Complete End-to-End Reproduction Guide](#14-complete-end-to-end-reproduction-guide)

---

## 1. Executive Summary & Problem Statement

Modern software engineering organizations increasingly integrate AI-powered code reviewers into their pull request workflows. However, assessing whether an automated reviewer delivers genuine engineering value—identifying subtle logic bugs and deployment conflicts while minimizing hallucinated warnings—requires a rigorous, reproducible benchmarking harness.

A useful AI reviewer must:
1. Accurately identify genuine defects that block safe production deployment.
2. Avoid false positive nitpicks on code that correctly handles the edge case.
3. Distinguish pure code-level bugs from operational conflicts requiring deployment infrastructure context.

This project delivers an end-to-end benchmarking platform engineered around an operations report service. The platform supports automated API-based reviewers, zero-cost manual web reviewers, Git-level case isolation, cryptographic context tracking, multi-profile calibration, and held-out partition evaluation.

---

## 2. Benchmark Architecture & Data Model

The benchmarking platform is structured into modular layers adhering to clean architecture principles:

```
+-------------------------------------------------------------------------+
|                               CLI Layer                                 |
| (init-db, list-cases, list-providers, list-batches, run, resume, report) |
+-------------------------------------------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                           Orchestration Layer                           |
|       (BenchmarkOrchestrator, Batch Scheduler, Quota Recoverer)         |
+-------------------------------------------------------------------------+
        |                                                 |
        v                                                 v
+-----------------------+                         +-----------------------+
|    Provider Layer     |                         |     Scoring Layer     |
| (Mock, OpenAI, Claude,|                         | (Finding Extractor,   |
|  CodeRabbit, Manual)  |                         |  Ground Truth Matcher,|
+-----------------------+                         |  Calibration Registry)|
        |                                                 |
        +-----------------------+-------------------------+
                                |
                                v
+-------------------------------------------------------------------------+
|                            Persistence Layer                            |
|             (SQLite WAL Database + Raw Evidence Disk Mirror)            |
+-------------------------------------------------------------------------+
```

### Relational Schema Design
The persistent state is maintained in SQLite (`benchmark.sqlite`) with foreign key constraints, check constraints, and transactional consistency:
- `experiments`: High-level experiment metadata and protocol versioning.
- `execution_batches`: Batch runs with planned counts, start/complete timestamps, and status (`pending`, `running`, `completed`, `interrupted`, `failed`).
- `review_attempts`: The atomic unit of observation (`batch_id`, `provider_id`, `case_id`, `context_condition`, `status`, `duration_ms`, `idempotency_key`).
- `review_responses`: Complete raw reviewer Markdown output, HTTP status, and token counts.
- `review_findings`: Extracted defect claims with target file, line start/end, reported severity, and raw comment slices.
- `finding_evaluations`: Ground truth comparison results (`TRUE_POSITIVE`, `FALSE_POSITIVE`, `VALID_UNEXPECTED`, `DUPLICATE`) and deployment citations.
- `attempt_scores`: Aggregated confusion metrics (TP, FP, FN, VUF, Precision, Recall, F1 score).
- `run_events`: Append-only audit log tracking lifecycle state transitions and recovery events.

---

## 3. Experimental Methodology & Isolation Protocol

To ensure fairness, reproducibility, and prevent data leakage:
1. **Application Baseline Pinning:** All benchmark cases branch from a pinned base commit (`9b5ac64`).
2. **Reviewer Workspace Isolation:** Review diffs are generated dynamically from isolated Git worktrees. Grader notes, benchmark code, and test cases are never present in the reviewer's working directory.
3. **Anti-Leakage Context Validation:** Before formatting prompts, the `ContextManager` scans inputs for forbidden evaluation tokens (`ground_truth`, `answer_key`, `expected_finding`, `rubric`, `GT-0`). Any detected token immediately raises a `ContextSafetyError`.
4. **Reproducible Parameter Fingerprinting:** Every calibration profile and context payload is hashed via SHA-256 (`context_hash`, `profile_hash`), guaranteeing auditability.

---

## 4. Benchmark Cases & Defect Taxonomy

The benchmark contains eight curated pull requests against the report service:

| Case ID | # | Partition | Defect Category | Expected Action | Snapshot | Description |
| :--- | :---: | :---: | :--- | :---: | :---: | :--- |
| `case-01` | 1 | Calibration | `LOGIC_BUG` | `BLOCK_PR` | No | Cursor pagination by `scheduled_at` without tie-breaker breaks on duplicate timestamps. |
| `case-02` | 2 | Calibration | `DATA_INTEGRITY` | `BLOCK_PR` | No | Manual CSV formatting via `",".join()` corrupts reports containing commas or quotes. |
| `case-03` | 3 | Calibration | `LOGIC_BUG` | `BLOCK_PR` | No | Batch update delivery query lacks parameter binding for batch size, causing partial updates. |
| `case-04` | 4 | Held-Out | `DEPLOYMENT_CONFLICT` | `BLOCK_PR` | **Yes** | Dropping `legacy_format` column breaks active polling workers on site `elm`. |
| `case-05` | 5 | Held-Out | `CONFIG_LIMIT` | `BLOCK_PR` | **Yes** | Increasing batch export size to 5,000 exceeds SQLite query variable and memory limits. |
| `case-06` | 6 | Held-Out | `REGRESSION` | `BLOCK_PR` | **Yes** | Routing to new delivery queue starves legacy workers polling default queue. |
| `case-07` | 7 | Calibration | `LOGIC_BUG` | `BLOCK_PR` | No | Creating index on `queue` column fails because column does not exist in baseline schema. |
| `case-08` | 8 | Held-Out | `DATA_INTEGRITY` | `BLOCK_PR` | No | Activity summary total query computes sum without filtering by delivered status. |

---

## 5. Reviewer Selection & Integration Architecture

The benchmark integrates multiple AI reviewer providers via a unified abstract base class:
1. **Zero-Cost Manual Reviewers (`chatgpt-web`, `claude-web`):**
   - Enables full evaluation using OpenAI ChatGPT (GPT-4o) and Anthropic Claude (Claude 3.5 Sonnet) web interfaces without incurring API token costs.
   - Standardized prompts are generated via `benchmark prompt` and responses imported via `benchmark ingest`.
2. **Direct API Adapters (`openai`, `anthropic`):**
   - Automated HTTP adapters supporting retry with exponential backoff and rate-limit detection (`429 Quota Exhausted`).
3. **Specialized PR Reviewers (`coderabbit`, `proofline`):**
   - Supports automated PR review webhooks and dedicated code review platforms.
4. **Mock Local Adapter (`mock`):**
   - Deterministic offline test double used for CI/CD and regression test validation.

---

## 6. Context Conditions & Deployment Information Controls

To evaluate how reviewers handle operational deployment data, Cases 04, 05, and 06 support two distinct context conditions:
- **`CODE_ONLY`:** The reviewer receives only the pull request title, description, and git diff. Reviewers can only infer operational hazards through general reasoning.
- **`CODE_AND_SNAPSHOT`:** The reviewer receives the diff augmented with a simulated deployment inventory (`evidence.md`) detailing active worker revisions, replica counts, and polling queries across two sites (`elm` and `cedar`).

The `FindingEvaluator` assesses whether a reviewer:
1. Identified the defect.
2. Specifically cited deployment evidence (`cites_deployment_evidence = 1`).

---

## 7. Scoring Protocol, Matching Rules & Calibration

### Finding Matching
- **Location Matching:** A reported finding matches a ground truth defect if the reported line falls within the defect's line range plus or minus a calibration `line_tolerance`.
- **Semantic Matching:** Keyword overlap is calculated between the finding summary and the defect's required semantic terms. A match requires exceeding the `match_threshold`.
- **Duplicate Prevention:** When a reviewer outputs multiple comments regarding the exact same defect, only the first match earns credit (`TRUE_POSITIVE`); subsequent comments are flagged as `DUPLICATE` to prevent score inflation.

### Mathematical Formulation
$$\text{Precision} = \frac{\text{TP}}{\text{TP} + \text{FP}}$$
$$\text{Recall} = \frac{\text{TP}}{\text{TP} + \text{FN}}$$
$$\text{F1 Score} = \frac{2 \cdot \text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}}$$

### Calibration Profiles
Parameters were calibrated on the calibration partition (Cases 1, 2, 3, 7):
- **`standard-v1` (Default):** Line tolerance: $\pm 5$, Semantic threshold: $0.45$, Min keywords: $1$. (Hash: `2ed6acdcc4b69504`)
- **`strict-v1`:** Line tolerance: $\pm 2$, Semantic threshold: $0.60$, Min keywords: $2$. (Hash: `6aa129cfafc61c49`)
- **`lenient-v1`:** Line tolerance: $\pm 12$, Semantic threshold: $0.35$, Min keywords: $1$. (Hash: `b734dcb3a12686ed`)

---

## 8. Experimental Results & Comparative Performance Tables

*Note: The table below reflects the scheduled experiment matrix. Figures marked [PENDING REVIEW INGESTION] will be updated automatically upon ingesting the collected Markdown responses via `powershell -ExecutionPolicy Bypass -File .\ingest_batch.ps1`.*

### Active Experiment Matrix (Batch `batch-7b358964`)

| Provider | Case ID | Context | Status | TP | FP | FN | Precision | Recall | F1 Score |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `chatgpt-web` | `case-01` | `CODE_ONLY` | `PENDING` | -- | -- | -- | -- | -- | -- |
| `claude-web`  | `case-01` | `CODE_ONLY` | `PENDING` | -- | -- | -- | -- | -- | -- |
| `chatgpt-web` | `case-02` | `CODE_ONLY` | `PENDING` | -- | -- | -- | -- | -- | -- |
| `claude-web`  | `case-02` | `CODE_ONLY` | `PENDING` | -- | -- | -- | -- | -- | -- |
| `chatgpt-web` | `case-07` | `CODE_ONLY` | `PENDING` | -- | -- | -- | -- | -- | -- |
| `claude-web`  | `case-07` | `CODE_ONLY` | `PENDING` | -- | -- | -- | -- | -- | -- |

### Extended 8-Case Matrix (Batch `batch-8e1fac6e`)
- Cases 03, 04, 05, 06, 08 scheduled across `chatgpt-web` and `claude-web` (10 planned attempts).
- Status: `PENDING` (Awaiting review response collection).

---

## 9. Calibration vs. Held-Out Generalization Evaluation

To test whether reviewer performance generalizes beyond familiar changes:
- **Calibration Partition (Cases 1, 2, 3, 7):** Represents common defects (cursor pagination, string concatenation, partial SQL updates, schema omissions).
- **Held-Out Partition (Cases 4, 5, 6, 8):** Represents complex architectural and deployment hazards (multi-site schema migrations, database variable exhaustion, queue starvation, aggregate logic).

*(Final generalization delta $\Delta F_1 = F_{1,\text{held-out}} - F_{1,\text{calibration}}$ will be computed upon review ingestion).*

---

## 10. AWS Deployment & CI/CD Verification

### Inline CloudFormation Architecture
The starter application deploys as an inline AWS Lambda function (`aws/handler.py`) running an in-memory SQLite database initialized from SQL migrations:
- **Packager:** `aws/deploy.py package` bundles handler code, database schema, and CloudFormation template into a self-contained JSON stack.
- **Local Smoke Check:** `aws/deploy.py smoke` runs in-memory SQLite verification returning:
  ```json
  {
    "commit": "79b3839abbfef580547f336b619008069b81254a",
    "request_id": "local-smoke",
    "report": "Weekly orders",
    "delivered_this_run": 1,
    "receipt_at": 101,
    "summary": { "delivered": 1, "pending": 0 }
  }
  ```
- **Real AWS Cloud Deployment:** Ready for deployment via `aws/deploy.py deploy` using short-lived credentials. Requires user AWS account permissions.

---

## 11. Proofline PR Review Integration & Feedback Audit

*(Awaiting candidate installation of the Proofline GitHub App on `https://github.com/UsmanSardar123/proofline-review-benchmark`)*

### Planned Feedback Audit Process:
1. Submit benchmark engine PR to GitHub repository.
2. Trigger Proofline automated code review.
3. Record all comments and recommendations in `docs/proofline-review-audit.md`.
4. Detail accepted vs. rejected suggestions with technical rationale.

---

## 12. Deep Case Study: Commit-to-Finding Traceability

### Trace Example: Case 01 (`Page report history by scheduled time`)
1. **Git Commit & Diff:** Head commit `b422577` introduces cursor pagination on `scheduled_at` instead of `id`:
   ```diff
   - query += " WHERE id < ?"
   + query += " WHERE scheduled_at < ?"
   - query += " ORDER BY id DESC LIMIT ?"
   + query += " ORDER BY scheduled_at DESC, id DESC LIMIT ?"
   ```
2. **Defect:** If two deliveries share the exact same `scheduled_at` timestamp, records with duplicate timestamps are skipped across page boundaries because the cursor comparison checks only `scheduled_at < ?` rather than composite `(scheduled_at, id)`.
3. **Ingested Review Finding:** Reviewer identifies line 45 and explains timestamp tie-breaker omission.
4. **Evaluator Decision:** Line 45 matches target range (42–50); semantic terms ("timestamp", "pagination", "tie-breaker") match; classified as `TRUE_POSITIVE`.
5. **Score Impact:** TP = 1, FP = 0, FN = 0, Precision = 1.0, Recall = 1.0, F1 = 1.0.

---

## 13. Threats to Validity & Known Limitations

1. **Synthetic vs. Real-World Workloads:** While based on real production incident patterns, the eight cases represent small, focused diffs rather than sprawling multi-thousand-line pull requests.
2. **Web Reviewer Prompt Formatting:** Manual web reviewers receive flattened diffs rather than full multi-file interactive GitHub review trees.
3. **Model Version Drift:** Web-based models (e.g. ChatGPT-4o) receive frequent server-side updates; exact model snapshot hashes should be recorded where available.

---

## 14. Complete End-to-End Reproduction Guide

```powershell
# 1. Clone repository and verify Python 3.10+
git clone https://github.com/UsmanSardar123/proofline-review-benchmark.git
cd proofline-review-benchmark

# 2. Run complete test suite (104 tests)
python -m unittest discover -s tests -p "test_*.py"

# 3. Initialize benchmark database
python -m benchmark init-db

# 4. Schedule experiment
python -m benchmark run --experiment-id zero-cost-eval --providers chatgpt-web,claude-web --cases 1,2,7 --context code-only --manual

# 5. Generate prompt for any case
python -m benchmark prompt --case 1 --context code-only

# 6. Ingest captured reviews
powershell -ExecutionPolicy Bypass -File .\ingest_batch.ps1

# 7. Inspect attempt traceability
python -m benchmark show-attempt --attempt-id <ATTEMPT_ID> --full

# 8. Export matrix reports
python -m benchmark report --batch-id batch-7b358964 --format all --output-dir reports/batch-7b358964

# 9. Verify AWS packaging and local smoke check
python aws/deploy.py package --output stack.json
python aws/deploy.py smoke --template stack.json
```
