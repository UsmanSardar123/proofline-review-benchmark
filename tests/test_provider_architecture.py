"""Unit tests for AI provider adapter architecture, auth, and error handling."""

import os
import unittest

from benchmark.domain.enums import ContextCondition
from benchmark.providers.base import (
    BaseProviderAdapter,
    ProviderAuthenticationError,
    ProviderConfig,
    ProviderFatalError,
    ProviderQuotaError,
    ProviderRawResult,
    ProviderTransportError,
    ReviewContext,
)
from benchmark.providers.mock import MockProviderAdapter
from benchmark.providers.registry import ProviderRegistry


class ProviderArchitectureTests(unittest.TestCase):
    def setUp(self):
        self.context = ReviewContext(
            case_id="case-01",
            case_number=1,
            pr_title="Title",
            pr_body="Body",
            base_commit="9b5ac64",
            head_commit="b422577",
            patch_diff="diff",
            context_condition=ContextCondition.CODE_ONLY,
        )

    def test_provider_config_and_secret_masking(self):
        cfg = ProviderConfig(
            provider_id="test-p",
            display_name="Test Provider",
            default_model="model-1",
            api_key_env_var="TEST_API_KEY",
            timeout_seconds=45.0,
            max_retries=3,
        )
        self.assertEqual(cfg.timeout_seconds, 45.0)
        self.assertEqual(cfg.max_retries, 3)

        # Secret masking tests
        self.assertEqual(BaseProviderAdapter.mask_secret(None), "<none>")
        self.assertEqual(BaseProviderAdapter.mask_secret(""), "<none>")
        self.assertEqual(BaseProviderAdapter.mask_secret("short"), "***")
        self.assertEqual(BaseProviderAdapter.mask_secret("sk-ant-api03-abcdef1234"), "sk-...1234")

    def test_credential_resolution_from_environment(self):
        cfg = ProviderConfig(
            provider_id="auth-test",
            display_name="Auth Test",
            default_model="m1",
            api_key_env_var="TEST_SECRET_ENV",
        )
        adapter = MockProviderAdapter(config=cfg)

        # Missing key raises ProviderAuthenticationError
        if "TEST_SECRET_ENV" in os.environ:
            del os.environ["TEST_SECRET_ENV"]
        with self.assertRaises(ProviderAuthenticationError):
            adapter.get_api_key()

        # Present key returns stripped secret
        os.environ["TEST_SECRET_ENV"] = "  secret_key_12345  "
        try:
            self.assertEqual(adapter.get_api_key(), "secret_key_12345")
        finally:
            del os.environ["TEST_SECRET_ENV"]

    def test_http_error_mapping(self):
        adapter = MockProviderAdapter()

        # 429 Quota
        with self.assertRaises(ProviderQuotaError):
            adapter.handle_http_error(429, "Too Many Requests")

        with self.assertRaises(ProviderQuotaError):
            adapter.handle_http_error(200, "Error: rate_limit exceeded")

        # 401/403 Auth
        with self.assertRaises(ProviderAuthenticationError):
            adapter.handle_http_error(401, "Unauthorized")

        with self.assertRaises(ProviderAuthenticationError):
            adapter.handle_http_error(403, "Forbidden")

        # 400 Fatal
        with self.assertRaises(ProviderFatalError):
            adapter.handle_http_error(400, "Bad Request")

        # 503 Transport
        with self.assertRaises(ProviderTransportError):
            adapter.handle_http_error(503, "Service Unavailable")

    def test_execute_with_retry_transient_recovery(self):
        # Adapter fails on first call, succeeds on second
        adapter = MockProviderAdapter(mode="retry_once")
        adapter.config.backoff_factor = 0.01
        res = adapter.execute_with_retry(self.context)
        self.assertEqual(res.http_status, 200)
        self.assertEqual(adapter.calls, 2)

    def test_execute_with_retry_quota_no_retry(self):
        # Quota error should fail immediately without consuming retries
        adapter = MockProviderAdapter(mode="quota")
        with self.assertRaises(ProviderQuotaError):
            adapter.execute_with_retry(self.context)
        self.assertEqual(adapter.calls, 1)

    def test_provider_registry(self):
        reg = ProviderRegistry()
        self.assertIn("mock", reg.list_registered())
        adapter = reg.get_adapter("mock")
        self.assertIsInstance(adapter, MockProviderAdapter)

        with self.assertRaises(KeyError):
            reg.get_adapter("nonexistent-provider")


if __name__ == "__main__":
    unittest.main()
