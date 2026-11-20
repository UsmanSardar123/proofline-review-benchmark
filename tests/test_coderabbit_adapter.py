"""Unit tests for CodeRabbit AI reviewer adapter."""

import os
import unittest

from benchmark.domain.enums import ContextCondition
from benchmark.providers.base import (
    ProviderAuthenticationError,
    ProviderQuotaError,
    ProviderTransportError,
    ReviewContext,
)
from benchmark.providers.coderabbit import CodeRabbitAdapter, CodeRabbitConfig
from benchmark.providers.registry import ProviderRegistry


class CodeRabbitAdapterTests(unittest.TestCase):
    def setUp(self):
        self.context = ReviewContext(
            case_id="case-01",
            case_number=1,
            pr_title="Page report history by scheduled time",
            pr_body="Show the most recently scheduled deliveries first.",
            base_commit="9b5ac64",
            head_commit="b422577",
            patch_diff="diff --git a/reports.py b/reports.py\n...",
            context_condition=ContextCondition.CODE_ONLY,
        )

    def test_fixture_mode_invocation(self):
        cfg = CodeRabbitConfig(
            provider_id="coderabbit",
            display_name="CodeRabbit AI",
            default_model="coderabbit-review",
            mode="fixture",
        )
        adapter = CodeRabbitAdapter(config=cfg)
        result = adapter.invoke_review(self.context)

        self.assertEqual(result.http_status, 200)
        self.assertEqual(result.external_id, "cr-rev-1")
        self.assertIn("CodeRabbit Review Summary", result.raw_content)
        self.assertIn("Page report history by scheduled time", result.raw_content)
        self.assertGreater(result.prompt_tokens, 0)
        self.assertGreater(result.completion_tokens, 0)
        self.assertIsNotNone(result.duration_ms)

    def test_missing_api_key_raises_auth_error(self):
        cfg = CodeRabbitConfig(
            provider_id="coderabbit",
            display_name="CodeRabbit AI",
            default_model="coderabbit-review",
            mode="api",
            api_key_env_var="NONEXISTENT_CODERABBIT_KEY",
        )
        adapter = CodeRabbitAdapter(config=cfg)
        with self.assertRaises(ProviderAuthenticationError):
            adapter.invoke_review(self.context)

    def test_coderabbit_http_error_handling(self):
        adapter = CodeRabbitAdapter(config=CodeRabbitConfig(
            provider_id="coderabbit",
            display_name="CodeRabbit AI",
            default_model="coderabbit-review",
            mode="fixture",
        ))

        # 429 Rate limit
        with self.assertRaises(ProviderQuotaError):
            adapter.handle_http_error(429, "Free trial review quota exceeded")

        # 502 Bad Gateway
        with self.assertRaises(ProviderTransportError):
            adapter.handle_http_error(502, "Bad Gateway")

    def test_provider_registry_resolves_coderabbit(self):
        reg = ProviderRegistry()
        self.assertIn("coderabbit", reg.list_registered())
        adapter = reg.get_adapter("coderabbit")
        self.assertIsInstance(adapter, CodeRabbitAdapter)


if __name__ == "__main__":
    unittest.main()
