"""Shared cross-cutting service clients used by multiple services and UIs.

Available clients:

* ``chat_client`` — ``FoundryChatClient`` singleton for Agent Framework
* ``kusto_client`` — Kusto (Azure Data Explorer) query helpers

Configuration is managed centrally in ``Shared.config.settings``.
"""
