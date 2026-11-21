# Proofline AI Review Benchmark (batch-7b358964)

**Batch ID:** `batch-7b358964`

## 1. Denominator & Run Breadth

### Evaluation Breadth & Denominator Breakdown (Batch: batch-7b358964)

| Provider | Planned | Completed | Quota Halted | Failed | Pending | Completion Rate |
| --- | --- | --- | --- | --- | --- | --- |
| chatgpt-web | 3 | 0 | 0 | 0 | 3 | 0.0% |
| claude-web | 3 | 1 | 0 | 0 | 2 | 33.3% |
| **Total** | **6** | **1** | **0** | **0** | **5** | **16.7%** |

## 2. Provider vs Case Comparison Matrix

### Provider vs Case Benchmark Matrix (Batch: batch-7b358964)

| Provider | case-01 | case-02 | case-07 | P | R | F1 | Passed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| chatgpt-web | `PENDING` | `PENDING` | `PENDING` | 0.00 | 0.00 | 0.00 | 0 |
| claude-web | ✓ TR (1.00) | `PENDING` | `PENDING` | 1.00 | 1.00 | 1.00 | 1 |

*Legend: `✓ TP` = True Positive, `✓ CL` = Clean Pass on benign PR, `✗ FP` = False Positive, `✗ FN` = Missed Defect, `🔍` = Cited Deployment Evidence.*

## 3. Deployment Context Ablation

### Context & Deployment Snapshot Ablation Study (Batch: batch-7b358964)

| Provider | Case | Code-Only F1 | Code+Snap F1 | F1 Delta | Evidence Grounded? |
| --- | --- | --- | --- | --- | --- |

## 4. Calibration vs Held-Out Generalization

### Calibration vs Held-Out Generalization (Batch: batch-7b358964)

- **Calibration Cases**: case-01, case-02, case-03, case-07
- **Held-Out Test Cases**: case-04, case-05, case-06, case-08

| Provider | Cal Cases | Held Cases | Cal F1 | Held F1 | Delta (Held - Cal) | Missed Cases | Overfit Alert |
| --- | --- | --- | --- | --- | --- | --- | --- |
| chatgpt-web | 0 | 0 | 0.00 | 0.00 | 0.00 | None | ✓ Generalizing |
| claude-web | 1 | 0 | 1.00 | 0.00 | -1.00 | None | ⚠️ Overfitting Risk |
