# Phase 2 Benchmark Automation Pipeline Guide

## Overview

The **Phase 2 Benchmark Automation Pipeline** provides an end-to-end, reproducible CLI command:

```powershell
python -m benchmark automate [OPTIONS]
```

It orchestrates the benchmark workflow while strictly adhering to safety and research integrity principles:
- **Zero Fabrication:** Never generates fake or simulated review text.
- **Zero Accidental Paid Calls:** Never invokes paid third-party AI APIs without explicit opt-in flags.
- **Prompt Anti-Leakage:** Generates reviewer prompts containing only case diffs, commit context, and instructions—never ground truth defect descriptions or scoring rubrics.
- **Robust Multi-Tier Matching:** Matches human-collected review files to experiment attempts using explicit metadata, not fragile filename heuristics.
- **Dual Evidence Preservation:** Computes SHA-256 hashes and saves raw responses both in SQLite and as raw markdown + metadata sidecars in `evidence/raw/<batch_id>/`.
- **Anti-Inflation Evaluation:** Extracts findings, matches against ground truth, suppresses duplicate/rephrased detections, and recalculates TP, FP, FN, precision, recall, and F1.
- **Continuous Reporting:** Regenerates Markdown, JSON, and CSV reports (`reports/<batch_id>/`) and updates the pending collection index (`collection/pending_prompts/README.md`).

---

## 1. CLI Usage & Flags

### Basic Invocations

Run the complete pipeline (synchronize prompts, scan & ingest new reviews, regenerate reports):
```powershell
python -m benchmark automate
```

### Command-Line Options

| Option | Default | Description |
| :--- | :--- | :--- |
| `--no-ingest` | `False` | Skip discovering and ingesting new review files; only sync prompts and reports. |
| `--no-prompts` | `False` | Skip generating prompt files; only scan/ingest reviews and update reports. |
| `--no-reports` | `False` | Skip batch report regeneration after ingestion. |
| `--prompts-dir PATH` | `collection/pending_prompts` | Directory where prompt files and index are generated. |
| `--reviews-dir PATH` | `reviews` | Directory scanned for incoming review Markdown files. |
| `--reports-dir PATH` | `reports` | Target directory for generated batch reports. |

---

## 2. Ingestion & Matching Architecture

When `python -m benchmark automate` runs, it scans the `--reviews-dir` (default: `reviews/`) for `.md` files and matches each file against pending attempts in `benchmark.sqlite` using a 3-tier matching strategy.

### Tier 1: Explicit Metadata Comment Header (Preferred & Recommended)
Generated prompt files in `collection/pending_prompts/` include a comment header at the top. When saving reviewer output, prepend or retain this block:

```html
<!--
  METADATA FOR AUTOMATED INGESTION:
  attempt_id: att-2c30ac581db0
  batch_id: batch-8e1fac6e
  provider_id: chatgpt-web
  case_id: case-03
  context_condition: CODE_ONLY
-->
```

- The pipeline inspects the file contents.
- If an `attempt_id` is present, it directly matches the attempt in SQLite.
- **Important:** The pipeline automatically strips this HTML comment before saving the raw response into evidence and SQLite, ensuring that evaluation and finding extraction only analyze authentic reviewer prose.

### Tier 2: Key-Value Attribute Block
If the attempt ID is omitted but case, provider, and context are supplied:

```text
Case: case-03
Provider: chatgpt-web
Context: CODE_ONLY
```

The pipeline queries SQLite for a pending attempt matching those exact attributes.

### Tier 3: Structured Filename Fallback
If the file contains no metadata header, the filename is parsed against canonical patterns:
- `case-03_code_only_chatgpt_response.md`
- `case-03_code_and_snapshot_claude_response.md`
- `case-03_chatgpt_response.md` (if context condition is unambiguous in pending attempts)

If any ambiguity exists (e.g., both `CODE_ONLY` and `CODE_AND_SNAPSHOT` attempts are pending for that case and provider), the pipeline **refuses to ingest** and logs an actionable warning asking for clarification.

---

## 3. Reviewer Workflow (Step-by-Step)

### Step 1: Check Pending Prompts
Run:
```powershell
python -m benchmark automate --no-ingest
```
This updates `collection/pending_prompts/README.md` listing all pending review tasks and generates self-contained prompt files.

### Step 2: Conduct the Review
1. Open the prompt file from `collection/pending_prompts/` (e.g. `case-03_code_only_chatgpt_att-2c30.md`).
2. Copy the prompt text (below the metadata header).
3. Paste it into the web interface of ChatGPT or Claude.
4. Copy the complete, unedited reviewer response.

### Step 3: Save the Review
Create a file in `reviews/` (e.g. `reviews/case-03_chatgpt_response.md`).
Include the metadata header from the prompt file at the top:

```markdown
<!--
  METADATA FOR AUTOMATED INGESTION:
  attempt_id: att-2c30ac581db0
  batch_id: batch-8e1fac6e
  provider_id: chatgpt-web
  case_id: case-03
  context_condition: CODE_ONLY
-->

## Pull Request Review
... [reviewer response text] ...
```

### Step 4: Run Automation
Execute:
```powershell
python -m benchmark automate
```

The pipeline will:
1. Detect `reviews/case-03_chatgpt_response.md`.
2. Match it to attempt `att-2c30ac581db0`.
3. Compute SHA-256 hash of the reviewer text.
4. Check for duplicate content (skipping if already ingested).
5. Ingest into SQLite and `evidence/raw/batch-8e1fac6e/att-2c30ac581db0.md` with `.meta.json`.
6. Extract findings, evaluate against ground truth, and calculate metrics.
7. Regenerate reports for `batch-8e1fac6e`.
8. Update `collection/pending_prompts/README.md`.

---

## 4. Duplicate & Overwrite Protection

- **Duplicate Content Suppression:** If a review file's SHA-256 content hash matches an already ingested response in the target attempt or batch, the pipeline marks it as `DUPLICATE` and skips re-ingestion.
- **Completed Attempt Protection:** Completed attempts will not be overwritten by `automate`. To force re-ingestion, use the manual CLI command:
  ```powershell
  python -m benchmark ingest --force --batch-id <batch_id> --attempt-id <attempt_id> --file <file>
  ```

---

## 5. Direct API Extensibility (Future Paid Integrations)

The pipeline is architected to seamlessly support automated live API calls to OpenAI (`gpt-4o`) and Anthropic (`claude-3-5-sonnet-20241022`) when authorized:

1. **Provider Adapters:** `OpenAIAdapter` (`benchmark/providers/openai.py`) and `AnthropicAdapter` (`benchmark/providers/anthropic.py`) implement the standard `ReviewerProvider` interface.
2. **Cost Controls:** Adapters enforce token ceilings (`max_tokens`) and budget tracking.
3. **Execution Mode Guard:** The existing `orchestrator.run_batch()` method accepts an `execution_mode` parameter. By default, it operates in offline/dry-run mode unless API keys are present and the user explicitly passes `--live-api`.
4. **Offline Isolation:** When API keys are not supplied in the environment (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`), adapters automatically fall back to dry-run or report missing credentials rather than crashing.
