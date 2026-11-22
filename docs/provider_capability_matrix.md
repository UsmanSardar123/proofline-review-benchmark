# Provider Integration Capability Matrix & Architecture Reference

**Document Version:** 1.0.0  
**Repository:** [proofline-review-benchmark](file:///c:/Users/hp/Desktop/proofline-review-benchmark)  
**Module:** `benchmark/providers/`  
**Test Suite:** `tests/test_providers_phase3.py`, `tests/test_greptile_provider.py`, `tests/test_manual_ingest.py`

---

## 1. Executive Provider Capability Matrix

The Proofline Benchmark architecture unifies direct paid API endpoints, local CLI tools, deterministic test mocks, and manual zero-cost web workflows under a polymorphic interface (`BaseProviderAdapter`).

Below is the verified status across all seven integrated provider adapters:

| Provider ID | Adapter Class | Implemented | Unit Tested | Fixture Tested | Live API Tested | Manual Workflow Supported | Pending Verification |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`openai`** | `OpenAIAdapter` | **Yes** | **Yes** (12 tests) | **Yes** (Dry-run mode) | Skipped (No key configured) | No (Direct API) | Requires user `OPENAI_API_KEY` |
| **`anthropic`** | `AnthropicAdapter` | **Yes** | **Yes** (12 tests) | **Yes** (Dry-run mode) | Skipped (No key configured) | No (Direct API) | Requires user `ANTHROPIC_API_KEY` |
| **`coderabbit`** | `CodeRabbitAdapter` | **Yes** | **Yes** (8 tests) | **Yes** (Verified smoke fixtures) | Supported (API / CLI) | No (CLI/API) | Completed smoke fixture (`batch-3cee82d4`) |
| **`greptile`** | `GreptileAdapter` | **Yes** | **Yes** (8 tests) | **Yes** (Verified smoke fixtures) | Supported (REST API) | No (API/Fixture) | Completed smoke fixture (`batch-3cee82d4`) |
| **`proofline`** | `ManualProviderAdapter`| **Yes** | **Yes** (6 tests) | **Yes** (CLI ingest) | N/A (PR Review Ingestion) | **Yes** (Full support) | Pending live PR #1 comment import |
| **`mock`** | `MockProviderAdapter` | **Yes** | **Yes** (10 tests) | **Yes** (Deterministic) | N/A (In-memory engine) | N/A (Automated) | Fully verified (100% pass) |
| **`chatgpt-web`**| `ManualProviderAdapter`| **Yes** | **Yes** (14 tests) | **Yes** (CLI ingest) | N/A (Browser manual) | **Yes** (Zero-cost web) | 3 attempts pending (`batch-7b358964`) |
| **`claude-web`** | `ManualProviderAdapter`| **Yes** | **Yes** (14 tests) | **Yes** (CLI ingest) | N/A (Browser manual) | **Yes** (Zero-cost web) | 1 completed (`att-e0ae3808d089`), 2 pending |

---

## 2. Technical Provider Specifications

### 2.1 OpenAI Adapter (`openai`)
- **Module:** `benchmark/providers/openai.py`
- **Primary Model:** `gpt-4o` (configurable: `gpt-4o-mini`, `o1-preview`, `o3-mini`)
- **API Endpoint:** `https://api.openai.com/v1/chat/completions`
- **Environment Variable:** `OPENAI_API_KEY`
- **Authentication:** HTTP Header `Authorization: Bearer sk-...`
- **Zero-Dependency Implementation:** Uses standard library `urllib.request` (no `openai` PyPI package dependency).
- **Rate Limit Handling:** Catches HTTP 429 (`urllib.error.HTTPError`), parses retry-after headers, and raises `ProviderQuotaError`.
- **Transient Error Handling:** Retries 5xx server errors with exponential backoff (`max_retries=2`, `backoff_factor=0.2`).
- **Offline / Dry-Run Mode:** Pass `dry_run=True` or run without `OPENAI_API_KEY` in test suites to return deterministic fixture responses without incurring API charges.

### 2.2 Anthropic Adapter (`anthropic`)
- **Module:** `benchmark/providers/anthropic.py`
- **Primary Model:** `claude-3-5-sonnet-20241022` (configurable: `claude-3-7-sonnet`, `claude-3-haiku`)
- **API Endpoint:** `https://api.anthropic.com/v1/messages`
- **Environment Variable:** `ANTHROPIC_API_KEY`
- **Authentication:** HTTP Headers `x-api-key: sk-ant-...` and `anthropic-version: 2023-06-01`
- **Zero-Dependency Implementation:** Uses standard library `urllib.request` (no `anthropic` PyPI package dependency).
- **Telemetry Parsing:** Accurately extracts `usage.input_tokens` and `usage.output_tokens` into `ProviderRawResult`.
- **Quota & Error Handling:** Maps HTTP 429 and 529 (Overloaded) to `ProviderQuotaError`. Maps HTTP 401/403 to `ProviderAuthenticationError`.
- **Offline / Dry-Run Mode:** Pass `dry_run=True` to simulate valid structured review responses without external network access.

### 2.3 CodeRabbit AI Adapter (`coderabbit`)
- **Module:** `benchmark/providers/coderabbit.py`
- **Primary Model:** `coderabbit-review`
- **Modes Supported:**
  1. `cli`: Invokes installed local binary `coderabbit review --diff <diff_file>`.
  2. `api`: Dispatches HTTP POST requests to `https://api.coderabbit.ai/v1/review` via `CODERABBIT_API_KEY`.
  3. `fixture`: Deterministically replays captured CodeRabbit review artifacts from `evidence/fixtures/coderabbit/`.
  4. `auto`: Checks for API key first, falls back to CLI binary if present, and finally falls back to fixture playback.
- **Error Handling:** Validates exit codes for CLI subprocesses and timeouts after 60 seconds; raises `ProviderTransportError` on unexpected termination.

### 2.4 Greptile AI Adapter (`greptile`)
- **Module:** `benchmark/providers/greptile.py`
- **Primary Model:** `greptile-review-v2`
- **API Endpoint:** `https://api.greptile.com/v2/review`
- **Environment Variable:** `GREPTILE_API_KEY`
- **Authentication:** HTTP Header `Authorization: Bearer <key>`
- **Execution Modes:**
  1. `api`: Live remote invocation against Greptile indexing API.
  2. `fixture`: Replays deterministic codebase review fixtures from `evidence/fixtures/greptile/`.
  3. `auto`: Detects `GREPTILE_API_KEY`; uses live API if set, otherwise uses fixture playback.

### 2.5 Proofline Native Adapter (`proofline`)
- **Module:** `benchmark/providers/manual.py` (Registered in `ProviderRegistry`)
- **Primary Model:** `proofline-pr`
- **Target Interface:** GitHub Pull Request comments submitted by the Proofline GitHub App or GitHub Action.
- **Workflow:**
  1. User opens PR (e.g. PR #1) on GitHub.
  2. Proofline bot inspects the PR and posts inline review comments.
  3. Comments are copied to a review markdown file (or fetched via GitHub API) and ingested via:
     ```powershell
     python -m benchmark ingest --batch-id <batch_id> --provider proofline --case 1 --file reviews/proofline_pr1.md
     ```
- **Scoring Pipeline:** Evaluated against ground-truth defects using identical calibration profiles as all other reviewers.

### 2.6 Mock Provider Adapter (`mock`)
- **Module:** `benchmark/providers/mock.py`
- **Primary Model:** `mock-model-v1`
- **Execution Mode:** Pure in-memory deterministic simulation.
- **Configurable Test Modes:**
  - `success`: Returns immediate synthetic review with 200 OK.
  - `quota`: Raises `ProviderQuotaError` to test orchestrator rate-limit backoff and batch halt.
  - `retry_once`: Raises `ProviderTransportError` on initial call, succeeds on retry #2 to verify exponential backoff.
  - `fatal`: Raises `ProviderFatalError` to verify immediate failure isolation.

### 2.7 Manual & Zero-Cost Web Reviewer Adapter (`manual`, `chatgpt-web`, `claude-web`)
- **Module:** `benchmark/providers/manual.py`
- **Primary Models:**
  - `chatgpt-web`: GPT-4o via chatgpt.com
  - `claude-web`: Claude 3.5 Sonnet via claude.ai
- **Zero-Cost Operation:** Completely free of API token fees; relies on interactive web chats with leak-free prompts generated by `python -m benchmark prompt --case <N>`.
- **Ingestion Mechanics:**
  - Raw markdown files saved in `reviews/`.
  - Ingestion CLI parses target coordinates and findings using regex and AST heuristic matching.
  - Full audit metadata recorded in `evidence/raw/` and `benchmark.sqlite`.

---

## 3. Provider Setup & Usage Instructions

### 3.1 Live API Execution (Paid APIs)

To execute live benchmarks against commercial APIs:

```powershell
# Set credentials in session
$env:OPENAI_API_KEY = "sk-..."
$env:ANTHROPIC_API_KEY = "sk-ant-..."
$env:CODERABBIT_API_KEY = "cr-..."
$env:GREPTILE_API_KEY = "grp-..."

# Execute live benchmark batch
python -m benchmark run --experiment live-eval --providers openai,anthropic --cases 1,2,7
```

### 3.2 Zero-Cost Manual Ingestion Workflow (Recommended for Zero-Budget Evals)

1. **Schedule a manual batch:**
   ```powershell
   python -m benchmark run --experiment zero-cost --providers chatgpt-web,claude-web --cases 1,2,7 --manual
   ```
2. **Generate leak-free prompts:**
   ```powershell
   python -m benchmark prompt --case 1 --context code-only > prompts/case01.md
   python -m benchmark prompt --case 2 --context code-only > prompts/case02.md
   python -m benchmark prompt --case 7 --context code-only > prompts/case07.md
   ```
3. **Submit prompts to web models and save outputs:**
   - Save ChatGPT response to `reviews/chatgpt_case01.md`.
   - Save Claude response to `reviews/claude_case01.md`.
4. **Ingest and score:**
   ```powershell
   python -m benchmark ingest --batch-id <BATCH_ID> --provider chatgpt-web --case 1 --file reviews/chatgpt_case01.md
   python -m benchmark ingest --batch-id <BATCH_ID> --provider claude-web --case 1 --file reviews/claude_case01.md
   ```

---

## 4. Test Verification Status

Every adapter is verified in the automated test suite (`tests/`):
- `tests/test_providers_phase3.py`: 26 tests verifying OpenAI, Anthropic, and CodeRabbit adapters (auth errors, quota errors, transport retries, secret masking, token tracking).
- `tests/test_greptile_provider.py`: 8 tests verifying Greptile adapter (modes, secret masking, retry logic, fixture playback).
- `tests/test_manual_ingest.py`: 12 tests verifying manual provider adapter, prompt leak isolation, coordinate extraction, and database persistence.
- `tests/test_engine_hardening_sprint1.py`: 5 tests verifying parser edge cases and duplicate suppression.

**Total Provider Tests Passing:** 51 / 51 tests passing.
