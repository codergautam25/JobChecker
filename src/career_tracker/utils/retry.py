"""Retry and backoff utilities.

Provides pre-configured retry decorators using tenacity for common
failure patterns in the application.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar

import structlog
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_random_exponential,
    before_sleep_log,
)

logger = structlog.get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def with_retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 30.0,
    retry_on: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """Decorator: retry a function with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts.
        min_wait: Minimum wait time between retries (seconds).
        max_wait: Maximum wait time between retries (seconds).
        retry_on: Tuple of exception types to retry on.

    Usage::

        @with_retry(max_attempts=3, retry_on=(TimeoutError, ConnectionError))
        def call_api():
            ...
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            retrier = retry(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
                retry=retry_if_exception_type(retry_on),
                reraise=True,
            )
            try:
                return retrier(func)(*args, **kwargs)
            except RetryError as e:
                logger.error(
                    "retry.exhausted",
                    function=func.__name__,
                    max_attempts=max_attempts,
                    error=str(e.last_attempt.exception()) if e.last_attempt.exception() else "",
                )
                raise

        return wrapper  # type: ignore[return-value]

    return decorator


def with_llm_retry(func: F) -> F:
    """Decorator: retry LLM calls with jittered exponential backoff.

    Pre-configured for common LLM API failure modes:
    - Rate limits
    - Timeouts
    - Transient server errors
    """
    return with_retry(
        max_attempts=3,
        min_wait=2.0,
        max_wait=60.0,
        retry_on=(Exception,),  # Broad catch — LLM clients raise varied exceptions
    )(func)


def with_gmail_retry(func: F) -> F:
    """Decorator: retry Gmail API calls with exponential backoff.

    Pre-configured for Gmail API rate limit handling.
    """
    return with_retry(
        max_attempts=3,
        min_wait=1.0,
        max_wait=30.0,
        retry_on=(Exception,),
    )(func)
