"""Per-call tracking for all MCP tool executions (sync and async).

Every tool invocation is recorded with caller info, timing, and outcome.
Records are pruned after CALL_TTL_SECONDS (default 600s).
"""
from __future__ import annotations
import asyncio, uuid, time, os
from typing import Any, Dict, Optional
from core.mcp_app import logger

CallRecord = Dict[str, Any]
_calls: Dict[str, CallRecord] = {}
_tasks: Dict[str, asyncio.Task] = {}
_lock = asyncio.Lock()
_CALL_TTL = int(os.getenv("CALL_TTL_SECONDS", "600"))

def _now() -> float:
    return time.time()

async def _prune() -> None:
    now = _now()
    async with _lock:
        to_remove = [cid for cid, rec in _calls.items() if rec.get("finished_at") and (now - rec["finished_at"]) > _CALL_TTL]
        for cid in to_remove:
            _calls.pop(cid, None)
            _tasks.pop(cid, None)
    if to_remove:
        logger.debug("Pruned %d call records", len(to_remove))

async def start_call(
    tool_name: str,
    params: Dict[str, Any],
    *,
    caller_ip: str | None = None,
    caller_sub: str | None = None,
    mode: str = "sync",
) -> CallRecord:
    """Begin tracking a tool call.

    Args:
        tool_name: Name of the tool being invoked.
        params: Parameters passed to the tool.
        caller_ip: Client IP address (from request).
        caller_sub: Authenticated subject/client ID (from auth claims).
        mode: "sync" or "async".
    """
    cid = uuid.uuid4().hex
    record: CallRecord = {
        "id": cid,
        "tool_name": tool_name,
        "params": params,
        "caller_ip": caller_ip,
        "caller_sub": caller_sub,
        "mode": mode,
        "status": "running",
        "started_at": _now(),
        "finished_at": None,
        "duration_ms": None,
        "result_summary": None,
        "error": None,
    }
    async with _lock:
        _calls[cid] = record
    logger.info(
        "CALL_START call_id=%s tool=%s mode=%s caller_ip=%s caller_sub=%s",
        cid, tool_name, mode, caller_ip, caller_sub,
    )
    return record

async def finish_call(cid: str, result: Any = None, error: Optional[str] = None) -> None:
    """Mark a call as finished with result or error."""
    async with _lock:
        rec = _calls.get(cid)
        if not rec:
            return
        rec["finished_at"] = _now()
        rec["duration_ms"] = round((rec["finished_at"] - rec["started_at"]) * 1000, 1)
        if error:
            rec["status"] = "failed"
            rec["error"] = error
        else:
            rec["status"] = "succeeded"
            # Store a brief summary, not the full result (to avoid memory bloat)
            if isinstance(result, str):
                rec["result_summary"] = result[:200] if len(result) > 200 else result
            else:
                rec["result_summary"] = str(result)[:200] if result else None
    logger.info(
        "CALL_END call_id=%s tool=%s status=%s duration_ms=%s",
        cid, rec["tool_name"], rec["status"], rec.get("duration_ms"),
    )
    await _prune()

async def cancel_call(cid: str) -> bool:
    async with _lock:
        rec = _calls.get(cid)
        task = _tasks.get(cid)
    if not rec:
        return False
    if rec.get("status") != "running":
        return True
    if task and not task.done():
        task.cancel()
        try:
            await task
        except Exception:
            pass
    async with _lock:
        rec["status"] = "cancelled"
        rec["finished_at"] = _now()
    logger.debug("Cancelled call %s", cid)
    return True

async def list_calls() -> list[CallRecord]:
    await _prune()
    async with _lock:
        return list(_calls.values())

def register_task(cid: str, task: asyncio.Task) -> None:
    _tasks[cid] = task

__all__ = ["start_call", "finish_call", "cancel_call", "list_calls", "register_task"]
