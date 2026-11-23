# Phase 2 Progress & Status Report — Benchmark Experiments & Automation Pipeline

**Date:** November 22, 2026  
**Repository:** `https://github.com/UsmanSardar123/proofline-review-benchmark`  
**Branch:** `feature/benchmark-engine`  
**Base Commit:** `9d37732`  
**Current Phase:** Phase 2 (Benchmark Experiments, Ingestion & Automation Pipeline)  
**Status:** Ingestion & Automation Pipeline Active — **3 Genuine Reviews Completed, 19 Pending**

---

## 1. Executive Summary

Phase 2 focuses on genuine benchmark experiment execution, zero-cost manual reviewer response ingestion, and pipeline automation. All operations have been conducted strictly within local project confines without touching Git history, remote GitHub branches, or AWS cloud infrastructure.

### Key Milestones Achieved:
1. **Automation Pipeline (`python -m benchmark automate`):** Built a unified, reproducible CLI engine that synchronizes pending review prompts, scans `reviews/` with 3-tier metadata matching, ingests genuine reviews, computes SHA-256 evidence hashes, prevents duplicates, extracts findings, calculates metrics, and regenerates batch reports.
2. **Genuine External Reviews Ingested (3 total):**
   - **Claude 3.5 Sonnet (Case 01, CODE_ONLY):** `att-e0ae3808d089` in `batch-7b358964` (TP=1, FP=0, FN=0, F1=1.0000).
   - **ChatGPT / GPT-6 (Case 01, CODE_ONLY):** `att-c0ff417e95fb` in `batch-7b358964` (TP=1, FP=0, FN=0, F1=1.0000).
   - **ChatGPT / GPT-6 (Case 02, CODE_ONLY):** `att-0ba1cc2f4b45` in `batch-7b358964` (TP=1, FP=0, FN=0, F1=1.0000).
3. **Synthetic Fixtures Preserved:** 4 smoke/fixture attempts preserved with `execution_mode='fixture'` in `batch-3cee82d4`.
4. **Pending Review Attempts:** 19 remaining attempts systematically organized in `collection/pending_prompts/` with anti-leak prompt files.
5. **Automated Test Suite:** **121 tests total (119 passed, 2 skipped offline API checks, 0 failures, 0 errors)**.

---

## 2. Experiment Database State & Inventory

### Database Summary:
| Batch ID | Experiment ID | Batch Name | Planned | Completed | Pending | Genuine Reviews | Fixtures |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `batch-7b358964` | `zero-cost-eval` | Initial Free AI Reviewer Exp | 6 | 3 | 3 | 3 | 0 |
| `batch-8e1fac6e` | `full-8case-eval` | Full 8-Case Extension | 10 | 0 | 10 | 0 | 0 |
| `batch-8aca4c4d` | `snapshot-ablation` | Deployment Snapshot Exp | 6 | 0 | 6 | 0 | 0 |
| `batch-3cee82d4` | `exp-20261121` | Additional Reviewer Smoke | 4 | 4 | 0 | 0 | 4 |
| **Total** | | | **26** | **7** | **19** | **3** | **4** |

---

## 3. Verified Genuine Review Records

All completed genuine reviews have been evaluated against case ground truth with dual storage (`benchmark.sqlite` + raw evidence files):

| Attempt ID | Batch ID | Case | Provider | Context | Mode | TP | FP | FN | VUF | F1 | Raw Evidence File |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `att-e0ae3808d089` | `batch-7b358964` | `case-01` | `claude-web` | `CODE_ONLY` | `live` | 1 | 0 | 0 | 2 | 1.0000 | `evidence/raw/batch-7b358964/att-e0ae3808d089.md` |
| `att-c0ff417e95fb` | `batch-7b358964` | `case-01` | `chatgpt-web` | `CODE_ONLY` | `live` | 1 | 0 | 0 | 0 | 1.0000 | `evidence/raw/batch-7b358964/att-c0ff417e95fb.md` |
| `att-0ba1cc2f4b45` | `batch-7b358964` | `case-02` | `chatgpt-web` | `CODE_ONLY` | `live` | 1 | 0 | 0 | 0 | 1.0000 | `evidence/raw/batch-7b358964/att-0ba1cc2f4b45.md` |

Each raw evidence file has a matching `.meta.json` sidecar storing the content SHA-256 hash, timestamps, model metadata, and ingestion execution mode.

---

## 4. Pending Reviews Collection Package (19 Remaining)

The 19 pending review attempts are organized in `collection/pending_prompts/`:

| # | Case ID | Case Title | Provider | Context Condition | Batch ID | Attempt ID | Prompt File |
| :-: | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `case-02` | Stream the report export | `claude-web` | `CODE_ONLY` | `batch-7b358964` | `att-2629b40a9666` | `case-02_code_only_claude_att-2629.md` |
| 2 | `case-03` | Batch queued deliveries | `chatgpt-web` | `CODE_ONLY` | `batch-8e1fac6e` | `att-2c30ac581db0` | `case-03_code_only_chatgpt_att-2c30.md` |
| 3 | `case-03` | Batch queued deliveries | `claude-web` | `CODE_ONLY` | `batch-8e1fac6e` | `att-3988adbbc39f` | `case-03_code_only_claude_att-3988.md` |
| 4 | `case-04` | Retire legacy delivery column | `chatgpt-web` | `CODE_AND_SNAPSHOT` | `batch-8aca4c4d` | `att-466d4194ecef` | `case-04_code_and_snapshot_chatgpt_att-466d.md` |
| 5 | `case-04` | Retire legacy delivery column | `claude-web` | `CODE_AND_SNAPSHOT` | `batch-8aca4c4d` | `att-5028cc3f12e0` | `case-04_code_and_snapshot_claude_att-5028.md` |
| 6 | `case-04` | Retire legacy delivery column | `chatgpt-web` | `CODE_ONLY` | `batch-8e1fac6e` | `att-b1377bcb7bc8` | `case-04_code_only_chatgpt_att-b137.md` |
| 7 | `case-04` | Retire legacy delivery column | `claude-web` | `CODE_ONLY` | `batch-8e1fac6e` | `att-969af64be053` | `case-04_code_only_claude_att-969a.md` |
| 8 | `case-05` | Increase export batch size | `chatgpt-web` | `CODE_AND_SNAPSHOT` | `batch-8aca4c4d` | `att-836b91f3b28c` | `case-05_code_and_snapshot_chatgpt_att-836b.md` |
| 9 | `case-05` | Increase export batch size | `claude-web` | `CODE_AND_SNAPSHOT` | `batch-8aca4c4d` | `att-e36d85f2240b` | `case-05_code_and_snapshot_claude_att-e36d.md` |
| 10 | `case-05` | Increase export batch size | `chatgpt-web` | `CODE_ONLY` | `batch-8e1fac6e` | `att-8c2e145b504b` | `case-05_code_only_chatgpt_att-8c2e.md` |
| 11 | `case-05` | Increase export batch size | `claude-web` | `CODE_ONLY` | `batch-8e1fac6e` | `att-d0cdd8768c72` | `case-05_code_only_claude_att-d0cd.md` |
| 12 | `case-06` | Use the new delivery system | `chatgpt-web` | `CODE_AND_SNAPSHOT` | `batch-8aca4c4d` | `att-f620d60e5076` | `case-06_code_and_snapshot_chatgpt_att-f620.md` |
| 13 | `case-06` | Use the new delivery system | `claude-web` | `CODE_AND_SNAPSHOT` | `batch-8aca4c4d` | `att-f965cdbb31df` | `case-06_code_and_snapshot_claude_att-f965.md` |
| 14 | `case-06` | Use the new delivery system | `chatgpt-web` | `CODE_ONLY` | `batch-8e1fac6e` | `att-2a56a9c459ca` | `case-06_code_only_chatgpt_att-2a56.md` |
| 15 | `case-06` | Use the new delivery system | `claude-web` | `CODE_ONLY` | `batch-8e1fac6e` | `att-470ea9a28633` | `case-06_code_only_claude_att-470e.md` |
| 16 | `case-07` | Clean pass case | `chatgpt-web` | `CODE_ONLY` | `batch-7b358964` | `att-cbe5400d576f` | `case-07_code_only_chatgpt_att-cbe5.md` |
| 17 | `case-07` | Clean pass case | `claude-web` | `CODE_ONLY` | `batch-7b358964` | `att-5bb0d7133dee` | `case-07_code_only_claude_att-5bb0.md` |
| 18 | `case-08` | Retry transient failures | `chatgpt-web` | `CODE_ONLY` | `batch-8e1fac6e` | `att-8a22c53c514b` | `case-08_code_only_chatgpt_att-8a22.md` |
| 19 | `case-08` | Retry transient failures | `claude-web` | `CODE_ONLY` | `batch-8e1fac6e` | `att-5a753f436114` | `case-08_code_only_claude_att-5a75.md` |

---

## 5. Automation Pipeline Features & Safeguards

The pipeline command `python -m benchmark automate` incorporates the following design:

1. **Pending Attempt Discovery:** Queries `AttemptRepository.list_all()` to find all attempts with `status == 'pending'`.
2. **Prompt Generation:** Emits clean Markdown prompts with metadata headers. Prompts never reveal the defect description, severity, or ground truth lines.
3. **Three-Tier Ingestion Matching:**
   - *Tier 1:* Explicit metadata comment header in the review file (primary, deterministic).
   - *Tier 2:* Key-value metadata block (`Case:`, `Provider:`, `Context:`).
   - *Tier 3:* Structured filename parsing.
4. **Duplicate Protection:** Computes SHA-256 of the review text and checks for matching hashes before ingesting.
5. **Finding Extraction & Evaluation:** Runs `BenchmarkOrchestrator._evaluate_attempt()` with duplicate-suppressed scoring.
6. **Reporting:** Exports Markdown, JSON, and CSV tables for each touched batch.
7. **Zero-API Safety:** Operates entirely locally without triggering external network calls.
