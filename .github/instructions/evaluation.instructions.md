---
applyTo: Code/Servers/eval/**
---

# Evaluation Service Instructions

## Service Context
- FastAPI evaluation sidecar at `Code/Servers/eval/` running on port 8011
- Evaluates LLM response quality using multiple metrics
- Depends on `agents` service (health check dependency in docker-compose)

## Architecture
- `adapters/` — External service adapters (Azure AI, DeepEval, etc.)
- `api/` — FastAPI routes (`app.py`, route modules)
- `core/` — Business logic (evaluation engine, metric computation)
- `models/` — Pydantic schemas (request/response models)
- `tests/` — Service tests (highest test coverage target)
- `infra/` — Service-specific Azure deployment (Bicep, scripts)
- `scripts/` — Deployment automation scripts

## Evaluation Metrics

Two categories of metrics:

### AI Quality Metrics (via Azure AI Evaluation SDK)
- Fluency, Coherence, Relevance, Groundedness
- Require Azure OpenAI connection for judge model

### NLP Metrics (local, no LLM needed)
- ROUGE (1, 2, L), BLEU, METEOR
- Run locally without external dependencies

## Patterns

### Adapter Pattern
External service calls go through adapters — never call Azure AI SDK directly from routes:
```python
# ✅ adapters/azure_eval_adapter.py
class AzureEvalAdapter:
    async def evaluate(self, input: EvalInput) -> EvalResult: ...

# ✅ api/routes.py
@router.post("/evaluate")
async def evaluate(request: EvalRequest, adapter: AzureEvalAdapter = Depends()):
    return await adapter.evaluate(request)
```

### Testing
- Tests in `tests/` — this service has the best test coverage, maintain it
- Mock external adapters in tests
- Test both success and error paths for each metric type

## Import Rules
- Service-local: `from api.app import app` ✅
- Shared: `from Code.Shared.evaluation.interfaces import BaseEvaluator` ✅
- This service has its own `infra/` and `scripts/` for independent deployment
