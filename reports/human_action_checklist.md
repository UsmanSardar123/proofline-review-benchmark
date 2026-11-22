# Human Action Checklist — Candidate Responsibilities

**Candidate:** Usman Ayaz  
**Last Updated:** November 22, 2026  
**Project:** `proofline-review-benchmark`

This checklist tracks only the manual actions reserved exclusively for the candidate. The autonomous agent will not attempt to automate, simulate, or fabricate any of these items.

---

## 1. Benchmark Review Collection (Zero-Cost Web Interface)

- [ ] **ChatGPT (GPT-4o) Case 01:** Copy [prompts/case01.md](file:///c:/Users/hp/Desktop/proofline-review-benchmark/prompts/case01.md) into [chatgpt.com](https://chatgpt.com) and save genuine response into `reviews/chatgpt_case01.md`.
- [ ] **ChatGPT (GPT-4o) Case 02:** Copy [prompts/case02.md](file:///c:/Users/hp/Desktop/proofline-review-benchmark/prompts/case02.md) into ChatGPT and save response into `reviews/chatgpt_case02.md`.
- [ ] **Claude (Claude 3.5 Sonnet) Case 02:** Copy [prompts/case02.md](file:///c:/Users/hp/Desktop/proofline-review-benchmark/prompts/case02.md) into [claude.ai](https://claude.ai) and save response into `reviews/claude_case02.md`.
- [ ] **ChatGPT (GPT-4o) Case 07:** Copy [prompts/case07.md](file:///c:/Users/hp/Desktop/proofline-review-benchmark/prompts/case07.md) into ChatGPT and save response into `reviews/chatgpt_case07.md`.
- [ ] **Claude (Claude 3.5 Sonnet) Case 07:** Copy [prompts/case07.md](file:///c:/Users/hp/Desktop/proofline-review-benchmark/prompts/case07.md) into Claude and save response into `reviews/claude_case07.md`.
- [ ] **Full 8-Case Extension (Cases 03, 04, 05, 06, 08):** Copy prompts from `prompts/` and save responses into `reviews/`.
- [ ] **Deployment Snapshot Ablation (Cases 04, 05, 06):** Copy snapshot prompts (`case04_snapshot.md`, `case05_snapshot.md`, `case06_snapshot.md`) into ChatGPT and Claude; save into `reviews/`.

*Note: Once review files are saved, run `powershell -ExecutionPolicy Bypass -File .\ingest_batch.ps1` to ingest and score automatically.*

---

## 2. Proofline GitHub App Integration

- [ ] **Install Proofline App:** Visit [GitHub Marketplace: Proofline](https://github.com/marketplace/proofline) or [proofline.sh](https://proofline.sh) and install on `UsmanSardar123/proofline-review-benchmark`.
- [ ] **Trigger Review:** Verify Proofline runs on open PR [#1](https://github.com/UsmanSardar123/proofline-review-benchmark/pull/1) (or trigger via PR comment `@proofline review`).
- [ ] **Save Proofline Comments:** Paste review comments into `reviews/proofline_pr_review.md`.

---

## 3. Candidate Personal Submissions

- [ ] **Video Walkthrough:** Record personal 2-minute narrated walkthrough screencast demonstrating the platform.
- [ ] **Application Email:** Review draft in [reports/application_email_draft.md](file:///c:/Users/hp/Desktop/proofline-review-benchmark/reports/application_email_draft.md) and send to `intern-applicants@proofline.sh` from candidate's personal email.

---

## 4. Excluded / Skipped Items

- [x] **Live AWS Deployment:** Skipped per candidate instruction (no AWS account; local packaging and smoke testing preserved as verified evidence).
