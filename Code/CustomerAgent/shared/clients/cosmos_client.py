"""Shared Cosmos DB client singleton.

Provides a lazily-initialised async ``CosmosClient`` using
``DefaultAzureCredential`` for Azure Cosmos DB (NoSQL API).

Usage::

    from Code.Shared.clients.cosmos_client import get_cosmos_container

    container = get_cosmos_container("my-database", "my-container")
    items = await container.query_items("SELECT * FROM c", enable_cross_partition_query=True)
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_cosmos_client = None
_database_cache: dict = {}
_container_cache: dict = {}


def get_cosmos_client():
    """Return a cached async ``CosmosClient`` singleton.

    Lazily imports ``azure.cosmos.aio`` so the module can be imported
    even when the package is not installed.

    Environment variables:
        COSMOSDB_ENDPOINT: The Cosmos DB account endpoint URL.
        COSMOSDB_KEY: Optional account key (uses DefaultAzureCredential if not set).
    """
    global _cosmos_client
    if _cosmos_client is not None:
        return _cosmos_client

    try:
        from azure.cosmos.aio import CosmosClient
    except ImportError as exc:
        raise RuntimeError(
            "azure-cosmos is not installed. Run: pip install azure-cosmos"
        ) from exc

    endpoint = os.getenv("COSMOSDB_ENDPOINT", "")
    if not endpoint:
        raise RuntimeError(
            "COSMOSDB_ENDPOINT must be set to use Cosmos DB."
        )

    key = os.getenv("COSMOSDB_KEY", "")
    if key:
        _cosmos_client = CosmosClient(endpoint, credential=key)
        logger.info("CosmosClient initialised with account key: %s", endpoint)
    else:
        from azure.identity.aio import DefaultAzureCredential
        credential = DefaultAzureCredential()
        _cosmos_client = CosmosClient(endpoint, credential=credential)
        logger.info("CosmosClient initialised with DefaultAzureCredential: %s", endpoint)

    return _cosmos_client


def get_cosmos_database(database_name: Optional[str] = None):
    """Return a cached ``DatabaseProxy`` for the given database.

    Falls back to the ``COSMOSDB_DATABASE`` environment variable.
    """
    db_name = database_name or os.getenv("COSMOSDB_DATABASE", "")
    if not db_name:
        raise RuntimeError(
            "database_name is required — pass it explicitly or set COSMOSDB_DATABASE"
        )

    if db_name not in _database_cache:
        client = get_cosmos_client()
        _database_cache[db_name] = client.get_database_client(db_name)
        logger.info("Cosmos database proxy created: %s", db_name)

    return _database_cache[db_name]


def get_cosmos_container(
    database_name: Optional[str] = None,
    container_name: Optional[str] = None,
):
    """Return a cached ``ContainerProxy`` for the given database and container.

    Falls back to ``COSMOSDB_DATABASE`` and ``COSMOSDB_CONTAINER`` env vars.
    """
    db_name = database_name or os.getenv("COSMOSDB_DATABASE", "")
    ctr_name = container_name or os.getenv("COSMOSDB_CONTAINER", "")
    if not db_name or not ctr_name:
        raise RuntimeError(
            "database_name and container_name are required — "
            "pass them explicitly or set COSMOSDB_DATABASE and COSMOSDB_CONTAINER"
        )

    cache_key = f"{db_name}/{ctr_name}"
    if cache_key not in _container_cache:
        database = get_cosmos_database(db_name)
        _container_cache[cache_key] = database.get_container_client(ctr_name)
        logger.info("Cosmos container proxy created: %s", cache_key)

    return _container_cache[cache_key]


async def close_cosmos_client() -> None:
    """Close the Cosmos client and clear all caches."""
    global _cosmos_client, _database_cache, _container_cache
    if _cosmos_client is not None:
        await _cosmos_client.close()
        _cosmos_client = None
    _database_cache.clear()
    _container_cache.clear()
    logger.info("CosmosClient closed and caches cleared")
