# Proofline Internship Application Email Draft

**To:** `intern-applicants@proofline.sh`  
**Subject:** Software Engineering Intern - Usman Ayaz  

---

Dear Proofline Engineering Team,

I am writing to submit my completed take-home assignment for the Software Engineering Intern position at Proofline.

I have engineered a production-grade, zero-external-dependency benchmarking platform designed to objectively evaluate, compare, and calibrate automated AI pull request reviewers across eight realistic review cases.

### Key Highlights of My Submission:

1. **Pluggable Multi-Provider Architecture (7 Adapters):**
   Unified adapter interface supporting direct paid APIs (`openai`, `anthropic`), developer PR review tools (`coderabbit`, `greptile`), native GitHub PR review ingestion (`proofline`), deterministic test harnesses (`mock`), and Cloudflare Workers AI (`cloudflare` running Qwen 2.5 Coder 32B) at strict zero-dollar ($0.00) spend.

2. **Fair Experiment Protocol & Zero Ground-Truth Leakage:**
   Strictly isolated reviewer inputs via ephemeral Git worktrees to ensure zero answer or rubric leakage, divided cases into Calibration (01, 02, 03, 07) and Held-Out (04, 05, 06, 08) partitions to detect prompt overfitting, and cryptographically fingerprinted calibration profiles (`standard-v1`).

3. **Phase 2 — Live Eight-Case Cloudflare Workers AI Benchmark:**
   Conducted an automated, live benchmark campaign (`batch-campaign-11221624`) using Qwen 2.5 Coder 32B across all 8 cases. The model achieved a micro F1 of 0.5714 and macro F1 of 0.5417 (TP=4, FP=4, FN=2), consuming exactly 732 Neurons out of our 5,000 daily free quota ($0.00 spend). The held-out F1 dropped to 0.4444, quantitatively measuring the generalization gap on unseen changes.

4. **Phase 3 — Genuine Proofline Pull Request Review Audit:**
   Integrated Proofline directly on our open Pull Request #1. Proofline provided 11 review comments, which I audited and deduplicated into 7 unique engineering findings. Proofline caught a genuine keyset pagination bug (timestamp ties dropping records) and valid credential masking improvements, while also flagging two instructive false positives: suggesting connection pooling for SQLite's single-writer WAL mode, and questioning transaction atomicity that Python's `with db:` context manager already guarantees.

5. **CI Root-Cause Diagnosis & Local Fix:**
   Diagnosed and reproduced a GitHub Actions CI failure where `actions/checkout` shallow history (`fetch-depth: 1`) omitted baseline commit `9b5ac64`, breaking Git isolation tests. Implemented Fix P1 (`fetch-depth: 0`) in `.github/workflows/check.yml` with clean local verification (remote push pending final authorization).

6. **Zero External PyPI Dependencies & 100% Test Pass Rate:**
   Built strictly on the Python Standard Library (`sqlite3` in WAL mode, `urllib`, `subprocess`, `unittest`). All 150 automated tests pass cleanly (148 passed, 2 skipped offline, 0 failures, 0 errors).

7. **AWS Deployment Verification:**
   Verified local CloudFormation packaging and executed local Lambda handler smoke test, obtaining confirmed receipt timestamp `101`, 1 delivered, 0 pending. (In full compliance with assignment transparency guidelines, live cloud deployment was marked NOT PERFORMED).

### Deliverable Links:
- **Pull Request #1:** https://github.com/UsmanSardar123/proofline-review-benchmark/pull/1 *(Proofline team granted access)*
- **Repository:** https://github.com/UsmanSardar123/proofline-review-benchmark
- **Phase 2 Benchmark Report:** https://github.com/UsmanSardar123/proofline-review-benchmark/blob/feature/benchmark-engine/reports/phase_2_cloudflare_benchmark_report.md
- **Phase 3 Proofline Audit Matrix:** https://github.com/UsmanSardar123/proofline-review-benchmark/blob/feature/benchmark-engine/docs/proofline-review-audit.md
- **Two-Minute Walkthrough Video Script:** https://github.com/UsmanSardar123/proofline-review-benchmark/blob/feature/benchmark-engine/reports/video_walkthrough_script.md
- **Two-Minute Walkthrough Video:** [CANDIDATE_VIDEO_LINK_PLACEHOLDER]

### Availability:
- **Location:** Rawalpindi, Pakistan (Equipped for remote work across global timezones)
- **Availability:** Available for a full-time 3–6 month software engineering internship immediately

Thank you for your time, review, and consideration. I look forward to discussing the architecture, experimental findings, and engineering trade-offs with your team.

Warm regards,

**Usman Ayaz**  
GitHub: https://github.com/UsmanSardar123  
Email: usmansardar037@gmail.com  
