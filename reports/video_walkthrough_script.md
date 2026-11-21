# Proofline Benchmark Walkthrough Video Script (120 Seconds Max)

**Target Duration:** Exactly 1 minute 50 seconds to 2 minutes  
**Tone:** Confident, technical, concise, engineering-focused  
**Candidate:** Usman Sardar — Software Engineering Intern Applicant  

---

## Storyboard & Timing Breakdown

### Segment 1: Introduction & Architecture (0:00 – 0:25)
- **Visual:** Terminal showing repository root with git branch `feature/benchmark-engine`, then briefly switching to architecture diagram in `reports/final_benchmark_report.md`.
- **Narration:**
  > *"Hi Proofline team, I'm Usman Sardar. Here is a walkthrough of my AI pull request review benchmarking platform. The core goal was to build a system that an engineer can easily operate to compare multiple AI reviewers on the same code changes without leaking answer keys, and trace any final score directly back to raw evidence."*

---

### Segment 2: CLI Operations & Zero-Cost Review Ingestion (0:25 – 0:50)
- **Visual:** Terminal running `python -m benchmark list-cases` and `python -m benchmark list-providers`. Then displaying a generated prompt with `python -m benchmark prompt --case 1 --context code-only`.
- **Narration:**
  > *"The platform provides 11 CLI subcommands. We support paid APIs like OpenAI and Anthropic, alongside a zero-cost manual ingestion pipeline. Using `benchmark prompt`, we format standardized PR diffs and deployment snapshots while enforcing strict anti-leakage rules—zero ground truth or rubrics are ever exposed to the model. We then ingest genuine reviews from ChatGPT or Claude via `benchmark ingest`."*

---

### Segment 3: Scoring, Ground Truth Matching & Traceability (0:50 – 1:15)
- **Visual:** Terminal running `python -m benchmark show-attempt --attempt-id <ATTEMPT_ID> --full`. Scroll through raw response, extracted findings, and confusion matrix.
- **Narration:**
  > *"Once a review is ingested, our finding extractor parses line numbers and reported severities. The scoring engine evaluates findings against ground truth defects using line-tolerance and semantic keyword matching. Using `benchmark show-attempt`, we can trace any attempt from its raw review text, extracted findings, True and False Positives, down to its F1 score and lifecycle audit logs."*

---

### Segment 4: Calibration, Held-Out Generalization & Snapshot Ablation (1:15 – 1:35)
- **Visual:** Terminal running `python -m benchmark calibrate`, then briefly showing the comparative matrix in `reports/batch-7b358964/report.md`.
- **Narration:**
  > *"To ensure fairness, we split the eight cases into calibration and held-out partitions, fingerprinting calibration profiles with SHA-256 hashes to prevent unrecorded parameter tuning. For Cases 4, 5, and 6, we designed a deployment snapshot ablation study, comparing code-only reviews against snapshot-augmented reviews to measure whether operational context turns False Negatives into True Positives."*

---

### Segment 5: AWS Verification, Test Suite & Conclusion (1:35 – 2:00)
- **Visual:** Terminal running `python aws/deploy.py smoke --template ...` showing successful receipt timestamp `101`, followed by `python -m unittest discover -s tests -p "test_*.py"` showing 104 passing tests.
- **Narration:**
  > *"We verified the AWS Lambda inline packaging and local smoke check, confirming report delivery receipts and zero-pending queues. The entire system is covered by 104 automated tests with zero failures. Everything is documented, reproducible, and ready for review in the pull request. Thank you for your consideration!"*

---

## Exact Commands Rehearsed for Recording

```powershell
$py = "C:\Users\hp\AppData\Local\Programs\Python\Python314\python.exe"

# 1. Cases & Providers overview
& $py -m benchmark list-cases
& $py -m benchmark list-providers

# 2. Prompt generation
& $py -m benchmark prompt --case 1 --context code-only

# 3. Attempt inspection and traceability
& $py -m benchmark show-attempt --attempt-id att-c0ff417e95fb --full

# 4. Calibration profiles
& $py -m benchmark calibrate

# 5. AWS Smoke check
& $py aws/deploy.py smoke --template aws_package_test.json

# 6. Complete test suite
& $py -m unittest discover -s tests -p "test_*.py"
```
