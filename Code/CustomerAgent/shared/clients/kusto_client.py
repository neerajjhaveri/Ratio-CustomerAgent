"""Shared Kusto (Azure Data Explorer) client utilities.

Provides a simple cached helper for executing KQL queries from shared or
notebook contexts.  Production services should use their own adapter classes
(``adapters/kusto_adapter.py``) for retry and async support.
"""

import asyncio
import logging
import os
from typing import Dict, List, Optional

from azure.identity import DefaultAzureCredential
from azure.kusto.data import KustoClient, KustoConnectionStringBuilder

logger = logging.getLogger(__name__)

# Per-cluster client cache
_client_cache: Dict[str, KustoClient] = {}


def _get_or_create_client(cluster_uri: str) -> KustoClient:
    """Return a cached Kusto client for *cluster_uri*.

    Creates a new client on first use, then caches it for subsequent calls.
    Uses ``DefaultAzureCredential`` which supports Managed Identity, Azure
    CLI, environment variables, and more.
    """
    if cluster_uri not in _client_cache:
        logger.info("Creating Kusto client for cluster: %s", cluster_uri)
        credential = DefaultAzureCredential()
        kcsb = KustoConnectionStringBuilder.with_azure_token_credential(
            cluster_uri, credential
        )
        _client_cache[cluster_uri] = KustoClient(kcsb)
    return _client_cache[cluster_uri]


def query_kql(
    cluster: str,
    database: str,
    query: str,
    limit: int = 50,
) -> List[Dict]:
    """Execute a KQL query and return the results as a list of dicts.

    Args:
        cluster: Full Kusto cluster URI
                 (e.g. ``"https://icmdataro.centralus.kusto.windows.net"``).
                 Falls back to the ``KUSTO_CLUSTER_URI`` environment variable
                 when an empty string is supplied.
        database: The name of the Kusto database to query.
        query: The KQL query to execute.
        limit: Maximum number of rows to return (0 = unlimited).

    Returns:
        List of dicts representing the rows returned by the query.
    """
    cluster_uri = cluster or os.getenv("KUSTO_CLUSTER_URI", "")
    if not cluster_uri:
        raise ValueError(
            "cluster URI is required — pass it explicitly or set KUSTO_CLUSTER_URI"
        )

    logger.info("Running Kusto query on cluster=%s database=%s", cluster_uri, database)

    client = _get_or_create_client(cluster_uri)
    response = client.execute(database, query)

    if not response.primary_results or len(response.primary_results) == 0:
        logger.warning("Query returned no primary results")
        return []

    rows = response.primary_results[0]
    data = [r.to_dict() for r in rows]
    return data[:limit] if limit else data


async def query_kql_async(
    cluster: str,
    database: str,
    query: str,
    limit: int = 50,
) -> List[Dict]:
    """Async wrapper around :func:`query_kql`.

    Executes the blocking Kusto SDK call in a thread-pool executor so the
    function can be ``await``-ed from async handlers without blocking the
    event loop.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, query_kql, cluster, database, query, limit)
