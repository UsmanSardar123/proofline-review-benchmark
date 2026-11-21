# Proofline GitHub App Installation & PR Review Audit Guide

**Repository:** `https://github.com/UsmanSardar123/proofline-review-benchmark`  
**Target Pull Request:** `feature/benchmark-engine` -> `main`  
**Purpose:** Mandatory Proofline assignment requirement to obtain an authentic automated PR review of our project changes and evaluate Proofline's findings.

---

## 1. Installation Procedure for Candidate

To install Proofline on your repository:
1. Navigate to **[https://proofline.sh/](https://proofline.sh/)** or the **[GitHub Marketplace: Proofline](https://github.com/marketplace/proofline)**.
2. Sign in with your GitHub account (`UsmanSardar123`).
3. Select **Install GitHub App** and choose your private repository:
   `UsmanSardar123/proofline-review-benchmark`.
4. Review requested permissions:
   - **Pull requests:** Read & write (to post review comments and line summaries).
   - **Issues & Checks:** Read & write (to create status check annotations).
   - **Repository contents:** Read-only (to read diffs and application source).
5. Authorize and complete installation.

---

## 2. Triggering the PR Review

1. Push latest verified changes on `feature/benchmark-engine`:
   ```bash
   git push origin feature/benchmark-engine
   ```
2. Open a Pull Request from `feature/benchmark-engine` into `main`:
   - Title: `feat: Proofline AI Pull Request Review Benchmarking Platform`
   - Base branch: `main`
   - Compare branch: `feature/benchmark-engine`
3. Proofline automatically triggers a webhook upon PR creation and analyzes the changes.
4. If a re-review is needed, comment on the PR:
   `@proofline review`

---

## 3. Recording and Auditing Proofline's Findings

Once Proofline completes its review on your pull request:
1. Copy Proofline's summary and line comments into `reviews/proofline_pr_review.md`.
2. Evaluate each finding in the audit table below:

### Findings Audit Matrix

| # | File & Line | Proofline Finding Summary | Category | Decision (Accept / Reject) | Technical Rationale & Actions Taken |
| :-: | :--- | :--- | :--- | :-: | :--- |
| **1** | `reports.py:45` | Example: Cursor keyset pagination tie-breaker missing | Logic Bug | **ACCEPT** | Added `(scheduled_at, id)` composite cursor tuple to eliminate boundary drops. |
| **2** | `benchmark/db/...` | Example: Connection pooling recommendation | Performance | **REJECT** | SQLite in WAL mode with single-writer architecture already handles benchmark concurrency without thread pool overhead. |

---

## 4. Ingesting Proofline Review into Benchmark Platform

Once saved to `reviews/proofline_pr_review.md`, ingest Proofline's review using:
```powershell
& "C:\Users\hp\AppData\Local\Programs\Python\Python314\python.exe" -m benchmark ingest --batch-id full-8case-eval --provider proofline --case 1 --file reviews/proofline_pr_review.md --model "proofline-pr"
```
