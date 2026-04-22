"""A2A JSON-RPC request/response schemas.

Mirrors the Google A2A protocol message format used in A2AAnalyticsAgent.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class A2AMessagePart(BaseModel):
    type: str = Field("text", description="Type of the message part")
    text: str


class A2AMessage(BaseModel):
    role: str = Field("user")
    parts: List[A2AMessagePart]


class A2ARequestParams(BaseModel):
    id: str
    sessionId: Optional[str] = None
    acceptedOutputModes: List[str] = ["text"]
    message: A2AMessage


class A2AJsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Any
    method: str
    params: A2ARequestParams


class A2AStreamChunk(BaseModel):
    jsonrpc: str = "2.0"
    id: Any
    method: str = "message/stream"
    params: Dict[str, Any]


class A2AJsonRpcResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Any
    result: Dict[str, Any]
