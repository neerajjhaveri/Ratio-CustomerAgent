"""Simple in-memory async job manager for MCP tools.
Not production-grade (no persistence, no pruning) but sufficient for short-lived async tasks (<120s).
"""
from __future__ import annotations
import asyncio, time, uuid, inspect, os
from typing import Any, Callable, Dict, Optional
from core.mcp_app import logger

JobRecord = Dict[str, Any]
_jobs: Dict[str, JobRecord] = {}
_tasks: Dict[str, asyncio.Task] = {}
_lock = asyncio.Lock()
_DEFAULT_TTL = int(os.getenv("JOB_TTL_SECONDS", "900"))  # seconds

# Status lifecycle: pending -> running -> succeeded|failed|cancelled

def _now() -> float:
    return time.time()

def _is_terminal(status: str) -> bool:
    return status in ("succeeded", "failed", "cancelled")

async def _prune_jobs(force: bool = False) -> int:
    """Remove terminal jobs older than TTL to keep memory bounded."""
    ttl = _DEFAULT_TTL
    now = _now()
    removed = 0
    async with _lock:
        to_delete = []
        for jid, rec in _jobs.items():
            fin = rec.get("finished_at") or rec.get("started_at") or 0
            if _is_terminal(rec["status"]) and (force or (now - fin) > ttl):
                to_delete.append(jid)
        for jid in to_delete:
            _jobs.pop(jid, None)
            _tasks.pop(jid, None)
            removed += 1
    if removed:
        logger.debug("Pruned %d expired jobs (ttl=%ds)", removed, ttl)
    return removed

async def create_job(tool_name: str, params: Dict[str, Any]) -> JobRecord:
    job_id = uuid.uuid4().hex
    record: JobRecord = {
        "id": job_id,
        "tool_name": tool_name,
        "params": params,
        "status": "pending",
        "result": None,
        "error": None,
        "started_at": None,
        "finished_at": None,
    }
    async with _lock:
        _jobs[job_id] = record
    # Opportunistic prune
    await _prune_jobs()
    return record

async def get_job(job_id: str) -> Optional[JobRecord]:
    async with _lock:
        return _jobs.get(job_id)

async def list_jobs() -> list[JobRecord]:
    await _prune_jobs()
    async with _lock:
        return list(_jobs.values())

async def _run_tool(job: JobRecord, tool_callable: Callable[..., Any], timeout: float = 115.0) -> None:
    job_id = job["id"]
    try:
        job["status"] = "running"
        job["started_at"] = _now()
        if inspect.iscoroutinefunction(tool_callable):
            coro = tool_callable(**job["params"])
        else:
            # Run sync call in thread to avoid blocking loop
            loop = asyncio.get_running_loop()
            coro = loop.run_in_executor(None, lambda: tool_callable(**job["params"]))
        result = await asyncio.wait_for(coro, timeout=timeout)
        job["result"] = result
        job["status"] = "succeeded"
    except asyncio.TimeoutError:
        job["error"] = f"Timed out after {timeout}s"
        job["status"] = "failed"
    except Exception as e:  # noqa: BLE001
        job["error"] = str(e)
        job["status"] = "failed"
        logger.error("Async job %s failed: %s", job_id, e, exc_info=True)
    finally:
        if job["status"] != "cancelled":
            job["finished_at"] = _now()
        await _prune_jobs()

async def schedule_tool_job(tool_name: str, tool_callable: Callable[..., Any], params: Dict[str, Any], timeout: float = 115.0) -> JobRecord:
    job = await create_job(tool_name, params)
    # Fire-and-forget background execution
    task = asyncio.create_task(_run_tool(job, tool_callable, timeout=timeout))
    async with _lock:
        _tasks[job["id"]] = task
    return job

async def cancel_job(job_id: str) -> bool:
    async with _lock:
        job = _jobs.get(job_id)
        task = _tasks.get(job_id)
    if not job:
        return False
    if _is_terminal(job["status"]):
        return True  # already done
    if task and not task.done():
        task.cancel()
        try:
            await task
        except Exception:
            pass
    job["status"] = "cancelled"
    job["finished_at"] = _now()
    logger.debug("Cancelled job %s", job_id)
    return True

__all__ = ["create_job", "get_job", "list_jobs", "schedule_tool_job", "cancel_job"]
