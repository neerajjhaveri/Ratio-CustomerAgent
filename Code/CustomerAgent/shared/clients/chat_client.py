"""Shared Agent Framework chat client singleton.

Provides a lazily-initialised ``FoundryChatClient`` using
``DefaultAzureCredential`` for Azure Foundry / Azure OpenAI.

Usage::

    from Code.Shared.clients.chat_client import get_chat_client

    client = get_chat_client()
    agent = client.as_agent(name="MyAgent", instructions="...")
"""

import logging
import os
import threading

from Code.Shared.config.settings import get_azure_openai_config

logger = logging.getLogger(__name__)

_client = None
_lock = threading.Lock()


def get_chat_client():
    """Return a process-wide ``AzureAIClient`` singleton (thread-safe).

    Lazily imports ``agent_framework_azure_ai`` so this module can be
    imported even when the package is not installed (guarded by callers).
    """
    global _client

    if _client is not None:
        return _client

    with _lock:
        if _client is not None:
            return _client

        from agent_framework.foundry import FoundryChatClient
        from azure.identity.aio import DefaultAzureCredential

        config = get_azure_openai_config()
        endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT", config.endpoint or "")

        logger.info(
            "Initialising FoundryChatClient: deployment=%s endpoint=%s",
            config.deployment,
            endpoint,
        )

        _client = FoundryChatClient(
            project_endpoint=endpoint,
            model=config.deployment,
            credential=DefaultAzureCredential(),
        )
        logger.info("FoundryChatClient initialised successfully")

    return _client
