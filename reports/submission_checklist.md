# Proofline AI Review Benchmark — Official Assignment Submission Checklist

**Candidate:** Usman Sardar  
**Position:** Software Engineering Intern  
**Repository:** `https://github.com/UsmanSardar123/proofline-review-benchmark`  
**Working Branch:** `feature/benchmark-engine`  

---

## Assignment Requirements Checklist

### 1. Operational Benchmark System
- [x] **Reproducible CLI commands:** Clean CLI implemented with 11 subcommands (`init-db`, `list-cases`, `list-providers`, `list-batches`, `run`, `resume`, `report`, `show-attempt`, `calibrate`, `prompt`, `ingest`).
- [x] **Add next provider easily:** Abstract `AIReviewerProvider` base class and `ProviderRegistry` allow adding a new reviewer in fewer than 40 lines of code.
- [x] **Run identical cases across reviewers:** Standardized prompts generated from clean Git diffs with SHA-256 context tracking.
- [x] **Crash recovery and resumability:** Interrupted or quota-halted runs can be recovered with `benchmark resume --batch-id <id>` with zero duplicate attempt executions.
- [x] **Trace score back to raw review:** `benchmark show-attempt --attempt-id <id> --full` displays full provenance, raw review text, extracted findings, ground truth defect, and score calculation.

### 2. Breadth of Real Reviews & Denominators
- [x] **Two providers to prove workflow:** `chatgpt-web` (GPT-4o) and `claude-web` (Claude 3.5 Sonnet) integrated via zero-cost manual ingestion.
- [x] **Provider-by-case denominator matrix:** Reports display completed, quota stopped, execution errors, and unattempted cases.
- [x] **Honest reporting:** No mock fixtures substituted for genuine reviews; live reviews count toward provider coverage only upon actual receipt.
- [ ] **Completed reviews collected:** Awaiting user collection of the 6 initial reviews (`batch-7b358964`) and 10 extension reviews (`batch-8e1fac6e`).

### 3. Fair Experiment Design
- [x] **Credit rules decided before reading output:** Strict ground truth definitions established in database migrations before runs.
- [x] **Answer key and rubric isolation:** Context manager actively checks for forbidden evaluation tokens (`ground_truth`, `answer_key`, `expected_finding`, `rubric`, `GT-0`) to prevent answer leakage.
- [x] **Pinned code and settings:** Application pinned to baseline `9b5ac64`; calibration profiles pinned by SHA-256 parameter hashes.
- [x] **Calibration vs Held-Out separation:** Calibration cases (1, 2, 3, 7) separated from held-out evaluation cases (4, 5, 6, 8).
- [x] **Ablation on deployment context:** Cases 4, 5, and 6 evaluated under both `code-only` and `code-and-snapshot` conditions.

### 4. Working Knowledge of Systems (AWS & CI/CD)
- [x] **PR checks and CI workflows:** `.github/workflows/check.yml` tests PRs automatically on GitHub Actions.
- [x] **AWS packaging and local smoke test:** `aws/deploy.py package` and `smoke` verify inline CloudFormation packaging and SQLite execution.
- [ ] **Live AWS deployment & verification:** Awaiting candidate deployment of CloudFormation stack `ai-review-bench` into AWS account and capturing Lambda invocation receipt.
- [ ] **Stack teardown:** `aws/deploy.py delete` after collecting delivery receipt.

### 5. Proofline Integration
- [x] **Proofline adapter implemented:** `ProoflineAdapter` and `ManualProviderAdapter` ready.
- [ ] **Proofline GitHub App installed:** Candidate installs app on repository and triggers review on PR.
- [ ] **Feedback audit:** Document which Proofline suggestions were accepted (with code changes) vs rejected (with reasons).

### 6. Submission Deliverables
- [ ] **Clean Pull Request:** Open PR from `feature/benchmark-engine` to `main` with detailed description.
- [ ] **Read access granted:** Grant read permissions to Proofline hiring team on GitHub.
- [ ] **Two-minute video:** Record concise terminal walkthrough demonstrating benchmark execution, traceability, and engineering decisions.
- [ ] **Application email:** Send email to `intern-applicants@proofline.sh` with PR link, video link, and availability.
