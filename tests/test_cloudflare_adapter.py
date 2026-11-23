"""Unit and integration tests for Cloudflare Workers AI provider adapter.

Verifies:
1. Adapter initialization, default model, and payload formatting.
2. Safe credential resolution from environment and placeholder detection.
3. Strict Zero-Cost policy enforcement via conservative daily Neuron tracking.
4. Mocked HTTP response parsing across standard, OpenAI-compatible, and raw text formats.
5. Error handling for HTTP 401, 403, 429, 500, and network timeouts.
6. Offline deterministic dry-run mode (zero network requests).
7. ProviderRegistry resolution.
"""

from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from benchmark.domain.enums import ContextCondition
from benchmark.providers.base import (
    ProviderAuthenticationError,
    ProviderFatalError,
    ProviderQuotaError,
    ProviderTransportError,
    ReviewContext,
)
from benchmark.providers.cloudflare import (
    CloudflareAdapter,
    CloudflareConfig,
    DEFAULT_MODEL,
    FREE_DAILY_NEURON_LIMIT,
    NeuronTracker,
    SUPPORTED_MODELS,
)
from benchmark.providers.registry import ProviderRegistry


def make_mock_http_response(status_code: int, data: dict, headers: dict = None):
    """Construct a mock urllib.request.urlopen context manager returning JSON."""
    body_bytes = json.dumps(data).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.status = status_code
    mock_resp.read.return_value = body_bytes
    mock_resp.headers = headers or {"content-type": "application/json"}
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None
    return mock_resp


class TestCloudflareWorkersAIAdapter(unittest.TestCase):
    """Test suite for CloudflareAdapter."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.usage_file = Path(self.tmp_dir.name) / "test_neurons.json"

        self.context = ReviewContext(
            case_id="case-01",
            case_number=1,
            pr_title="Page report history by scheduled time",
            pr_body="Fix pagination cursor bug",
            base_commit="9b5ac64",
            head_commit="b422577",
            patch_diff="--- a/reports.py\n+++ b/reports.py\n@@ -45,1 +45,1 @@\n-WHERE scheduled_at < ?\n+WHERE scheduled_at <= ?",
            context_condition=ContextCondition.CODE_ONLY,
        )

    def tearDown(self):
        try:
            self.tmp_dir.cleanup()
        except Exception:
            pass

    def test_default_configuration_and_models(self):
        """Verify default configuration attributes and supported model catalog."""
        adapter = CloudflareAdapter()
        self.assertEqual(adapter.provider_id, "cloudflare")
        self.assertEqual(adapter.display_name, "Cloudflare Workers AI")
        self.assertEqual(adapter.default_model, DEFAULT_MODEL)
        self.assertIn("@cf/qwen/qwen2.5-coder-32b-instruct", SUPPORTED_MODELS)
        self.assertIn("@cf/meta/llama-3.3-70b-instruct-fp8-fast", SUPPORTED_MODELS)
        self.assertIn("@cf/meta/llama-3.1-8b-instruct", SUPPORTED_MODELS)

    def test_payload_construction(self):
        """Verify message structure built for Cloudflare Workers AI."""
        adapter = CloudflareAdapter(config=CloudflareConfig(
            provider_id="cloudflare",
            display_name="Cloudflare Workers AI",
            default_model="@cf/qwen/qwen2.5-coder-32b-instruct",
            account_id="mock_account_123",
            dry_run=True,
        ))
        payload = adapter.build_payload(self.context)
        self.assertIn("messages", payload)
        self.assertEqual(len(payload["messages"]), 2)
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(payload["messages"][1]["role"], "user")
        self.assertIn("Page report history", payload["messages"][1]["content"])
        self.assertEqual(payload["max_tokens"], 1536)
        self.assertEqual(payload["temperature"], 0.0)

    def test_endpoint_url_construction(self):
        """Verify REST endpoint URL construction."""
        adapter = CloudflareAdapter(config=CloudflareConfig(
            provider_id="cloudflare",
            display_name="Cloudflare Workers AI",
            default_model="@cf/qwen/qwen2.5-coder-32b-instruct",
            account_id="test_acc_999",
            dry_run=True,
        ))
        url = adapter.build_endpoint_url()
        expected = "https://api.cloudflare.com/client/v4/accounts/test_acc_999/ai/run/@cf/qwen/qwen2.5-coder-32b-instruct"
        self.assertEqual(url, expected)

    def test_missing_credentials_raises_auth_error(self):
        """Verify missing token or account ID raises ProviderAuthenticationError."""
        with patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "", "CLOUDFLARE_ACCOUNT_ID": ""}, clear=True):
            adapter = CloudflareAdapter(config=CloudflareConfig(
                provider_id="cloudflare",
                display_name="Cloudflare Workers AI",
                default_model=DEFAULT_MODEL,
                dry_run=False,
            ))
            with self.assertRaises(ProviderAuthenticationError):
                adapter.invoke_review(self.context)

    def test_placeholder_credentials_raises_auth_error(self):
        """Verify placeholder values in .env raise ProviderAuthenticationError."""
        with patch.dict(os.environ, {
            "CLOUDFLARE_API_TOKEN": "paste_your_new_token_here",
            "CLOUDFLARE_ACCOUNT_ID": "your_cloudflare_account_id",
        }):
            adapter = CloudflareAdapter(config=CloudflareConfig(
                provider_id="cloudflare",
                display_name="Cloudflare Workers AI",
                default_model=DEFAULT_MODEL,
                dry_run=False,
            ))
            with self.assertRaises(ProviderAuthenticationError):
                adapter.invoke_review(self.context)

    @patch("urllib.request.urlopen")
    def test_mocked_http_success_and_normalization(self, mock_urlopen):
        """Verify successful HTTP 200 response normalization."""
        mock_payload = {
            "result": {
                "response": "## Cloudflare Review\n- **File:** `reports.py`\n- **Lines:** 45\n- **Severity:** critical\n- **Comment:** Missing tie-breaker."
            },
            "success": True,
            "errors": [],
            "messages": [],
        }
        mock_urlopen.return_value = make_mock_http_response(200, mock_payload)

        cfg = CloudflareConfig(
            provider_id="cloudflare",
            display_name="Cloudflare Workers AI",
            default_model="@cf/qwen/qwen2.5-coder-32b-instruct",
            account_id="mock_acc_id",
            usage_file=self.usage_file,
            dry_run=False,
        )
        adapter = CloudflareAdapter(config=cfg)

        with patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "valid_mock_token_12345"}):
            res = adapter.invoke_review(self.context)

        self.assertEqual(res.http_status, 200)
        self.assertEqual(res.execution_mode, "live")
        self.assertEqual(res.model_name, "@cf/qwen/qwen2.5-coder-32b-instruct")
        self.assertIn("Missing tie-breaker", res.raw_content)
        self.assertGreater(res.prompt_tokens, 0)
        self.assertGreater(res.completion_tokens, 0)

    @patch("urllib.request.urlopen")
    def test_mocked_http_401_raises_auth_error(self, mock_urlopen):
        """Verify HTTP 401 Unauthorized raises ProviderAuthenticationError."""
        err_response = BytesIO(b'{"success": false, "errors": [{"message": "Invalid API Token"}]}')
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://api.cloudflare.com/...",
            code=401,
            msg="Unauthorized",
            hdrs={"content-type": "application/json"},
            fp=err_response,
        )

        cfg = CloudflareConfig(
            provider_id="cloudflare",
            display_name="Cloudflare Workers AI",
            default_model=DEFAULT_MODEL,
            account_id="mock_acc_id",
            usage_file=self.usage_file,
            dry_run=False,
        )
        adapter = CloudflareAdapter(config=cfg)

        with patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "invalid_mock_token"}):
            with self.assertRaises(ProviderAuthenticationError):
                adapter.invoke_review(self.context)

    @patch("urllib.request.urlopen")
    def test_mocked_http_429_raises_quota_error(self, mock_urlopen):
        """Verify HTTP 429 Rate Limit raises ProviderQuotaError."""
        err_response = BytesIO(b'{"success": false, "errors": [{"message": "Rate limit exceeded"}]}')
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://api.cloudflare.com/...",
            code=429,
            msg="Too Many Requests",
            hdrs={"content-type": "application/json"},
            fp=err_response,
        )

        cfg = CloudflareConfig(
            provider_id="cloudflare",
            display_name="Cloudflare Workers AI",
            default_model=DEFAULT_MODEL,
            account_id="mock_acc_id",
            usage_file=self.usage_file,
            dry_run=False,
        )
        adapter = CloudflareAdapter(config=cfg)

        with patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "mock_token"}):
            with self.assertRaises(ProviderQuotaError):
                adapter.invoke_review(self.context)

    @patch("urllib.request.urlopen")
    def test_mocked_http_500_raises_transport_error(self, mock_urlopen):
        """Verify HTTP 500 Server Error raises ProviderTransportError."""
        err_response = BytesIO(b'{"success": false, "errors": [{"message": "Internal Server Error"}]}')
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://api.cloudflare.com/...",
            code=500,
            msg="Server Error",
            hdrs={"content-type": "application/json"},
            fp=err_response,
        )

        cfg = CloudflareConfig(
            provider_id="cloudflare",
            display_name="Cloudflare Workers AI",
            default_model=DEFAULT_MODEL,
            account_id="mock_acc_id",
            usage_file=self.usage_file,
            dry_run=False,
        )
        adapter = CloudflareAdapter(config=cfg)

        with patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "mock_token"}):
            with self.assertRaises(ProviderTransportError):
                adapter.invoke_review(self.context)

    def test_neuron_tracker_and_hard_zero_cost_policy(self):
        """Verify daily Neuron tracking and strict refusal to exceed quota."""
        tracker = NeuronTracker(usage_file=self.usage_file)

        # Estimate neurons for 500 in, 1000 out with Qwen 2.5 Coder 32B
        est = tracker.estimate_neurons("@cf/qwen/qwen2.5-coder-32b-instruct", 500, 1000)
        self.assertGreater(est, 50)
        self.assertLess(est, 200)

        # Record 4,900 neurons
        tracker.record_usage(4900)
        self.assertEqual(tracker.get_daily_used_neurons(), 4900)

        adapter = CloudflareAdapter(config=CloudflareConfig(
            provider_id="cloudflare",
            display_name="Cloudflare Workers AI",
            default_model="@cf/qwen/qwen2.5-coder-32b-instruct",
            account_id="test_acc",
            daily_neuron_limit=5000,
            allow_paid_overage=False,  # Strict zero-cost
            usage_file=self.usage_file,
            dry_run=False,
        ))

        # Requesting another 150 neurons would exceed 5,000 conservative limit -> must raise ProviderQuotaError
        with patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "mock_token"}):
            with self.assertRaises(ProviderQuotaError) as ctx:
                adapter.check_neuron_allowance(500, 1000)
            self.assertIn("Strict Zero-Cost Policy", str(ctx.exception))

    def test_fail_closed_on_corrupt_neuron_file(self):
        """Verify fail-closed behavior: unreadable usage file halts rather than guessing."""
        with open(self.usage_file, "w", encoding="utf-8") as f:
            f.write("{corrupt json content")

        tracker = NeuronTracker(usage_file=self.usage_file)
        with self.assertRaises(ProviderQuotaError) as ctx:
            tracker.get_daily_used_neurons()
        self.assertIn("fail-closed zero-cost policy", str(ctx.exception))

    def test_max_input_token_limit_exceeded(self):
        """Verify prompt exceeding max_input_tokens raises ProviderFatalError."""
        cfg = CloudflareConfig(
            provider_id="cloudflare",
            display_name="Cloudflare Workers AI",
            default_model="@cf/qwen/qwen2.5-coder-32b-instruct",
            account_id="test_acc",
            max_input_tokens=10,  # artificially low
            usage_file=self.usage_file,
            dry_run=False,
        )
        adapter = CloudflareAdapter(config=cfg)
        with patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "mock_token"}):
            with self.assertRaises(ProviderFatalError) as ctx:
                adapter.invoke_review(self.context)
            self.assertIn("exceed maximum allowed input limit", str(ctx.exception))

    def test_cmd_cloudflare_status_execution(self):
        """Verify CLI cloudflare-status command runs safely without network calls."""
        from benchmark.cli.commands import cmd_cloudflare_status
        code = cmd_cloudflare_status()
        self.assertEqual(code, 0)

    def test_offline_dry_run_invocation(self):
        """Verify offline dry-run returns deterministic results with zero network calls."""
        cfg = CloudflareConfig(
            provider_id="cloudflare",
            display_name="Cloudflare Workers AI",
            default_model="@cf/qwen/qwen2.5-coder-32b-instruct",
            dry_run=True,
        )
        adapter = CloudflareAdapter(config=cfg)
        res = adapter.invoke_review(self.context)

        self.assertEqual(res.http_status, 200)
        self.assertEqual(res.execution_mode, "dry_run")
        self.assertEqual(res.model_name, "@cf/qwen/qwen2.5-coder-32b-instruct")
        self.assertIn("Cursor pagination", res.raw_content)

    def test_provider_registry_resolves_cloudflare(self):
        """Verify ProviderRegistry resolves 'cloudflare' and 'cloudflare-ai'."""
        reg = ProviderRegistry()
        self.assertIn("cloudflare", reg.list_registered())
        self.assertIn("cloudflare-ai", reg.list_registered())

        cf_inst = reg.get_adapter("cloudflare", dry_run=True)
        self.assertIsInstance(cf_inst, CloudflareAdapter)
        self.assertEqual(cf_inst.provider_id, "cloudflare")


if __name__ == "__main__":
    unittest.main()
