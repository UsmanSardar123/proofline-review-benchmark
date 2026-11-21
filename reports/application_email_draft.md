# Proofline Internship Application Email Draft

**To:** `intern-applicants@proofline.sh`  
**Subject:** Application: Software Engineering Intern — Usman Sardar  

---

Dear Proofline Hiring Team,

I am writing to submit my completed take-home assignment for the Software Engineering Intern position at Proofline.

I have built a comprehensive, reproducible AI pull request review benchmarking system designed to evaluate, compare, and calibrate automated code reviewers across eight realistic review cases on the report service application.

### Key Highlights of My Submission:
1. **Multi-Provider & Zero-Cost Architecture:** Designed a unified reviewer interface supporting direct API adapters (OpenAI, Anthropic, CodeRabbit, Proofline) alongside a zero-cost manual ingestion pipeline (`benchmark prompt` and `benchmark ingest`) that enables genuine evaluations of ChatGPT (GPT-4o) and Claude (Claude 3.5 Sonnet) at $0 cost.
2. **Fair Experiment Protocol & Isolation:** Strictly isolated reviewer inputs to ensure zero ground-truth leakage, divided cases into calibration (01, 02, 03, 07) and held-out (04, 05, 06, 08) partitions, and fingerprinted calibration profiles with SHA-256 hashes.
3. **Deployment Snapshot Ablation:** Implemented dual context conditions (`code-only` vs `code-and-snapshot`) on Cases 04–06 to measure the exact impact of operational infrastructure context on reviewer precision and recall.
4. **Resumability & Audit Traceability:** Implemented crash recovery and a detailed inspection command (`benchmark show-attempt --full`) that traces any calculated score directly back to the original raw review, extracted findings, line matches, and lifecycle audit events.
5. **Quality & Systems Engineering:** Maintained 100% test pass rate across 104 automated tests, verified SQLite WAL migrations, packaged CloudFormation templates for inline Lambda deployment, and verified local smoke checks.

### Links & Submission Artifacts:
- **Pull Request:** https://github.com/UsmanSardar123/proofline-review-benchmark/pull/1 *(Read access granted to Proofline team)*
- **Repository:** https://github.com/UsmanSardar123/proofline-review-benchmark
- **Two-Minute Walkthrough Video:** [VIDEO_LINK_PLACEHOLDER]

### Availability & Location:
- **Location:** Rawalpindi, Pakistan (Fully equipped for remote work across global timezones)
- **Availability:** Available for a full-time 3–6 month software engineering internship immediately

Thank you for your time, review, and consideration. I look forward to discussing the architecture, findings, and engineering trade-offs with your team.

Warm regards,

**Usman Sardar**  
Email: [YOUR_EMAIL_HERE]  
GitHub: https://github.com/UsmanSardar123  
LinkedIn: [YOUR_LINKEDIN_HERE]  
