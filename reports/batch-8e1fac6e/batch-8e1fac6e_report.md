# Proofline AI Review Benchmark (batch-8e1fac6e)

**Batch ID:** `batch-8e1fac6e`

## 1. Denominator & Run Breadth

### Evaluation Breadth & Denominator Breakdown (Batch: batch-8e1fac6e)

| Provider | Planned | Completed | Quota Halted | Failed | Pending | Completion Rate |
| --- | --- | --- | --- | --- | --- | --- |
| chatgpt-web | 5 | 0 | 0 | 0 | 5 | 0.0% |
| claude-web | 5 | 0 | 0 | 0 | 5 | 0.0% |
| **Total** | **10** | **0** | **0** | **0** | **10** | **0.0%** |

## 2. Provider vs Case Comparison Matrix

### Provider vs Case Benchmark Matrix (Batch: batch-8e1fac6e)

| Provider | case-03 | case-04 | case-05 | case-06 | case-08 | P | R | F1 | Passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| chatgpt-web | `PENDING` | `PENDING` | `PENDING` | `PENDING` | `PENDING` | 0.00 | 0.00 | 0.00 | 0 |
| claude-web | `PENDING` | `PENDING` | `PENDING` | `PENDING` | `PENDING` | 0.00 | 0.00 | 0.00 | 0 |

*Legend: `✓ TP` = True Positive, `✓ CL` = Clean Pass on benign PR, `✗ FP` = False Positive, `✗ FN` = Missed Defect, `✗ MX` = Mixed (TP and FP), `🔍` = Cited Deployment Evidence, `[FIXTURE]`/`[DRY_RUN]`/`[MOCK]` = synthetic output, NOT a genuine external review. Columns suffixed `@code`/`@snap` separate CODE_ONLY and CODE_AND_SNAPSHOT attempts.*

## 3. Deployment Context Ablation

### Context & Deployment Snapshot Ablation Study (Batch: batch-8e1fac6e)

| Provider | Case | Code-Only F1 | Code+Snap F1 | F1 Delta | Evidence Grounded? |
| --- | --- | --- | --- | --- | --- |
| chatgpt-web | case-04 | 0.00 | 0.00 | 0.00 | No |
| chatgpt-web | case-05 | 0.00 | 0.00 | 0.00 | No |
| chatgpt-web | case-06 | 0.00 | 0.00 | 0.00 | No |
| claude-web | case-04 | 0.00 | 0.00 | 0.00 | No |
| claude-web | case-05 | 0.00 | 0.00 | 0.00 | No |
| claude-web | case-06 | 0.00 | 0.00 | 0.00 | No |

## 4. Calibration vs Held-Out Generalization

### Calibration vs Held-Out Generalization (Batch: batch-8e1fac6e)

- **Calibration Cases**: case-01, case-02, case-03, case-07
- **Held-Out Test Cases**: case-04, case-05, case-06, case-08

| Provider | Cal Cases | Held Cases | Cal F1 | Held F1 | Delta (Held - Cal) | Missed Cases | Overfit Alert |
| --- | --- | --- | --- | --- | --- | --- | --- |
| chatgpt-web | 0 | 0 | 0.00 | 0.00 | 0.00 | None | N/A (insufficient data) |
| claude-web | 0 | 0 | 0.00 | 0.00 | 0.00 | None | N/A (insufficient data) |
