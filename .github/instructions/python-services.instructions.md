---
applyTo: Code/Servers/**/*.py
---

# Python Service Instructions

## General Rules

All Python services in `Code/Servers/` follow these standards:

### Async by Default
- All route handlers: `async def`
- All I/O operations: `await` (httpx, aiohttp, kusto, cosmos)
- Sync SDKs: `await run_in_threadpool(sync_call)`
- Sleep: `await asyncio.sleep(n)` — never `time.sleep(n)`
- HTTP: `httpx.AsyncClient` — never `requests`

### FastAPI Patterns
- `response_model=` on every route decorator
- `status_code=` explicit on create/update routes
- `HTTPException` for all error responses (never 200 with error body)
- `Depends()` for dependency injection (auth, validation, shared resources)
- `GET /health` → `{"status": "ok", "service": "<name>", "version": "..."}` on every service

### Pydantic v2
- All request/response bodies: `BaseModel` subclass
- Field constraints: `Field(min_length=1, max_length=4096, ge=0, le=100)`
- Config: `BaseSettings` subclass with `env_prefix`
- Never read `os.environ` directly

### Error Handling
```python
# ✅ Correct
raise HTTPException(status_code=404, detail="Resource not found")

# ❌ Wrong
return {"error": "not found"}  # 200 status with error body
```

### Logging
```python
import logging
logger = logging.getLogger(__name__)

logger.info("Processing request %s", request_id)
logger.exception("Failed to process")  # includes traceback
```

Never use `print()`.

### Imports
- Within service: absolute from service root (`from api.app import app`)
- Shared code: `from Code.Shared.config.settings import ...` with `try/except ImportError`
- Cross-service: never import directly between services — use HTTP calls

### Testing
- `pytest` + `@pytest.mark.asyncio`
- `httpx.AsyncClient` with `ASGITransport` for route tests
- Mock all external services (Azure, Kusto, OpenAI)
- Tests in `tests/` directory within the service
- Naming: `test_<module>.py` → `test_<function>_<scenario>()`
