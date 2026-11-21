# Pull Request: Proofline AI Pull Request Review Benchmarking Platform

**Target Branch:** `main`  
**Working Branch:** `feature/benchmark-engine`  
**Candidate:** Usman Sardar (Software Engineering Intern Candidate)  

---

## 1. Overview & Objective

This pull request implements the **Proofline AI Pull Request Review Benchmarking System** designed to evaluate, compare, and calibrate automated AI code reviewers across identical, reproducible pull requests.

The platform measures real-world review capabilities on a realistic Python report service across eight distinct review cases, incorporating:
- Multi-provider review execution and manual ingestion for zero-cost evaluation ($0 budget).
- Strict isolation of review context to prevent ground-truth defect leakage.
- Deterministic scoring mathematics (TP, FP, FN, Precision, Recall, F1).
- Calibration profiles vs. held-out evaluation datasets.
- Operational deployment snapshot ablation analysis (Cases 04, 05, 06).
- End-to-end crash recovery, resumability, and raw response audit traceability.
- CloudFormation packaging and deployment validation on AWS Lambda.

---

## 2. Key Architecture & Components

```
proofline-review-benchmark/
├── benchmark/
│   ├── cases/               # BenchmarkCase registry, Git diff isolation, ContextManager
│   ├── cli/                 # CLI subcommands (run, resume, report, show-attempt, calibrate, prompt, ingest)
│   ├── collector/           # Dual storage engine (SQLite + evidence/raw/ disk mirror)
│   ├── db/                  # SQLite connection, schema migrations, and repository layer
│   ├── domain/              # Clean domain dataclasses and enums
│   ├── extractor/           # Regex & semantic finding extraction from Markdown
│   ├── orchestrator/        # Batch scheduling, dispatch loop, quota recovery, review ingestion
│   ├── providers/           # Provider adapters (Manual, OpenAI, Anthropic, CodeRabbit, Proofline, Mock)
│   ├── reporting/           # Markdown, CSV, and JSON matrix report generator
│   └── scoring/             # Location & semantic matching, calibration profiles, held-out manager
├── aws/                     # Lambda handler, CloudFormation packaging & smoke verification
├── cases/                   # 8 benchmark review cases with patches and deployment snapshots
├── migrations/              # Application SQL migrations
├── prompts/                 # Pre-generated, un-leaked review prompts
├── reports/                 # Quality assurance, execution audit, and submission reports
└── tests/                   # 104 automated unit, integration, and CLI tests
```

---

## 3. Core Implementation Highlights

### Database & State Machine
- SQLite database (`benchmark.sqlite`) with write-ahead logging (WAL), strict foreign key constraints, and transactional migrations.
- Complete lifecycle audit tracking in `run_events` (`STATE_TRANSITION`, `API_DISPATCH`, `QUOTA_EXHAUSTED`, `RECOVERED`).
- Five-state attempt state machine: `PENDING -> RUNNING -> COMPLETED / FAILED / QUOTA_EXHAUSTED`.

### Zero-Cost Manual Review Ingestion
To conduct genuine AI reviewer experiments without paid API keys, the system introduces:
1. `benchmark prompt --case <N> --context <C>`: Generates clean Markdown prompts formatting the PR title, body, and git diff without leaking ground truth defects.
2. `benchmark ingest --batch-id <B> --provider <P> --case <N> --file <F>`: Ingests raw reviews from ChatGPT (GPT-4o) and Claude (Claude 3.5 Sonnet) web interfaces into scheduled attempts, triggering automatic finding extraction and scoring.
3. [ingest_batch.ps1](file:///c:/Users/hp/Desktop/proofline-review-benchmark/ingest_batch.ps1): Automated script to batch-import multiple reviews and export matrix reports.

### Fair Experiment Protocol & Ground-Truth Isolation
- Context manager scans prompts for forbidden tokens (`ground_truth`, `answer_key`, `expected_finding`, `rubric`) ensuring zero reviewer leakage.
- Cases 01, 02, 03, and 07 form the **Calibration Partition** (used to tune line tolerances and keyword thresholds).
- Cases 04, 05, 06, and 08 form the **Held-Out Partition** (evaluated with frozen calibration parameters).
- Calibration profiles are cryptographically fingerprinted using SHA-256 hashes (`standard-v1`: `2ed6acdcc4b69504`).

### AWS Deployment & Invocation
- Embedded CloudFormation packager in `aws/deploy.py` creates inline Lambda deployments.
- Local smoke test runs memory SQLite check returning receipt timestamp `101`, 1 delivered, 0 pending, with genuine commit hash.
- Clear distinction maintained between local simulation (`request_id: local-smoke`) and live AWS invocation.

---

## 4. Verification & Test Results

```
python -m unittest discover -s tests -p "test_*.py"
Ran 104 tests in 8.177s — OK (skipped=2)
```

- **102 tests passed, 2 skipped** (the 2 skipped are live external network tests requiring paid API keys).
- **Zero failures, zero errors.**
- Verified compatibility with base application and SQLite schema.

---

## 5. End-to-End Reproduction Instructions

```powershell
# 1. Initialize database and apply migrations
python -m benchmark init-db

# 2. Inspect cases and registered providers
python -m benchmark list-cases
python -m benchmark list-providers

# 3. Schedule a benchmark batch
python -m benchmark run --experiment-id my-eval --providers mock --cases all --context code-only --dry-run

# 4. Generate standardized review prompts
python -m benchmark prompt --case 1 --context code-only

# 5. Ingest external review markdown
python -m benchmark ingest --batch-id my-eval --provider chatgpt-web --case 1 --file reviews/chatgpt_case01.md

# 6. Trace an attempt back to raw review and score
python -m benchmark show-attempt --attempt-id <ATTEMPT_ID> --full

# 7. Generate benchmark reports
python -m benchmark report --batch-id my-eval --format all --output-dir reports/my-eval

# 8. Run full test suite
python -m unittest discover -s tests -p "test_*.py"

# 9. Verify AWS packaging and local smoke check
python aws/deploy.py package --output stack.json
python aws/deploy.py smoke --template stack.json
```
