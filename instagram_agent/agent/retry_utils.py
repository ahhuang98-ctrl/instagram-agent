import logging

import requests
from tenacity import before_sleep_log, retry, retry_if_exception, stop_after_attempt, wait_exponential


def is_transient_requests_error(exc: BaseException) -> bool:
    """True for errors worth retrying: network issues, rate limits, server errors."""
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return False


def http_retry(logger: logging.Logger):
    """Tenacity retry decorator: 3 attempts, 2s→4s→8s backoff, transient errors only."""
    return retry(
        retry=retry_if_exception(is_transient_requests_error),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
