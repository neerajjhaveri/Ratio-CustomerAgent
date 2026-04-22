# Moved from src/llm.py
import os, json, asyncio, random, inspect, logging
from dotenv import load_dotenv
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from helper.auth import get_token_provider

logger = logging.getLogger("llm_auth"); logger.setLevel(logging.INFO)
load_dotenv(override=True)

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
AZURE_OPENAI_GPT_MODEL_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_GPT_MODEL_DEPLOYMENT_NAME")
AZURE_OPENAI_GPT_MODEL_NAME = os.getenv("AZURE_OPENAI_GPT_MODEL_NAME")
AZURE_OPENAI_REASONING_MODEL_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_REASONING_MODEL_DEPLOYMENT_NAME")
AZURE_OPENAI_REASONING_MODEL_NAME = os.getenv("AZURE_OPENAI_REASONING_MODEL_NAME")
MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "5"))
BASE_DELAY = float(os.getenv("LLM_BASE_DELAY", "1.5"))
MAX_DELAY = float(os.getenv("LLM_MAX_DELAY", "20"))

credential = get_token_provider("https://cognitiveservices.azure.com/.default")


def _is_transient_error(exc: Exception) -> bool:
    msg = str(exc).lower(); needles = ["rate limit", "too many requests", "quota", "overloaded", "429", "server is busy", "temporarily unavailable", "retry later"]
    return any(n in msg for n in needles)

class RetryAzureClient:
    def __init__(self, inner, max_retries=MAX_RETRIES, base_delay=BASE_DELAY, max_delay=MAX_DELAY, factor=2.0, jitter=0.25):
        self._inner = inner; self._cfg = dict(max_retries=max_retries, base=base_delay, max=max_delay, factor=factor, jitter=jitter)
    def __getattr__(self, name):
        target = getattr(self._inner, name)
        if not callable(target): return target
        async def async_wrapper(*args, **kwargs):
            for attempt in range(self._cfg["max_retries"]):
                try:
                    result = target(*args, **kwargs)
                    if inspect.isawaitable(result): result = await result
                    return result
                except Exception as e:
                    if not _is_transient_error(e) or attempt == self._cfg["max_retries"] - 1: raise
                    delay = min(self._cfg["base"] * (self._cfg["factor"] ** attempt), self._cfg["max"])
                    delay = delay * (0.85 + random.random() * self._cfg["jitter"])
                    print(f"[RetryAzureClient] Transient error ({e}); retry {attempt+1}/{self._cfg['max_retries']} in {delay:.2f}s")
                    await asyncio.sleep(delay)
            raise RuntimeError("Exhausted retries without raising inside loop.")
        return async_wrapper

def _wrap_with_retry(client): return RetryAzureClient(client)

def get_reasoning_model_client():
    client = AzureOpenAIChatCompletionClient(azure_endpoint=AZURE_OPENAI_ENDPOINT, api_version=AZURE_OPENAI_API_VERSION, model=AZURE_OPENAI_REASONING_MODEL_NAME, azure_deployment=AZURE_OPENAI_REASONING_MODEL_DEPLOYMENT_NAME, azure_ad_token_provider=credential)
    return _wrap_with_retry(client)

def get_gpt_model_client():
    client = AzureOpenAIChatCompletionClient(azure_endpoint=AZURE_OPENAI_ENDPOINT, api_version=AZURE_OPENAI_API_VERSION, model=AZURE_OPENAI_GPT_MODEL_NAME, azure_deployment=AZURE_OPENAI_GPT_MODEL_DEPLOYMENT_NAME, azure_ad_token_provider=credential)
    return _wrap_with_retry(client)

__all__ = ["get_reasoning_model_client", "get_gpt_model_client", "RetryAzureClient"]
