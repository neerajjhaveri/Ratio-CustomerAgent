"""Azure Data Explorer (Kusto) authentication helper.

Delegates auth to helper.auth with priority:
  MI → DefaultAzureCredential → CertificateCredential.
Uses token_provider for auto-refreshing tokens.
"""
from __future__ import annotations
import logging
from azure.kusto.data import KustoConnectionStringBuilder, KustoClient
from helper.auth import get_token

logger = logging.getLogger("ratio_mcp")


def get_kusto_client(kustocluster: str, *, cert_client_id: str | None = None) -> KustoClient:
    """Build a KustoClient with auto-refreshing token provider.
    Auth priority: MI → DefaultAzureCredential → CertificateCredential.

    Args:
        kustocluster: Kusto cluster URL.
        cert_client_id: Optional override client ID for CertificateCredential auth.
                        When set, uses this instead of the default AUTH_CLIENT_ID.
    """
    scope = f"{kustocluster}/.default"
    kcsb = KustoConnectionStringBuilder.with_token_provider(
        kustocluster, lambda: get_token(scope, cert_client_id=cert_client_id)
    )
    return KustoClient(kcsb)


__all__ = ["get_kusto_client"]
