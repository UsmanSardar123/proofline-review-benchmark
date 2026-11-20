"""Unit tests for Anthropic Claude and OpenAI GPT adapters."""

import os
import unittest

from benchmark.domain.enums import ContextCondition
from benchmark.providers.anthropic import AnthropicAdapter, AnthropicConfig
from benchmark.providers.base import (
    ProviderAuthenticationError,
    ProviderQuotaError,
    ProviderTransportError,
    ReviewContext,
)
from benchmark.providers.openai import OpenAIAdapter, OpenAIConfig
from benchmark.providers.registry import ProviderRegistry


class LLMAdaptersTests(unittest.TestCase):
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

    def test_anthropic_payload_and_dry_run(self):
        adapter = AnthropicAdapter(config=AnthropicConfig(
            provider_id="anthropic",
            display_name="Claude",
            default_model="claude-3-5-sonnet-20241022",
            dry_run=True,
        ))
        payload = adapter.build_payload(self.context)
        self.assertEqual(payload["model"], "claude-3-5-sonnet-20241022")
        self.assertEqual(len(payload["messages"]), 1)
        self.assertEqual(payload["messages"][0]["role"], "user")
        self.assertIn("Page report history by scheduled time", payload["messages"][0]["content"])

        # Execute dry-run
        res = adapter.invoke_review(self.context)
        self.assertEqual(res.http_status, 200)
        self.assertEqual(res.model_name, "claude-3-5-sonnet-20241022")
        self.assertEqual(res.finish_reason, "end_turn")
        self.assertIn("Claude Review", res.raw_content)
        self.assertEqual(res.prompt_tokens, 320)
        self.assertEqual(res.completion_tokens, 90)

    def test_anthropic_missing_key_raises_auth_error(self):
        adapter = AnthropicAdapter(config=AnthropicConfig(
            provider_id="anthropic",
            display_name="Claude",
            default_model="claude-3-5-sonnet",
            api_key_env_var="NONEXISTENT_ANTHROPIC_KEY",
            dry_run=False,
        ))
        with self.assertRaises(ProviderAuthenticationError):
            adapter.invoke_review(self.context)

    def test_openai_payload_and_dry_run(self):
        adapter = OpenAIAdapter(config=OpenAIConfig(
            provider_id="openai",
            display_name="GPT-4o",
            default_model="gpt-4o",
            dry_run=True,
        ))
        payload = adapter.build_payload(self.context)
        self.assertEqual(payload["model"], "gpt-4o")
        self.assertEqual(len(payload["messages"]), 2)
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(payload["messages"][1]["role"], "user")

        # Execute dry-run
        res = adapter.invoke_review(self.context)
        self.assertEqual(res.http_status, 200)
        self.assertEqual(res.model_name, "gpt-4o")
        self.assertEqual(res.finish_reason, "stop")
        self.assertIn("GPT-4o Review", res.raw_content)
        self.assertEqual(res.prompt_tokens, 310)
        self.assertEqual(res.completion_tokens, 85)

    def test_openai_missing_key_raises_auth_error(self):
        adapter = OpenAIAdapter(config=OpenAIConfig(
            provider_id="openai",
            display_name="GPT-4o",
            default_model="gpt-4o",
            api_key_env_var="NONEXISTENT_OPENAI_KEY",
            dry_run=False,
        ))
        with self.assertRaises(ProviderAuthenticationError):
            adapter.invoke_review(self.context)

    def test_provider_registry_resolves_all_llms(self):
        reg = ProviderRegistry()
        self.assertIn("anthropic", reg.list_registered())
        self.assertIn("openai", reg.list_registered())

        anthropic_inst = reg.get_adapter("anthropic")
        self.assertIsInstance(anthropic_inst, AnthropicAdapter)

        openai_inst = reg.get_adapter("openai")
        self.assertIsInstance(openai_inst, OpenAIAdapter)


if __name__ == "__main__":
    unittest.main()
