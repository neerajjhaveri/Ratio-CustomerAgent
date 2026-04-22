# Moved from src/adls.py
"""Azure Data Lake Storage Gen2 helper utilities."""
from __future__ import annotations
import os
from typing import Optional
from azure.storage.filedatalake import DataLakeServiceClient
from azure.core.exceptions import AzureError
import logging
from helper.auth import get_credential, get_cert_credential

class ADLSConfig:
    def __init__(self, account_name: str, file_system: str):
        self.account_name = account_name
        self.file_system = file_system
    @property
    def dfs_url(self) -> str:
        return f"https://{self.account_name}.dfs.core.windows.net"

logger = logging.getLogger("ratio_mcp")


def _build_client(cfg: ADLSConfig):
    """Build a DataLakeServiceClient.
    Auth priority: MI → DefaultAzureCredential → CertificateCredential.
    """
    # 1. MI → DefaultAzureCredential
    try:
        credential = get_credential()
        return DataLakeServiceClient(account_url=cfg.dfs_url, credential=credential)
    except Exception as e:
        logger.warning("Primary credential failed for ADLS: %s; trying cert fallback", e)

    # 2. Certificate fallback
    cert_cred = get_cert_credential()
    if cert_cred:
        return DataLakeServiceClient(account_url=cfg.dfs_url, credential=cert_cred)

    raise ConnectionError(
        "All ADLS auth methods failed. Configure USER_ASSIGNED_CLIENT_ID, "
        "DefaultAzureCredential, or CERT_NAME + KEY_VAULT_NAME."
    )

def read_text_file(path: str, account_name: Optional[str] = None, file_system: Optional[str] = None) -> str:
    account_name = account_name or os.getenv("ADLS_ACCOUNT_NAME")
    file_system = file_system or os.getenv("ADLS_FILE_SYSTEM")
    if not account_name or not file_system:
        raise RuntimeError("ADLS account name and file system required for remote load")
    cfg = ADLSConfig(account_name, file_system)
    try:
        client = _build_client(cfg)
        file_client = client.get_file_system_client(cfg.file_system).get_file_client(path)
        download = file_client.download_file()
        data = download.readall()
        return data.decode("utf-8", errors="replace")
    except AzureError as e:
        raise RuntimeError(f"Azure error reading ADLS file '{path}': {e}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error reading ADLS file '{path}': {e}") from e

__all__ = ["read_text_file", "ADLSConfig"]
