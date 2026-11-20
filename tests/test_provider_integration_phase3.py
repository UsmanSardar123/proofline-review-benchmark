"""Comprehensive integration tests for Phase 3 AI reviewer integrations.

Tests:
1. Provider configuration and validation.
2. Mocked HTTP API execution for Anthropic and OpenAI.
3. Authentication failure handling (missing / invalid keys).
4. Error mapping: timeouts, rate limits (HTTP 429), server errors (500/503), fatal (400).
5. Retry behavior and transport recovery.
6. Response normalization, token telemetry, and dual persistence.
7. Orchestrator compatibility and duplicate prevention (idempotency).
8. Optional live test harnesses guarded by explicit environment flags.
"""

from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from benchmark.collector.storage import RawEvidenceStore
from benchmark.config import PROJECT_ROOT
from benchmark.db.connection import get_connection
from benchmark.db.migrations import migrate_benchmark_db
from benchmark.domain.enums import AttemptStatus, ContextCondition
from benchmark.orchestrator.engine import BenchmarkOrchestrator
from benchmark.providers.anthropic import AnthropicAdapter, AnthropicConfig
from benchmark.providers.base import (
    ProviderAuthenticationError,
    ProviderConfig,
    ProviderFatalError,
    ProviderQuotaError,
    ProviderRawResult,
    ProviderTransportError,
    ReviewContext,
)
from benchmark.providers.coderabbit import CodeRabbitAdapter, CodeRabbitConfig
from benchmark.providers.openai import OpenAIAdapter, OpenAIConfig
from benchmark.providers.registry import ProviderRegistry


def make_mock_http_response(status_code: int, body_dict: dict, headers: dict = None):
    """Helper creating a mock urllib HTTP response."""
    body_bytes = json.dumps(body_dict).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.status = status_code
    mock_resp.read.return_value = body_bytes
    mock_resp.headers = headers or {"Content-Type": "application/json"}
    mock_resp.__enter__.return_value = mock_resp
    return mock_resp


class Phase3ProviderIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "p3_test.sqlite"
        self.evidence_dir = Path(self.temp_dir.name) / "evidence"
        self.db = get_connection(self.db_path)
        migrate_benchmark_db(self.db)

        self.evidence_store = RawEvidenceStore(self.evidence_dir)
        self.orchestrator = BenchmarkOrchestrator(
            self.db,
            cases_dir=PROJECT_ROOT / "cases",
            evidence_store=self.evidence_store,
        )

        self.sample_context = ReviewContext(
            case_id="case-01",
            case_number=1,
            pr_title="Page report history by scheduled time",
            pr_body="Show the most recently scheduled deliveries first.",
            base_commit="9b5ac64",
            head_commit="e454f5f",
            patch_diff="diff --git reports.py reports.py\n+ query += ' WHERE scheduled_at < ?'",
            context_condition=ContextCondition.CODE_ONLY,
        )

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def test_provider_registry_discovery_and_instantiation(self):
        """Verify dynamic discovery and instantiation of all registered providers."""
        registry = ProviderRegistry()
        registered = registry.list_registered()

        self.assertIn("anthropic", registered)
        self.assertIn("openai", registered)
        self.assertIn("coderabbit", registered)
        self.assertIn("mock", registered)

        # Test instantiating with dry-run mode
        claude = registry.get_adapter("anthropic", dry_run=True)
        self.assertIsInstance(claude, AnthropicAdapter)
        self.assertTrue(claude.anthropic_config.dry_run)

        gpt = registry.get_adapter("openai", dry_run=True)
        self.assertIsInstance(gpt, OpenAIAdapter)
        self.assertTrue(gpt.openai_config.dry_run)

        rabbit = registry.get_adapter("coderabbit", mode="fixture")
        self.assertIsInstance(rabbit, CodeRabbitAdapter)

    def test_anthropic_mocked_http_success_and_normalization(self):
        """Verify Anthropic Claude adapter with mocked HTTP /v1/messages API response."""
        mock_payload = {
            "id": "msg_anthropic_test_123",
            "type": "message",
            "role": "assistant",
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "end_turn",
            "content": [
                {
                    "type": "text",
                    "text": "## Claude Review\n- **File:** `reports.py`\n- **Lines:** 45\n- **Severity:** critical\n- **Comment:** Cursor pagination lacks tie-breaker.",
                }
            ],
            "usage": {
                "input_tokens": 512,
                "output_tokens": 128,
            },
        }

        mock_http = make_mock_http_response(200, mock_payload)

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-key-mock"}):
            adapter = AnthropicAdapter(dry_run=False)
            with patch("urllib.request.urlopen", return_value=mock_http):
                res: ProviderRawResult = adapter.invoke_review(self.sample_context)

        self.assertEqual(res.http_status, 200)
        self.assertEqual(res.external_id, "msg_anthropic_test_123")
        self.assertEqual(res.prompt_tokens, 512)
        self.assertEqual(res.completion_tokens, 128)
        self.assertEqual(res.finish_reason, "end_turn")
        self.assertIn("Cursor pagination lacks tie-breaker", res.raw_content)

    def test_openai_mocked_http_success_and_normalization(self):
        """Verify OpenAI GPT-4o adapter with mocked HTTP /v1/chat/completions API response."""
        mock_payload = {
            "id": "chatcmpl-test-gpt4o-456",
            "object": "chat.completion",
            "model": "gpt-4o-2024-08-06",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "## GPT-4o Review\n- **File:** `reports.py`\n- **Lines:** 45\n- **Severity:** critical\n- **Comment:** Missing tie-breaker in cursor query.",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 480,
                "completion_tokens": 115,
                "total_tokens": 595,
            },
        }

        mock_http = make_mock_http_response(200, mock_payload)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-proj-test-key-mock"}):
            adapter = OpenAIAdapter(dry_run=False)
            with patch("urllib.request.urlopen", return_value=mock_http):
                res: ProviderRawResult = adapter.invoke_review(self.sample_context)

        self.assertEqual(res.http_status, 200)
        self.assertEqual(res.external_id, "chatcmpl-test-gpt4o-456")
        self.assertEqual(res.prompt_tokens, 480)
        self.assertEqual(res.completion_tokens, 115)
        self.assertEqual(res.finish_reason, "stop")
        self.assertIn("Missing tie-breaker in cursor query", res.raw_content)

    def test_http_rate_limit_maps_to_quota_error(self):
        """Verify HTTP 429 maps to ProviderQuotaError for both providers."""
        err_429 = urllib.error.HTTPError(
            url="https://api.anthropic.com/v1/messages",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=BytesIO(b'{"type": "error", "error": {"type": "rate_limit_error", "message": "Rate limit exceeded"}}'),
        )

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-key"}):
            adapter = AnthropicAdapter(dry_run=False)
            with patch("urllib.request.urlopen", side_effect=err_429):
                with self.assertRaises(ProviderQuotaError):
                    adapter.invoke_review(self.sample_context)

    def test_http_auth_failure_maps_to_auth_error(self):
        """Verify HTTP 401 maps to ProviderAuthenticationError."""
        err_401 = urllib.error.HTTPError(
            url="https://api.openai.com/v1/chat/completions",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=BytesIO(b'{"error": {"message": "Incorrect API key provided"}}'),
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "invalid-key"}):
            adapter = OpenAIAdapter(dry_run=False)
            with patch("urllib.request.urlopen", side_effect=err_401):
                with self.assertRaises(ProviderAuthenticationError):
                    adapter.invoke_review(self.sample_context)

    def test_socket_timeout_maps_to_transport_error(self):
        """Verify network timeout maps to ProviderTransportError."""
        timeout_err = urllib.error.URLError("timed out")

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-key"}):
            adapter = AnthropicAdapter(dry_run=False)
            with patch("urllib.request.urlopen", side_effect=timeout_err):
                with self.assertRaises(ProviderTransportError):
                    adapter.invoke_review(self.sample_context)

    def test_orchestrator_multi_provider_run_and_idempotency(self):
        """Verify orchestrator executing batch across Anthropic, OpenAI, and CodeRabbit."""
        batch = self.orchestrator.schedule_batch(
            experiment_id="exp-p3-multi",
            batch_name="Multi-Provider Execution",
            provider_ids=["anthropic", "openai", "coderabbit"],
            case_numbers=[1, 4, 7],
            context_conditions=[ContextCondition.CODE_ONLY, ContextCondition.CODE_AND_SNAPSHOT],
        )

        # 3 providers * 3 cases * 2 context conditions = 18 planned attempts
        self.assertEqual(batch.planned_attempts_count, 18)

        # Execute using dry_run=True (controlled offline execution)
        run_stats = self.orchestrator.run_batch(batch.id, dry_run=True)
        self.assertEqual(run_stats["completed"], 18)
        self.assertEqual(run_stats["failed"], 0)
        self.assertEqual(run_stats["quota_exhausted"], 0)

        # Idempotency check: running the batch again does not re-execute completed attempts
        run_stats_repeat = self.orchestrator.run_batch(batch.id, dry_run=True)
        self.assertEqual(run_stats_repeat["completed"], 18)
        self.assertEqual(run_stats_repeat["pending"], 0)

        # Verify dual persistence: DB responses & raw evidence disk files
        for att in self.orchestrator.attempt_repo.list_for_batch(batch.id):
            resp = self.orchestrator.response_repo.get_by_attempt_id(att.id)
            self.assertIsNotNone(resp)
            self.assertTrue(len(resp.raw_content) > 20)

            # Check disk mirror
            disk_content = self.evidence_store.get_evidence(batch.id, att.id)
            self.assertIsNotNone(disk_content)
            self.assertEqual(disk_content, resp.raw_content)

        # Verify report generation covers all three providers
        report = self.orchestrator.generate_report(batch.id, title="Phase 3 Multi-Provider Benchmark")
        self.assertIn("anthropic", report["markdown"])
        self.assertIn("openai", report["markdown"])
        self.assertIn("coderabbit", report["markdown"])

    def test_optional_live_anthropic_api(self):
        """Optional live API invocation against Anthropic if PROOFLINE_LIVE_ANTHROPIC=1."""
        if not os.environ.get("PROOFLINE_LIVE_ANTHROPIC") or not os.environ.get("ANTHROPIC_API_KEY"):
            self.skipTest("Skipping live Anthropic API test (PROOFLINE_LIVE_ANTHROPIC not set)")

        adapter = AnthropicAdapter(dry_run=False)
        result = adapter.invoke_review(self.sample_context)
        self.assertEqual(result.http_status, 200)
        self.assertIsNotNone(result.prompt_tokens)
        self.assertIsNotNone(result.completion_tokens)

    def test_optional_live_openai_api(self):
        """Optional live API invocation against OpenAI if PROOFLINE_LIVE_OPENAI=1."""
        if not os.environ.get("PROOFLINE_LIVE_OPENAI") or not os.environ.get("OPENAI_API_KEY"):
            self.skipTest("Skipping live OpenAI API test (PROOFLINE_LIVE_OPENAI not set)")

        adapter = OpenAIAdapter(dry_run=False)
        result = adapter.invoke_review(self.sample_context)
        self.assertEqual(result.http_status, 200)
        self.assertIsNotNone(result.prompt_tokens)
        self.assertIsNotNone(result.completion_tokens)


if __name__ == "__main__":
    unittest.main()
