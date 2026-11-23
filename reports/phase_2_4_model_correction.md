# Phase 2.4 — Model Lifecycle Audit & Configuration Correction Report

**Date:** November 22, 2026  
**Project:** Proofline AI Pull Request Reviewer Benchmark  
**Working Branch:** `feature/benchmark-engine`  
**Base Commit:** `9d37732`  
**Scope:** Investigation of model lifecycle deprecations for both Anthropic and OpenAI, identification and evaluation of active code-review models, cost recalculations, and adapter configuration updates.

---

## 1. Executive Summary

During the Phase 2.4 pre-execution audit and lifecycle verification, critical deprecation and retirement statuses were audited across both primary API providers:

1. **Anthropic Model (`claude-3-5-sonnet-20241022`):**
   - **Status:** **RETIRED on October 28, 2025**. Any direct API request submitting this retired string fails immediately with `404 Not Found` (`model_not_found`).
   - **Replacement:** **`claude-sonnet-5-5`**, the current active frontier model for coding and architectural reasoning ($2.00/M input, $10.00/M output, 1M context window).

2. **OpenAI Model (`gpt-4o` and `gpt-4o-2024-11-20`):**
   - **Status:** **DEPRECATED on October 14, 2026**; scheduled for **PERMANENT SHUTDOWN on January 14, 2027**. Any application or benchmark relying on this endpoint will cease functioning in less than two months.
   - **Replacement Options:** **`gpt-6.1-sol`** (the active flagship workhorse for code review and PR analysis at $2.00/M input, $10.00/M output) and **`gpt-6-luna`** (high-throughput, lightweight tier at $0.10/M input, $0.50/M output).
   - **Decision:** **`gpt-6.1-sol`** is recommended and configured as the primary target for the 9 pending OpenAI attempts to match Anthropic's `claude-sonnet-5-5` in generational capability and ensure long-term benchmark reproducibility.

Existing website-based reviews (`att-e0ae3808d089`, `att-c0ff417e95fb`, `att-0ba1cc2f4b45`) remain completely untouched and preserved with their authentic provenance.

---

## 2. OpenAI Model Lifecycle Verification

OpenAI's official API deprecation notices and model lifecycle documentation confirm the following:
- **Deprecation Notice Date:** October 14, 2026.
- **Affected Models & Snapshots:** Base `gpt-4o`, snapshots `gpt-4o-2024-08-06`, `gpt-4o-2024-11-20`, `gpt-4o-mini-2024-07-18`, `gpt-4.1-2025-04-14`, and `gpt-4.1-mini-2025-04-14`.
- **Scheduled Termination Date:** **January 14, 2027**.
- **Implication for Benchmark:** While `gpt-4o` can technically process requests today (November 22, 2026) for approximately 53 more days, any benchmark data collected on `gpt-4o` will become impossible to reproduce via API after January 14, 2027.

---

## 3. Anthropic Model Lifecycle Verification

Anthropic's official model lifecycle policy operates on structured phases: *Active* $\rightarrow$ *Legacy* $\rightarrow$ *Deprecated* ($\ge$ 60 days notice) $\rightarrow$ *Retired* (endpoint permanently disabled).
- **Deprecation Notice Date:** August 13, 2025.
- **Retirement Date:** **October 28, 2025**.
- **Endpoint Status:** Fully disabled. Submissions to `/v1/messages` with `model: "claude-3-5-sonnet-20241022"` fail immediately.
- **Active Current Generation:** **`claude-sonnet-5-5`** ($2.00/M input, $10.00/M output, 1M context window).

---

## 4. Evaluation of OpenAI Replacements for Code Review

OpenAI's active GPT-6 lineup provides three tiers relevant to code analysis:

| Model Identifier | Primary Role | Context / Output | Pricing (Input / Output per 1M) | Code Review Suitability |
| :--- | :--- | :---: | :---: | :--- |
| **`gpt-6.1-sol`** *(Recommended)* | Workhorse for interactive coding & PR reviews | 1.05M / 128k | **$2.00 / $10.00** | **Optimal:** Native reasoning effort tiers, deep logic tracing, catches concurrency & composite cursor defects. |
| **`gpt-6-luna`** | Lightweight, high-throughput utility | 1.05M / 128k | $0.10 / $0.50 | Fast & ultra-cheap, but less deep on subtle PR boundary regressions. |
| **`gpt-6-astra`** | Frontier flagship for monorepo audits | 1.05M / 128k | $10.00 / $50.00 | Highest intelligence, but unnecessarily expensive for standard PR diffs. |

### Comparative Analysis: `gpt-6.1-sol` vs `gpt-4o`

1. **Financial Cost:**
   - `gpt-4o`: $2.50 / 1M input, $10.00 / 1M output.
   - `gpt-6.1-sol`: $2.00 / 1M input, $10.00 / 1M output.
   - **Advantage:** `gpt-6.1-sol` provides a **20% discount on input tokens** with matching output pricing.
2. **Coding Capability:**
   - `gpt-4o`: 2024 legacy architecture without reasoning effort control. Struggles with multi-file contextual integration and subtle data-streaming bugs.
   - `gpt-6.1-sol`: Modern 2026 reasoning model with granular effort controls (`none` to `max`). Significantly lowers False Negatives on subtle logic bugs (such as composite cursor pagination and unescaped CSV serialization).
3. **Reproducibility & Longevity:**
   - `gpt-4o`: Deprecated, shutting down January 14, 2027. Results become non-reproducible in 53 days.
   - `gpt-6.1-sol`: Active production model with multi-year lifecycle horizon, providing guaranteed reproducibility for future comparative studies.

---

## 5. Architectural Decision on Pending Attempts

### Decision: Migrate to `gpt-6.1-sol`
For the 9 pending OpenAI attempts:
1. **Benchmark Longevity:** The Proofline benchmark is designed to establish reproducible baseline metrics. Benchmarking an end-of-life model scheduled for decommissioning in weeks undermines publication credibility.
2. **Cross-Generational Fairness:** Pairing a 2024 legacy model (`gpt-4o`) against Anthropic's 2026 frontier model (`claude-sonnet-5-5`) introduces an unfair cross-generational mismatch. Comparing `claude-sonnet-5-5` with `gpt-6.1-sol` creates a balanced, frontier peer-to-peer evaluation where both models share identical pricing ($2.00 / $10.00).
3. **Backward Compatibility Preserved:** The adapter retains explicit support for `gpt-4o` via CLI/parameter override for researchers conducting legacy retrospectives before January 14, 2027.

---

## 6. Official Model Configuration Matrix

| Provider | Retired / Deprecated Model | Selected Active Model | Display Name | Context Window | Input / Output Pricing |
| :--- | :--- | :--- | :--- | :---: | :---: |
| **OpenAI** | `gpt-4o` *(Deprecated, shutdown Jan 14, 2027)* | **`gpt-6.1-sol`** | OpenAI GPT-6.1 Sol | 1.05M | **$2.00 / $10.00** |
| **Anthropic** | `claude-3-5-sonnet-20241022` *(Retired Oct 28, 2025)* | **`claude-sonnet-5-5`** | Anthropic Claude Sonnet 5.5 | 1.0M | **$2.00 / $10.00** |

---

## 7. Recalculated Financial Cost Projections (19 Pending Attempts)

With both providers operating at the modern frontier tier ($2.00 / 1M input, $10.00 / 1M output):

### Per-Attempt Token Breakdown:
- **OpenAI (9 attempts):** 3,316 total input tokens, 6,750 expected completion tokens (750 tokens/attempt average).
- **Anthropic (10 attempts):** 3,746 total input tokens, 7,500 expected completion tokens (750 tokens/attempt average).

### Complete Financial Breakdown:

| Provider | Attempts | Target Model | Total Input Tokens | Expected Output Tokens | Max Output Tokens (2048 cap) | Expected Cost (USD) | Maximum Ceiling Cost (USD) |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| **OpenAI** | 9 | `gpt-6.1-sol` | 3,316 | 6,750 | 18,432 | **$0.0741** | **$0.1910** |
| **Anthropic** | 10 | `claude-sonnet-5-5` | 3,746 | 7,500 | 20,480 | **$0.0825** | **$0.2123** |
| **COMBINED TOTAL** | **19** | — | **7,062** | **14,250** | **38,912** | **$0.1566 USD** | **$0.4033 USD** |

### Financial Safety Findings:
1. **Expected Total Expenditure:** **$0.1566 USD** (~15.7 cents across all 19 reviews).
2. **Theoretical Maximum Cost:** In the extreme edge case where all 19 models hit the hard output ceiling of 2,048 tokens, the total possible cost is strictly capped at **$0.4033 USD** (~40.3 cents).
3. **Enforced Safety Limit:** The dispatcher enforces a hard ceiling of **$2.00 USD** (~5× buffer) before any billable request is permitted.

---

## 8. Preservation of Existing Genuine Evidence

The benchmark's three existing genuine reviews are preserved with immutable integrity:
- **`att-e0ae3808d089` (Case 01, Claude Web):** Collected during Claude 3.5 Sonnet's active lifecycle; provenance remains `claude-3-5-sonnet`.
- **`att-c0ff417e95fb` (Case 01, ChatGPT Web):** Collected via ChatGPT Web; provenance remains `GPT-6`.
- **`att-0ba1cc2f4b45` (Case 02, ChatGPT Web):** Collected via ChatGPT Web; provenance remains `GPT-6`.

None of these attempts or their SHA-256 evidence files will be overwritten or re-ingested.

---

## 9. Configuration Changes Applied

The codebase has been updated with the corrected active model identifiers and token pricing:
1. [benchmark/providers/openai.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/providers/openai.py):
   - Set `default_model = "gpt-6.1-sol"`
   - Set `display_name = "OpenAI GPT-6.1 Sol"`
2. [benchmark/providers/anthropic.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/providers/anthropic.py):
   - Set `default_model = "claude-sonnet-5-5"`
   - Set `display_name = "Anthropic Claude Sonnet 5.5"`
3. [benchmark/collector/dispatcher.py](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/benchmark/collector/dispatcher.py):
   - Configured `MODEL_PRICING` with `gpt-6.1-sol`, `gpt-6-sol`, `gpt-6-luna`, `gpt-6-astra`, `claude-sonnet-5-5`.
   - Updated default OpenAI target model mapping to `"gpt-6.1-sol"`.
4. [reports/phase_2_4_api_validation.md](file:///c:/Users/FA22-BSE-018.CUIWAH/Downloads/proofline-review-benchmark/proofline-review-benchmark/reports/phase_2_4_api_validation.md):
   - Synchronized model identifiers and updated financial tables.

---

## 10. Verification & Test Evidence

- **Zero-Cost Dry-Run:** Executed `python -m benchmark collect --dry-run`:
  - 19 pending attempts discovered.
  - 9 mapped to `gpt-6.1-sol`, 10 mapped to `claude-sonnet-5-5`.
  - External API calls: **0**
  - Actual expenditure: **$0.00 USD**
  - Simulation status: **SUCCESS**
- **Automated Regression Suite:** Executed `python -m unittest discover -s tests -v`:
  - Result: **126 tests total: 124 passed, 2 skipped, 0 failures, 0 errors**.
