# 10 — Student Learning Guide

Welcome! This guide explains your **Proofline AI Pull Request Review Benchmark** in plain, practical language so you can understand every piece before writing or changing another line of code.

---

## 1. The Big Picture (In Plain English)

Imagine you want to know: **"Is Claude or ChatGPT better at reviewing Pull Requests?"**
If you just ask each one to review one random file, you can't measure it fairly. Instead, you built a **scientific test lab** for AI code reviewers:

1. **The Subject Under Test (Target App):** A tiny 86-line Python app (`reports.py` + `console.py`) that schedules reports, exports CSVs, and delivers queued jobs using SQLite.
2. **The 8 Exams (`cases/01`–`08`):** 8 small Git patches against `reports.py`.
   - **Cases 01–03:** Pure code bugs (pagination tie-breaker, unescaped CSV, dropped batch remainder).
   - **Cases 04–06:** Operational/deployment bugs that **only** make sense if the AI sees a production "deployment snapshot" (`evidence.md` — e.g., active worker versions or queue names).
   - **Cases 07–08:** Clean, harmless PRs (to test if the AI cries wolf with false alarms!).
3. **The Examiner (`benchmark/`):** Your Python CLI that hands the exam to AI reviewers (without leaking the answer key), collects their written answers, grades them automatically against ground truth, and prints report cards.

---

## 2. How the Evaluation System Works (Simple Language + Formulas)

When an AI reviewer reads a PR and writes comments, your system extracts each comment as a **Finding** (`ReviewFinding`) and grades it in `benchmark/scoring/`:

### Key Metrics
- **True Positive (TP):** The AI found the **real bug** that we know is in the PR. *(Good!)*
- **False Positive (FP):** The AI reported a **serious bug (`high`/`critical`/`error`/`blocker`) that isn't actually a bug** (or on a clean PR 07/08). *(Bad — noisy false alarm!)*
- **False Negative (FN):** The AI **missed** the real bug in a buggy PR (01–06). *(Bad — bug slipped to production!)*
- **Valid Unexpected Finding (VUF):** A non-blocking suggestion (`warning`/`info`) that isn't the main ground-truth bug, e.g., "Consider adding unit tests." *(Neutral — doesn't hurt Precision!)*
- **Duplicate:** The AI mentioned the **same** ground-truth bug 2 or 3 times in different paragraphs. Your `ScoringService` counts the **first** match as `TP = 1` and marks the rest `DUPLICATE` so a chatty AI can't artificially inflate its score!

### Formulas (from `benchmark/scoring/metrics.py` — `ScoringCalculator.calculate_metrics`)
- **For Buggy PRs (Cases 01–06):**
  - $\text{Precision} = \frac{TP}{TP + FP}$ (or `0.0` if $TP + FP = 0$) — *"When the AI raises an alarm, how often is it right?"*
  - $\text{Recall} = \frac{TP}{TP + FN}$ (or `0.0` if $TP + FN = 0$) — *"Out of all real bugs, how many did the AI catch?"*
  - $F_1 = \frac{2 \times \text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$ (or `0.0` if $\text{Precision} + \text{Recall} = 0$) — *"Balanced score between Precision and Recall."*
- **For Benign/Clean PRs (Cases 07–08):**
  - If `FP == 0` (no false alarms): `Precision = 1.0, Recall = 1.0, F1 = 1.0, passed_cleanly = True`.
  - If `FP > 0` (false alarm): `Precision = 0.0, Recall = 0.0, F1 = 0.0, passed_cleanly = False`.
- **Calibration (`benchmark/scoring/calibration.py`):**
  - A `CalibrationProfile` (like `standard-v1`) sets the grading strictness: how close the AI's line number must be (`line_tolerance = 5`), how many keywords must match (`min_keyword_matches = 1`), and the minimum confidence (`match_threshold = 0.45`).
  - How matching confidence works in `FindingMatcher.match()`:
    $$\text{confidence} = (0.4 \times \text{location\_score}) + (0.6 \times \text{semantic\_score})$$
- **Held-Out Evaluation (`benchmark/scoring/heldout.py`):**
  - Cases `01, 02, 03, 07` are the **Calibration set** (used to tune/check your grader).
  - Cases `04, 05, 06, 08` are the **Held-Out set** (kept separate to test if a reviewer generalizes to unseen operational bugs).
  - `Generalization Delta = heldout_f1 - calibration_f1`. If `calibration_f1 - heldout_f1 > 0.25`, it flags `is_overfitted = True`.

### Practical Example (Real Data from `batch-7b358964`, `claude-web`, Case 01)
1. **Input:** `reviews/claude_case01.md` targets `reports.py` lines ~44–49 and describes `"Rows skipped at page boundaries... scheduled_at < ? ..."` plus 5 other sections.
2. **Extraction (`FindingExtractor`):** Extracts 6 `ReviewFinding` rows from the Markdown headings/bullets.
3. **Matching (`FindingMatcher` vs `gt-case-01`):** Ground truth is `reports.py:42-50` with keywords `["cursor", "scheduled_at", "tie", ...]`. Finding #1 matches line 44 (`loc_score = 1.0`) and keywords (`sem_score > 0`), giving `confidence >= 0.45` → **TRUE_POSITIVE (`TP = 1`)**.
4. **Deduplication:** Findings #2–#6 also match `gt-case-01`, so `ScoringService` marks all 5 as **DUPLICATE** (not 6 TPs!).
5. **Final Score:** `TP=1, FP=0, FN=0, VUF=0` → `Precision = 1.0`, `Recall = 1.0`, `F1 = 1.0`, `passed_cleanly = True`.

---

## 3. Component-by-Component Student Guide

1. **Domain & Database (`benchmark/domain/`, `benchmark/db/`)**
   - *What it does:* Defines Python dataclasses (`ReviewAttempt`, `ReviewFinding`, `AttemptScore`) and saves them to `benchmark.sqlite`.
   - *Why we need it:* So every experiment is auditable and crash-safe (if your internet drops mid-run, `benchmark resume` picks up where it left off).
2. **Cases & Context (`benchmark/cases/`)**
   - *What it does:* Loads `cases/01..08`, checks patches with `git apply --check`, and builds clean prompts while blocking answer-key leaks (`ContextSafetyError`).
3. **Providers (`benchmark/providers/`)**
   - *What it does:* A unified "plug" (`BaseProviderAdapter`) so the engine can talk to OpenAI, Anthropic, CodeRabbit, Greptile, or manual web pastes (`chatgpt-web`, `claude-web`, `proofline`) the exact same way.
4. **Orchestrator (`benchmark/orchestrator/engine.py`)**
   - *What it does:* The "manager" that schedules a batch, runs or ingests each attempt, retries network glitches, calls the collector/extractor/scorer, and logs every step to `run_events`.
5. **Extractor, Scorer & Reporter (`benchmark/eval/`, `benchmark/scoring/`, `benchmark/reporting/`)**
   - *What it does:* Turns raw Markdown reviews into structured findings, grades them against `STANDARD_GROUND_TRUTHS`, and exports Markdown/CSV/JSON tables.
6. **AWS Fixture (`aws/`)**
   - *What it does:* Packages the *sample app* (`reports.py` + `migrations/`) into a tiny AWS Lambda function to prove cloud deployment & CI/CD readiness.

---

## 4. Recommended File-Reading Order

Read these files in order (about 15–20 minutes each) to master the whole codebase without getting overwhelmed:
1. `reports.py` + `migrations/001_initial.sql` (understand the tiny app being reviewed).
2. `cases/01/title.txt`, `body.md`, `change.patch` and `cases/04/evidence.md` (see what a case & snapshot look like).
3. `benchmark/domain/enums.py` & `benchmark/domain/models.py` (learn the core vocabulary).
4. `benchmark/migrations/001_initial_benchmark.sql` (see how the 11 tables relate).
5. `benchmark/cases/context.py` (see how prompts are built and leak-checked).
6. `benchmark/providers/base.py` & `benchmark/providers/manual.py` (see how adapters work).
7. `benchmark/orchestrator/engine.py` (trace `schedule_batch`, `execute_attempt`, and `ingest_review`).
8. `benchmark/eval/extractor.py` → `benchmark/scoring/matcher.py` → `benchmark/scoring/metrics.py` → `benchmark/scoring/service.py` (follow the grading pipeline).
9. `benchmark/cli/main.py` & `benchmark/cli/commands.py` (see how everything is wired to CLI commands).
10. `aws/handler.py` & `aws/deploy.py` (understand the AWS Lambda fixture).
