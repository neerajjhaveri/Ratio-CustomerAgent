# Skill: Add a New FastAPI Endpoint

## When to Use

Use this skill when asked to add a new API endpoint to any FastAPI service (agents, eval, or a new service).

## Steps

### 1. Define the Pydantic schemas

Create or update the models file in the target service:

```python
# models/<feature>.py or schemas.py
from pydantic import BaseModel, Field

class <Feature>Request(BaseModel):
    """Request body for <feature> endpoint."""
    input_data: str = Field(..., min_length=1, max_length=4096, description="...")
    options: dict | None = None

class <Feature>Response(BaseModel):
    """Response body for <feature> endpoint."""
    result: str
    metadata: dict | None = None
```

### 2. Create the route

Add the endpoint to the appropriate router file:

```python
# api/routes_<feature>.py
import logging
from fastapi import APIRouter, HTTPException, status

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/<feature>", tags=["<Feature>"])


@router.post(
    "/",
    response_model=<Feature>Response,
    status_code=status.HTTP_200_OK,
    summary="<One-line summary>",
    description="<Detailed description>",
)
async def <feature>_endpoint(request: <Feature>Request) -> <Feature>Response:
    """<Feature> endpoint implementation."""
    logger.info("Processing <feature> request")
    try:
        result = await process(request.input_data)
        return <Feature>Response(result=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Unexpected error in <feature>")
        raise HTTPException(status_code=500, detail="Internal server error")
```

### 3. Register the router

In the service's main app file (e.g., `app_kernel.py` or `api/app.py`):

```python
from api.routes_<feature> import router as <feature>_router
app.include_router(<feature>_router)
```

### 4. Add tests

```python
# tests/test_<feature>.py
import pytest
from httpx import AsyncClient, ASGITransport

@pytest.mark.asyncio
async def test_<feature>_success():
    from api.app import app  # or app_kernel:app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/<feature>/", json={"input_data": "test"})
        assert resp.status_code == 200
        assert "result" in resp.json()

@pytest.mark.asyncio
async def test_<feature>_validation_error():
    from api.app import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/<feature>/", json={"input_data": ""})
        assert resp.status_code == 422  # Pydantic validation
```

## Rules

- **Always define `response_model`** on route decorators
- **Always set explicit `status_code`** for create/update operations
- **Use Pydantic v2 `BaseModel`** for all request/response schemas
- **Async by default** — use `async def` for all route handlers
- **Structured logging** — `logger.info/error/exception()`, never `print()`
- **HTTPException for errors** — never return error bodies with 200 status
- **Guard inputs** — use Pydantic `Field()` constraints (min_length, max_length, ge, le, pattern)
- **OpenAPI docs** — set `summary`, `description`, and `tags` on routes
