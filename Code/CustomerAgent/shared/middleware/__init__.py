"""Shared Agent Framework middleware for all RatioAI agent services.

Provides cross-cutting concerns as middleware classes that can be imported
by any agent service (ratio_agents, ratio_customer_health, etc.):

* ``LoggingAgentMiddleware`` — structured logging with timing + App Insights
* ``ToolTimingMiddleware`` — function call logging with duration
* ``SecurityMiddleware`` — blocks sensitive content before LLM calls
* ``PromptInjectionMiddleware`` — screens prompts through the PI container
* ``ErrorHandlingMiddleware`` — graceful tool failure handling
* ``EvalMiddleware`` — post-execution quality scoring via ratio_eval_sidecar
* ``ContentFilterMiddleware`` — placeholder for Azure Content Safety

Usage::

    from Code.Shared.middleware import build_default_middleware

    middleware = build_default_middleware()
    agent = Agent(client=client, ..., middleware=middleware)
"""

from Code.Shared.middleware.logging_middleware import (
    LoggingAgentMiddleware,
    ToolTimingMiddleware,
)
from Code.Shared.middleware.security_middleware import SecurityMiddleware
from Code.Shared.middleware.prompt_injection_middleware import PromptInjectionMiddleware
from Code.Shared.middleware.error_middleware import ErrorHandlingMiddleware
from Code.Shared.middleware.eval_middleware import EvalMiddleware, ContentFilterMiddleware

__all__ = [
    "LoggingAgentMiddleware",
    "ToolTimingMiddleware",
    "SecurityMiddleware",
    "PromptInjectionMiddleware",
    "ErrorHandlingMiddleware",
    "EvalMiddleware",
    "ContentFilterMiddleware",
    "build_default_middleware",
]


def build_default_middleware(
    *,
    enable_eval: bool = False,
    eval_sidecar_url: str = "http://127.0.0.1:8011",
    enable_prompt_injection: bool = False,
    pi_service_url: str = "http://127.0.0.1:8000",
) -> list:
    """Build the default middleware stack for all agents.

    Execution order (outermost first):
    1. Security — block blocked terms / PII before anything else
    2. Logging — time the full request lifecycle
    3. Tool timing — log individual tool calls
    4. Error handling — catch tool exceptions gracefully
    5. Prompt injection — screen prompts through PI container (chat-level)
    6. Eval — post-execution quality scoring (non-blocking)
    """
    stack: list = [
        SecurityMiddleware(),
        LoggingAgentMiddleware(),
        ToolTimingMiddleware(),
        ErrorHandlingMiddleware(),
    ]
    if enable_prompt_injection:
        stack.append(PromptInjectionMiddleware(pi_service_url=pi_service_url))
    if enable_eval:
        stack.append(EvalMiddleware(enabled=True, eval_sidecar_url=eval_sidecar_url))
    return stack
