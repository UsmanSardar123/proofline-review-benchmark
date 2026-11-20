"""Provider adapters, configuration, and registry."""

from benchmark.providers.anthropic import AnthropicAdapter, AnthropicConfig
from benchmark.providers.base import (
    BaseProviderAdapter,
    ProviderAuthenticationError,
    ProviderConfig,
    ProviderError,
    ProviderFatalError,
    ProviderQuotaError,
    ProviderRawResult,
    ProviderTransportError,
    ReviewContext,
)
from benchmark.providers.coderabbit import CodeRabbitAdapter, CodeRabbitConfig
from benchmark.providers.mock import MockProviderAdapter
from benchmark.providers.openai import OpenAIAdapter, OpenAIConfig
from benchmark.providers.registry import ProviderRegistry

__all__ = [
    "AnthropicAdapter",
    "AnthropicConfig",
    "BaseProviderAdapter",
    "CodeRabbitAdapter",
    "CodeRabbitConfig",
    "MockProviderAdapter",
    "OpenAIAdapter",
    "OpenAIConfig",
    "ProviderAuthenticationError",
    "ProviderConfig",
    "ProviderError",
    "ProviderFatalError",
    "ProviderQuotaError",
    "ProviderRawResult",
    "ProviderRegistry",
    "ProviderTransportError",
    "ReviewContext",
]
