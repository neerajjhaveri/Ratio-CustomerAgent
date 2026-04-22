"""MCP integration for MAF GroupChat agents.

Creates MCPStreamableHTTPTool instances with auth header support
for passing user tokens to the MCP server.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from agent_framework import MCPStreamableHTTPTool
from dotenv import load_dotenv

from helper.agent_logger import get_current_xcv
from helper.auth import get_mcp_bearer_token, get_user_token

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

logger = logging.getLogger(__name__)

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp")


def _create_authenticated_http_client():
    """Create an httpx.AsyncClient that injects auth headers on EVERY request.

    This ensures the MCP protocol's initial `initialize` handshake also
    carries the bearer token (the header_provider only fires during call_tool).
    """
    import httpx

    async def _inject_auth_headers(request: httpx.Request) -> None:
        bearer = get_mcp_bearer_token()
        if bearer:
            request.headers["Authorization"] = f"Bearer {bearer}"
        # Also inject X-User-Token if available
        user_token = get_user_token()
        if user_token:
            request.headers["X-User-Token"] = user_token
        # Propagate XCV for end-to-end traceability
        xcv = get_current_xcv()
        if xcv:
            request.headers["X-XCV"] = xcv

    client = httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(300.0, read=300.0),
        event_hooks={"request": [_inject_auth_headers]},
    )
    return client


def _header_provider(_context: dict[str, Any]) -> dict[str, str]:
    """Provide auth headers for MCP tool calls.

    Called by MCPStreamableHTTPTool during call_tool() — supplements
    the http_client event hook for tool-call-time headers.
    """
    headers: dict[str, str] = {}

    # Bearer token for MCP server auth
    bearer = get_mcp_bearer_token()
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"

    # User token for SQL passthrough
    user_token = get_user_token()
    if user_token:
        headers["X-User-Token"] = user_token

    # Propagate XCV for end-to-end traceability
    xcv = get_current_xcv()
    if xcv:
        headers["X-XCV"] = xcv

    return headers


def create_mcp_tool(
    name: str,
    allowed_tools: list[str] | None = None,
    url: str | None = None,
) -> MCPStreamableHTTPTool:
    """Create an MCPStreamableHTTPTool connected to the RATIO MCP server.

    Args:
        name: Unique name for this MCP tool instance.
        allowed_tools: Optional list of MCP tool names to expose. None = all tools.
        url: Override MCP server URL. Defaults to MCP_SERVER_URL env var.

    Returns:
        Configured MCPStreamableHTTPTool instance.
    """
    server_url = url or MCP_SERVER_URL

    # Create authenticated HTTP client that injects bearer on ALL requests
    # (including the initial MCP initialize handshake)
    http_client = _create_authenticated_http_client()

    kwargs: dict = {
        "name": name,
        "url": server_url,
        "load_prompts": False,
        "header_provider": _header_provider,
        "http_client": http_client,
    }

    if allowed_tools:
        kwargs["allowed_tools"] = allowed_tools

    tool = MCPStreamableHTTPTool(**kwargs)
    logger.info("Created MCP tool '%s' → %s (allowed: %s)", name, server_url, allowed_tools or "ALL")
    return tool


def create_filtered_mcp_tool(agent_name: str, tool_names: list[str]) -> MCPStreamableHTTPTool:
    """Create an MCP tool filtered to specific tool names for an agent.

    Args:
        agent_name: Agent name (used in MCP tool name for debugging).
        tool_names: List of MCP tool names this agent can access.

    Returns:
        MCPStreamableHTTPTool filtered to the specified tools.
    """
    return create_mcp_tool(
        name=f"ratio-mcp-{agent_name}",
        allowed_tools=tool_names if tool_names else None,
    )
