# Proofline Benchmark Walkthrough Video Script (120 Seconds Max)

**Target Duration:** Exactly 1 minute 50 seconds to 2 minutes (~275 words)  
**Speaking Pace:** ~135 words per minute (deliberate, clear, technical, confident)  
**Candidate:** Usman Ayaz — Software Engineering Intern Take-Home Submission  
**Repository:** [https://github.com/UsmanSardar123/proofline-review-benchmark](https://github.com/UsmanSardar123/proofline-review-benchmark)  
**Target Pull Request:** [PR #1: feat: Proofline AI Pull Request Review Benchmarking Platform](https://github.com/UsmanSardar123/proofline-review-benchmark/pull/1)  

---

## 1. Two-Minute Narration Script

### Segment 1: Architecture & Benchmark Engine (0:00 – 0:25)
> *"Hi Proofline team, I'm Usman Ayaz. Here is my AI pull request review benchmarking platform. I built an end-to-end evaluation engine supporting eight realistic defect cases across calibration and held-out partitions, seven provider adapters, and an isolated Git sandbox that prevents code reviewers from ever seeing answer keys or test harnesses. Every review attempt is cryptographically fingerprinted with SHA-256 hashes and tracked in SQLite."*

### Segment 2: Live Eight-Case Cloudflare Benchmark (0:25 – 0:50)
> *"In Phase 2, I ran an automated live campaign across all eight benchmark cases using Cloudflare Workers AI with Qwen 2.5 Coder 32B at zero-dollar cost. The model achieved a micro F1 of 0.5882 and macro F1 of 0.5833, with 5 True Positives, 6 False Positives, and 1 False Negative—yielding 45.5% precision, 83.3% recall, and 732 Neurons consumed. Its held-out micro F1 dropped to 0.4444, quantitatively measuring the generalization gap on unseen changes."*

### Segment 3: Proofline PR #1 Review & Findings Audit (0:50 – 1:15)
> *"For Phase 3, I integrated Proofline directly on our open Pull Request #1. Proofline completed its review with 11 comments, which I audited and deduplicated into 7 unique findings. Proofline caught a genuine keyset pagination bug where timestamp ties drop rows, and flagged credential logging and CSV memory spikes. However, it also produced two false positives: recommending connection pooling for SQLite's single-writer WAL mode, and questioning transaction atomicity that Python's `with db:` context manager already guarantees."*

### Segment 4: CI Root-Cause & Local Fix Verification (1:15 – 1:40)
> *"When PR #1 ran in CI, GitHub Actions failed. I diagnosed that `actions/checkout` defaulted to `fetch-depth: 1`, omitting baseline commit `9b5ac64` and breaking Git isolation tests. I verified this by reproducing the failure in a controlled shallow test, then implemented Fix P1 by setting `fetch-depth: 0` in `check.yml`. Remote CI verification is currently pending push authorization."*

### Segment 5: Local Test Suite & Conclusion (1:40 – 2:00)
> *"Locally, the complete test suite passes: 148 passed, 2 skipped, and zero failures across 150 tests. The entire platform is reproducible, documented, and ready for your review in PR #1. Thank you for your time and consideration!"*

---

## 2. Word Count & Timing Verification

| Segment | Timing Window | Target Words | Actual Words | Pacing Status |
| :---: | :---: | :---: | :---: | :---: |
| **Segment 1: Architecture** | `0:00 – 0:25` (25s) | ~55 words | 56 words | Perfect (~134 WPM) |
| **Segment 2: Cloudflare Benchmark** | `0:25 – 0:50` (25s) | ~70 words | 73 words | Crisp (~135 WPM) |
| **Segment 3: Proofline Review Audit** | `0:50 – 1:15` (25s) | ~65 words | 65 words | Perfect (~135 WPM) |
| **Segment 4: CI Diagnosis & Fix** | `1:15 – 1:40` (25s) | ~55 words | 51 words | Comfortable (~122 WPM) |
| **Segment 5: Tests & Wrap-up** | `1:40 – 2:00` (20s) | ~40 words | 36 words | Natural close (~110 WPM) |
| **Total** | **1:55 (115s)** | **~280 words** | **281 words** | **Exact 2-Minute Window** |

---

## 3. Audited Benchmark Metrics & Test Ground Truth

### Cloudflare Workers AI Benchmark (`batch-campaign-11221624`)
- **Model:** `@cf/qwen/qwen2.5-coder-32b-instruct`
- **Execution Mode:** `live` (sequential, 8 cases, zero retries, $0.00 cost)
- **True Positives (TP):** `5`
- **False Positives (FP):** `6`
- **False Negatives (FN):** `1`
- **Micro Precision:** `0.4545` (45.45%)
- **Micro Recall:** `0.8333` (83.33%)
- **Micro F1:** `0.5882`
- **Macro F1:** `0.5833`
- **Held-Out Micro F1:** `0.4444` (Cases 04, 05, 06, 08)
- **Neuron Consumption:** `732` Neurons (out of 5,000 daily free tier)

### Verified Skipped Tests (Exact Names from Test Output)
From verbose test runner invocation (`python -m unittest discover tests -p "test_*.py" -v`):
1. **`test_optional_live_anthropic_api`**  
   - *Full path:* `test_provider_integration_phase3.Phase3ProviderIntegrationTests.test_optional_live_anthropic_api`  
   - *Skip Reason in Output:* `Skipping live Anthropic API test (PROOFLINE_LIVE_ANTHROPIC not set)`
2. **`test_optional_live_openai_api`**  
   - *Full path:* `test_provider_integration_phase3.Phase3ProviderIntegrationTests.test_optional_live_openai_api`  
   - *Skip Reason in Output:* `Skipping live OpenAI API test (PROOFLINE_LIVE_OPENAI not set)`

---

## 4. Screen-Recording Sequence & Visual Storyboard

Follow this step-by-step visual sequence while narrating:

```
+--------------------------------------------------------------------------------------------------+
| 0:00 - 0:25 | Screen 1: Architecture & Repository Layout                                        |
|             | • Open VS Code showing project tree: benchmark/, cases/, docs/, reports/.          |
|             | • Switch to docs/benchmark-foundation.md architecture diagram.                     |
+--------------------------------------------------------------------------------------------------+
| 0:25 - 0:50 | Screen 2: Genuine Cloudflare Benchmark Campaign Results                            |
|             | • Display reports/phase_2_cloudflare_benchmark_report.md.                          |
|             | • Highlight 8-case summary table: TP=5, FP=6, FN=1, Micro P=45.5%, Micro R=83.3%,  |
|             |   Micro F1=0.5882, Macro F1=0.5833, Held-Out Micro F1=0.4444, 732 Neurons.         |
|             | • Show terminal command: python -m benchmark report --batch-id batch-campaign...   |
+--------------------------------------------------------------------------------------------------+
| 0:50 - 1:15 | Screen 3: Proofline PR #1 Review & Findings Audit Matrix                           |
|             | • Open GitHub PR #1 in browser showing Proofline review comments.                  |
|             | • Switch to docs/proofline-review-audit.md table:                                 |
|             |   - Highlight PL-01 (Accepted pagination defect).                                  |
|             |   - Highlight PL-02 (Rejected SQLite connection pool false positive).              |
|             |   - Highlight PL-06 (Rejected transaction atomicity false positive).               |
+--------------------------------------------------------------------------------------------------+
| 1:15 - 1:40 | Screen 4: CI Failure Diagnosis & .github/workflows/check.yml Fix                    |
|             | • Show git diff on .github/workflows/check.yml: + fetch-depth: 0.                  |
|             | • Briefly show reports/phase_3_initial_audit.md shallow reproduction output.      |
|             | • Clarify on screen: "Local fix verified; remote push pending authorization".      |
+--------------------------------------------------------------------------------------------------+
| 1:40 - 2:00 | Screen 5: Complete Test Suite & PR Overview                                        |
|             | • Terminal running: uv run python -m unittest discover tests -p "test_*.py"        |
|             | • Highlight final green output: Ran 150 tests ... OK (skipped=2).                  |
|             | • Note 2 skipped tests: test_optional_live_anthropic_api & test_optional_live_openai |
|             | • Return to browser showing GitHub PR #1 title and description.                    |
+--------------------------------------------------------------------------------------------------+
```

---

## 5. Rehearsal Terminal Commands

Run these exact commands during screen recording to populate your terminal:

```powershell
# Step 1: Display benchmark campaign report
uv run python -m benchmark report --batch-id batch-campaign-11221624 --format markdown

# Step 2: Show Git workflow diff for Fix P1
git diff .github/workflows/check.yml

# Step 3: Run the full 150-test benchmark suite live
uv run python -m unittest discover tests -p "test_*.py"
```

---

## 6. Candidate Checklist Before Recording

1. [ ] Set terminal resolution to 1080p (1920x1080) with a clean dark theme.
2. [ ] Open browser tab: `https://github.com/UsmanSardar123/proofline-review-benchmark/pull/1`.
3. [ ] Open VS Code tabs:
   - `reports/phase_2_cloudflare_benchmark_report.md`
   - `docs/proofline-review-audit.md`
   - `.github/workflows/check.yml`
4. [ ] Rehearse speaking along with a 2-minute timer on your phone.
5. [ ] Ensure microphone audio is clean without background noise.
