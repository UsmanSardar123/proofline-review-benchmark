"""Unit tests for Greptile AI reviewer adapter."""

import unittest

from benchmark.domain.enums import ContextCondition
from benchmark.providers.base import (
    ProviderAuthenticationError,
    ProviderQuotaError,
    ReviewContext,
)
from benchmark.providers.greptile import GreptileAdapter, GreptileConfig
from benchmark.providers.registry import ProviderRegistry


class GreptileAdapterTests(unittest.TestCase):
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
        cfg = GreptileConfig(
            provider_id="greptile",
            display_name="Greptile AI",
            default_model="greptile-review-v2",
            mode="fixture",
        )
        adapter = GreptileAdapter(config=cfg)
        result = adapter.invoke_review(self.context)

        self.assertEqual(result.http_status, 200)
        self.assertEqual(result.external_id, "grep-rev-1")
        self.assertIn("Greptile Review Summary", result.raw_content)
        self.assertIn("Page report history by scheduled time", result.raw_content)
        self.assertGreater(result.prompt_tokens, 0)
        self.assertGreater(result.completion_tokens, 0)
        self.assertIsNotNone(result.duration_ms)

    def test_missing_api_key_raises_auth_error(self):
        cfg = GreptileConfig(
            provider_id="greptile",
            display_name="Greptile AI",
            default_model="greptile-review-v2",
            mode="api",
            api_key_env_var="NONEXISTENT_GREPTILE_KEY",
        )
        adapter = GreptileAdapter(config=cfg)
        with self.assertRaises(ProviderAuthenticationError):
            adapter.invoke_review(self.context)

    def test_greptile_http_error_handling(self):
        adapter = GreptileAdapter(config=GreptileConfig(
            provider_id="greptile",
            display_name="Greptile AI",
            default_model="greptile-review-v2",
            mode="fixture",
        ))

        with self.assertRaises(ProviderQuotaError):
            adapter.handle_http_error(429, "Greptile rate limit exceeded")

    def test_provider_registry_resolves_greptile(self):
        reg = ProviderRegistry()
        adapter = reg.get_adapter("greptile")
        self.assertIsInstance(adapter, GreptileAdapter)

        manual_adapter = reg.get_adapter("greptile-web")
        self.assertEqual(manual_adapter.provider_id, "greptile-web")
