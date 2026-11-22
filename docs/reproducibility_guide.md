# Proofline AI Review Benchmark: Reproducibility & Execution Guide

**Document Version:** 1.0.0  
**Candidate:** Usman Ayaz  
**Repository:** [proofline-review-benchmark](file:///c:/Users/hp/Desktop/proofline-review-benchmark)  
**Target Environment:** Cross-platform (Windows, Linux, macOS)  
**Python Runtime:** Python 3.10+ (Verified on Python 3.14.0a2)

---

## 1. Zero-Dependency Architectural Guarantee

The Proofline Benchmark suite was deliberately engineered with **zero external PyPI package dependencies**. The entire engine — including SQLite database persistence, Git worktree manipulation, HTTP provider transport, regex-based finding extraction, scoring calibration, and reporting — runs directly on the Python Standard Library:

- Database: `sqlite3` (WAL mode enabled)
- Git Orchestration: `subprocess` (direct Git CLI bindings, `shell=False`)
- HTTP Transport: `urllib.request` / `urllib.error`
- Concurrency & Process Safety: `threading`, `hashlib`, `json`, `dataclasses`
- Test Harness: `unittest`

No `pip install`, `virtualenv`, or binary compilation is required.

---

## 2. Quickstart: Clean Clone to Verification in Under 60 Seconds

### Step 1: Clone Repository
```bash
git clone https://github.com/UsmanSardar123/proofline-review-benchmark.git
cd proofline-review-benchmark
git checkout feature/benchmark-engine
```

### Step 2: Run the Automated Test Suite (113 Tests)
Execute the complete test suite across all 5 implementation phases:
```bash
# Windows
py -m unittest discover tests

# Linux / macOS
python3 -m unittest discover tests
```
*Expected Output:*
```text
Ran 113 tests in ~11s
OK (skipped=2)
```
*(The 2 skipped tests are live external API checks that skip cleanly when `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` are not set).*

### Step 3: Verify the 8 Benchmark Cases
Verify that all 8 benchmark cases apply cleanly against base commit `9b5ac64` and that prompts are leak-free:
```bash
python -m benchmark cases list --validate
```
*Expected Output:*
```text
All 8 benchmark cases verified cleanly. Zero patch conflicts. Zero ground-truth leakage.
```

---

## 3. Running Benchmark Experiments

### 3.1 Offline Dry-Run Benchmark (Zero Network, Zero Cost)
To run an immediate offline verification benchmark using the built-in mock reviewer:
```bash
python -m benchmark run \
    --experiment quick-smoke \
    --providers mock \
    --cases 1,2,7 \
    --dry-run
```

### 3.2 Zero-Cost Manual Ingestion Workflow (ChatGPT & Claude Web)

To evaluate state-of-the-art web models without paid API keys:

1. **Schedule a Manual Review Batch:**
   ```bash
   python -m benchmark run \
       --experiment my-zero-cost-run \
       --providers chatgpt-web,claude-web \
       --cases 1,2,7 \
       --manual
   ```
   *The CLI outputs the generated `BATCH_ID` and lists planned attempts.*

2. **Generate Sanitized Prompts:**
   ```bash
   # Generate leak-free prompt for Case 01 (Code-Only)
   python -m benchmark prompt --case 1 --context code-only > prompts/case01.md

   # Generate leak-free prompt for Case 04 with Deployment Snapshot
   python -m benchmark prompt --case 4 --context code-and-snapshot > prompts/case04_snap.md
   ```

3. **Feed Prompt into AI Web Interface:**
   - Copy the exact contents of `prompts/case01.md`.
   - Paste into ChatGPT (chatgpt.com) or Claude (claude.ai).
   - Save the raw AI markdown response into `reviews/chatgpt_case01.md` or `reviews/claude_case01.md`.

4. **Ingest and Score the Review:**
   ```bash
   python -m benchmark ingest \
       --batch-id <BATCH_ID> \
       --provider claude-web \
       --case 1 \
       --file reviews/claude_case01.md
   ```
   *The engine extracts findings, evaluates against ground truth `gt-case-01`, scores precision/recall/F1, and commits evidence to `evidence/raw/<BATCH_ID>/`.*

---

## 4. Exporting Benchmark Reports

The benchmark generates multi-format comparative reports (Markdown, JSON, CSV):

```bash
python -m benchmark report \
    --batch-id batch-7b358964 \
    --format all \
    --output-dir reports/batch-7b358964
```

Generated files:
- `batch-7b358964_report.md`: Human-readable markdown comparative analysis.
- `batch-7b358964_report.json`: Machine-readable evaluation metrics and finding metadata.
- `batch-7b358964_matrix.csv`: Case vs Provider performance matrix.
- `batch-7b358964_ablation.csv`: Context ablation study results.
- `batch-7b358964_denominators.csv`: Run volume, completed, pending, and completion rates.
- `batch-7b358964_partition.csv`: Calibration vs Held-out partition generalization scores.

---

## 5. Local AWS Lambda Packaging & Smoke Verification

To verify that the application Lambda package builds cleanly and executes its handler without AWS credentials:

```bash
# Package the application stack
python aws/deploy.py package --output /tmp/report-stack.json

# Smoke test the packaged Lambda handler locally
python aws/deploy.py smoke --template /tmp/report-stack.json
```
*Expected Output:*
```json
{
  "commit": "c51662d...",
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

---

## 6. Directory Structure & Key Files

```text
proofline-review-benchmark/
├── aws/
│   └── deploy.py                 # AWS deployment, local packaging & smoke-test engine
├── benchmark/
│   ├── cases/                    # 8 benchmark cases, patches, and deployment snapshots
│   ├── db/                       # SQLite WAL database, migrations, and repositories
│   ├── domain/                   # Domain entities, value objects, and enums
│   ├── eval/                     # Finding extractor, calibration profiles, and scorer
│   ├── git/                      # Git worktree sandbox, patch application, diff generator
│   ├── orchestrator/             # Batch scheduler, retry policies, run event logger
│   ├── providers/                # Adapters for Anthropic, OpenAI, CodeRabbit, Greptile, Manual
│   └── report/                   # Markdown, JSON, and CSV comparative report generators
├── docs/
│   ├── provider_capability_matrix.md # Full capability status of all 7 adapters
│   ├── proofline-review-audit.md     # PR #1 Proofline review audit and findings matrix
│   └── reproducibility_guide.md      # This guide
├── evidence/
│   └── raw/                      # Cryptographic audit trail of raw reviews and metadata
├── reports/
│   ├── benchmark_comparative_analysis.md # Comprehensive 11-section benchmark analysis
│   └── batch-7b358964/           # Exported report files for active experiment
├── reviews/                      # Pre-formatted review destination files
├── tests/                        # 113 automated unit & integration tests
├── benchmark.sqlite              # Persistent benchmark database
└── README.md                     # Master project overview
```
