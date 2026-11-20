"""Registry and factory for AI code-review providers."""

from typing import Optional, Type

from benchmark.providers.anthropic import AnthropicAdapter
from benchmark.providers.base import BaseProviderAdapter, ProviderConfig
from benchmark.providers.coderabbit import CodeRabbitAdapter
from benchmark.providers.mock import MockProviderAdapter
from benchmark.providers.openai import OpenAIAdapter


class ProviderRegistry:
    """Discovers, registers, and instantiates provider adapters."""

    def __init__(self):
        self._adapters: dict[str, Type[BaseProviderAdapter]] = {}
        # Pre-register mock adapter for offline testing and baseline verification
        self.register("mock", MockProviderAdapter)
        self.register("mock-reviewer", MockProviderAdapter)
        # Register production AI review provider adapters
        self.register("coderabbit", CodeRabbitAdapter)
        self.register("anthropic", AnthropicAdapter)
        self.register("openai", OpenAIAdapter)

    def register(self, provider_id: str, adapter_cls: Type[BaseProviderAdapter]) -> None:
        """Register a provider adapter class under a unique identifier."""
        self._adapters[provider_id.lower()] = adapter_cls

    def get_adapter(
        self,
        provider_id: str,
        config: Optional[ProviderConfig] = None,
        **kwargs,
    ) -> BaseProviderAdapter:
        """Instantiate a provider adapter with the given configuration."""
        key = provider_id.lower()
        if key not in self._adapters:
            raise KeyError(
                f"Unknown provider: '{provider_id}'. Available providers: {list(self._adapters.keys())}"
            )
        cls = self._adapters[key]
        return cls(config=config, **kwargs) if config else cls(**kwargs)

    def list_registered(self) -> list[str]:
        """Return a list of registered provider IDs."""
        return sorted(self._adapters.keys())
