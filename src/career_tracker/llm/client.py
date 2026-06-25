"""OpenAI-compatible LLM client.

Works with OpenAI, Azure OpenAI, Ollama, LM Studio, vLLM, or any
OpenAI-compatible API. Configured via environment variables.
"""

from __future__ import annotations

from functools import lru_cache

import structlog
from langchain_openai import ChatOpenAI

from career_tracker.config import get_settings

logger = structlog.get_logger(__name__)


from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from typing import Any

class TokenUsageCallbackHandler(BaseCallbackHandler):
    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        try:
            token_usage = {}
            if response.llm_output and "token_usage" in response.llm_output:
                token_usage = response.llm_output["token_usage"]
            elif response.generations:
                try:
                    first_gen = response.generations[0][0]
                    if hasattr(first_gen, "message"):
                        msg = first_gen.message
                        if hasattr(msg, "usage_metadata") and msg.usage_metadata:
                            token_usage = {
                                "prompt_tokens": msg.usage_metadata.get("input_tokens", 0),
                                "completion_tokens": msg.usage_metadata.get("output_tokens", 0),
                                "total_tokens": msg.usage_metadata.get("total_tokens", 0),
                            }
                        elif hasattr(msg, "response_metadata") and msg.response_metadata:
                            token_usage = msg.response_metadata.get("token_usage", {})
                except Exception:
                    pass

            if not token_usage:
                return
                
            prompt_tokens = token_usage.get("prompt_tokens", 0)
            completion_tokens = token_usage.get("completion_tokens", 0)
            total_tokens = token_usage.get("total_tokens", 0)
            
            if total_tokens == 0:
                total_tokens = prompt_tokens + completion_tokens
            
            # Simple cost estimation based on gpt-4o-mini
            # $0.150 / 1M input tokens, $0.600 / 1M output tokens
            cost = (prompt_tokens / 1_000_000 * 0.150) + (completion_tokens / 1_000_000 * 0.600)
            
            def _log():
                try:
                    from career_tracker.db.repositories.event_repo import EventRepository
                    EventRepository().log(
                        event_type="llm_api_usage",
                        entity_type="llm",
                        entity_id="usage",
                        data={
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": total_tokens,
                            "cost": cost
                        }
                    )
                except Exception:
                    pass
                    
            import threading
            threading.Thread(target=_log, daemon=True).start()
        except Exception as e:
            logger.warning("token_usage_tracking_failed", error=str(e))


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    """Return a cached ChatOpenAI instance configured from settings.

    The client supports structured output via ``.with_structured_output()``
    and can be used directly in LangGraph nodes.
    """
    settings = get_settings()
    
    try:
        from langchain.globals import set_llm_cache
        from langchain_community.cache import SQLiteCache
        cache_path = settings.resolve_path("data/llm_cache.db")
        set_llm_cache(SQLiteCache(database_path=str(cache_path)))
    except ImportError:
        logger.warning("langchain_community not installed, llm caching disabled")

    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        api_key=settings.openai_api_key or "not-set",
        base_url=settings.openai_api_base,
        max_retries=2,
        request_timeout=300,
        callbacks=[TokenUsageCallbackHandler()],
    )

    logger.info(
        "llm.initialized",
        model=settings.llm_model,
        base_url=settings.openai_api_base,
        temperature=settings.llm_temperature,
    )
    return llm


def get_structured_llm(schema: type) -> ChatOpenAI:
    """Return an LLM bound to produce structured output matching a Pydantic schema.

    Args:
        schema: A Pydantic model class. The LLM will be constrained to
                produce JSON matching this schema.

    Usage::

        from career_tracker.models import EmailClassification
        llm = get_structured_llm(EmailClassification)
        result = llm.invoke("Classify this email...")
        # result is an EmailClassification instance
    """
    return get_llm().with_structured_output(schema, method="json_mode")
