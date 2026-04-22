"""Centralised configuration management for RatioAI.

Provides configuration dataclasses and helper functions for:
- Azure OpenAI service settings
- Confident AI integration settings
- Environment variable management
- Secure credential handling

Usage::

    from Code.Shared.config.settings import get_azure_openai_config

    config = get_azure_openai_config()
    print(config.endpoint)
"""

import os
from dataclasses import dataclass
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not available; environment variables must be set manually
    pass


@dataclass
class AzureOpenAIConfig:
    """Azure OpenAI configuration settings.

    ``api_key`` is intentionally optional — the project uses
    ``DefaultAzureCredential`` (Managed Identity / Entra ID) as the primary
    authentication method.  An explicit API key is only needed when running
    outside Azure without a configured credential chain.
    """

    endpoint: Optional[str]
    api_key: Optional[str]
    deployment: str
    api_version: str

    def __post_init__(self) -> None:
        """Validate that the required endpoint is present."""
        if not self.endpoint:
            raise ValueError(
                "AZURE_OPENAI_ENDPOINT is required but was not set. "
                "Add it to your .env file or environment."
            )

    @property
    def is_valid(self) -> bool:
        """Return ``True`` when the endpoint is present.

        Authentication may be handled by ``DefaultAzureCredential`` even when
        ``api_key`` is ``None``, so only the endpoint is checked here.
        """
        return bool(self.endpoint)


@dataclass
class ConfidentAIConfig:
    """Confident AI / DeepEval integration configuration."""

    api_key: Optional[str]

    @property
    def enabled(self) -> bool:
        """Return ``True`` if a Confident AI API key is configured."""
        return self.api_key is not None

    @property
    def is_valid(self) -> bool:
        """Alias for :attr:`enabled`."""
        return self.enabled


def get_azure_openai_config() -> AzureOpenAIConfig:
    """Build :class:`AzureOpenAIConfig` from environment variables.

    Returns:
        Populated ``AzureOpenAIConfig`` instance.

    Raises:
        ValueError: If ``AZURE_OPENAI_ENDPOINT`` is not set.
    """
    return AzureOpenAIConfig(
        endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-01-preview"),
    )


def get_confident_ai_config() -> ConfidentAIConfig:
    """Build :class:`ConfidentAIConfig` from environment variables.

    Checks both ``DEEPEVAL_KEY`` and ``CONFIDENT_API_KEY`` for compatibility.
    """
    api_key = os.getenv("DEEPEVAL_KEY") or os.getenv("CONFIDENT_API_KEY")
    return ConfidentAIConfig(api_key=api_key)


def validate_environment() -> dict[str, bool]:
    """Validate all service environment configurations.

    Returns:
        Dictionary mapping service names to their validation status.
    """
    results: dict[str, bool] = {}

    try:
        azure_config = get_azure_openai_config()
        results["azure_openai"] = azure_config.is_valid
    except ValueError:
        results["azure_openai"] = False

    confident_config = get_confident_ai_config()
    results["confident_ai"] = confident_config.is_valid

    return results
