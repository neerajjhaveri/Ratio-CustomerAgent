"""
LLM client factory for MAF agents.

Creates Azure OpenAI chat clients used by MAF Agent instances.

Migration note: shared/clients/chat_client.py provides a FoundryChatClient-based
implementation. This file uses OpenAIChatCompletionClient from agent_framework.openai,
which is the MAF-native pattern. Migrate when shared client supports the same interface.
"""
from __future__ import annotations

import logging
import os

from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

logger = logging.getLogger(__name__)


def create_chat_client(model: str | None = None):
    """Create an AzureOpenAI-compatible chat client for MAF agents.

    Uses Azure OpenAI via the openai package with DefaultAzureCredential.
    MAF's Agent accepts any client that implements get_response().

    Args:
        model: Optional model deployment name override. When provided, uses
               this instead of the AZURE_OPENAI_GPT_MODEL_DEPLOYMENT_NAME env var.

    Returns:
        An AzureOpenAIChatClient instance for use with MAF Agent.
    """
    from agent_framework.openai import OpenAIChatCompletionClient

    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    deployment = model or os.getenv("AZURE_OPENAI_GPT_MODEL_DEPLOYMENT_NAME", "gpt-4o")

    credential = DefaultAzureCredential()

    client = OpenAIChatCompletionClient(
        azure_endpoint=endpoint,
        api_version=api_version,
        model=deployment,
        credential=credential,
    )

    logger.info("Created OpenAIChatCompletionClient (Chat Completions API) → %s / %s", endpoint, deployment)
    return client
