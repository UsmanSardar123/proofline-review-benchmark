# Proofline AI Review Benchmark (batch-3cee82d4)

**Batch ID:** `batch-3cee82d4`

## 1. Denominator & Run Breadth

### Evaluation Breadth & Denominator Breakdown (Batch: batch-3cee82d4)

| Provider | Planned | Completed | Quota Halted | Failed | Pending | Completion Rate |
| --- | --- | --- | --- | --- | --- | --- |
| coderabbit | 2 | 2 | 0 | 0 | 0 | 100.0% |
| greptile | 2 | 2 | 0 | 0 | 0 | 100.0% |
| **Total** | **4** | **4** | **0** | **0** | **0** | **100.0%** |

## 2. Provider vs Case Comparison Matrix

### Provider vs Case Benchmark Matrix (Batch: batch-3cee82d4)

| Provider | case-01@code | case-01@snap | P | R | F1 | Passed |
| --- | --- | --- | --- | --- | --- | --- |
| coderabbit | ✗ FN (0.00) [FIXTURE] | ✗ FN (0.00) [FIXTURE] | 0.00 | 0.00 | 0.00 | 0 |
| greptile | ✗ FN (0.00) [FIXTURE] | ✗ FN (0.00) [FIXTURE] | 0.00 | 0.00 | 0.00 | 0 |

*Legend: `✓ TP` = True Positive, `✓ CL` = Clean Pass on benign PR, `✗ FP` = False Positive, `✗ FN` = Missed Defect, `✗ MX` = Mixed (TP and FP), `🔍` = Cited Deployment Evidence, `[FIXTURE]`/`[DRY_RUN]`/`[MOCK]` = synthetic output, NOT a genuine external review. Columns suffixed `@code`/`@snap` separate CODE_ONLY and CODE_AND_SNAPSHOT attempts.*

> **Warning:** synthetic (fixture/dry-run/mock) results are included for: `coderabbit` (2), `greptile` (2). Do not cite these as genuine reviewer performance.

## 3. Deployment Context Ablation

### Context & Deployment Snapshot Ablation Study (Batch: batch-3cee82d4)

| Provider | Case | Code-Only F1 | Code+Snap F1 | F1 Delta | Evidence Grounded? |
| --- | --- | --- | --- | --- | --- |

## 4. Calibration vs Held-Out Generalization

### Calibration vs Held-Out Generalization (Batch: batch-3cee82d4)

- **Calibration Cases**: case-01, case-02, case-03, case-07
- **Held-Out Test Cases**: case-04, case-05, case-06, case-08

| Provider | Cal Cases | Held Cases | Cal F1 | Held F1 | Delta (Held - Cal) | Missed Cases | Overfit Alert |
| --- | --- | --- | --- | --- | --- | --- | --- |
| coderabbit | 2 | 0 | 0.00 | 0.00 | 0.00 | case-01 | N/A (insufficient data) |
| greptile | 2 | 0 | 0.00 | 0.00 | 0.00 | case-01 | N/A (insufficient data) |
