"""Arch Agent retry, circuit breaker, and exception types.

Every external call uses exponential backoff with jitter.
Agent failures are contained — never cascade.
"""

import asyncio
import functools
import random
from typing import Callable


def arch_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    exceptions: tuple = (Exception,),
):
    """Exponential backoff retry with jitter for all external calls."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts - 1:
                        raise ArchRetryExhaustedError(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        ) from e
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    await asyncio.sleep(delay)

        return wrapper

    return decorator


class ArchRetryExhaustedError(Exception):
    """Raised when all retry attempts are exhausted. Triggers Sentinel alert."""


class ArchBudgetExceededError(Exception):
    """Raised when agent token budget is exceeded. Triggers model downgrade."""


class ArchConstitutionalViolationError(Exception):
    """Raised when an action would violate a Prime Directive. Cannot be retried."""


class ArchFinancialGateError(Exception):
    """Raised when financial gate check fails. Triggers Treasurer escalation."""


class ArchCircuitBreakerTrippedError(Exception):
    """Raised when agent circuit breaker is tripped."""
