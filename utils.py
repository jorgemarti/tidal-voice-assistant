"""
Utility functions and decorators for Tidal Voice Assistant.
"""

import time
import functools
from typing import TypeVar, Callable, Any, Optional
from config import (
    RETRY_MAX_ATTEMPTS,
    RETRY_DELAY_SECONDS,
    RETRY_BACKOFF_MULTIPLIER,
    setup_logging
)

logger = setup_logging(__name__)

F = TypeVar('F', bound=Callable[..., Any])


def with_retry(
    max_attempts: Optional[int] = None,
    delay: Optional[float] = None,
    backoff: Optional[float] = None,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
) -> Callable[[F], F]:
    """
    Decorator that retries a function on failure with exponential backoff.

    Args:
        max_attempts: Maximum retry attempts (default: from config)
        delay: Initial delay between retries in seconds (default: from config)
        backoff: Backoff multiplier for delay (default: from config)
        exceptions: Tuple of exceptions to catch and retry on
        on_retry: Optional callback called on each retry with (exception, attempt)

    Returns:
        Decorated function

    Example:
        @with_retry(max_attempts=3, delay=1.0)
        def flaky_function():
            # May fail sometimes
            pass

        @with_retry(exceptions=(ConnectionError, TimeoutError))
        def network_call():
            # Only retry on network errors
            pass
    """
    max_attempts = max_attempts or RETRY_MAX_ATTEMPTS
    delay = delay or RETRY_DELAY_SECONDS
    backoff = backoff or RETRY_BACKOFF_MULTIPLIER

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        logger.debug(
                            f"{func.__name__} failed (attempt {attempt}/{max_attempts}): {e}. "
                            f"Retrying in {current_delay}s..."
                        )
                        if on_retry:
                            on_retry(e, attempt)
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )

            # Re-raise the last exception if all attempts failed
            if last_exception:
                raise last_exception

        return wrapper  # type: ignore
    return decorator


def retry_on_failure(func: F) -> F:
    """
    Simple retry decorator using default config values.

    Use this for quick decoration without customization:

        @retry_on_failure
        def my_function():
            pass
    """
    return with_retry()(func)
