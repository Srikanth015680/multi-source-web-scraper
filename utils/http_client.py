from __future__ import annotations

import logging
import time
from typing import Callable

import requests

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; ScrapingAssignmentBot/1.0; educational project)"
)

RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class HttpClient:
    """HTTP client with timeout, retries, backoff, and rate limiting."""

    def __init__(
        self,
        timeout: float = 10.0,
        max_attempts: int = 3,
        backoff_factor: float = 1.0,
        min_delay: float = 0.3,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be greater than 0")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if backoff_factor < 0:
            raise ValueError("backoff_factor cannot be negative")
        if min_delay < 0:
            raise ValueError("min_delay cannot be negative")

        self.timeout = timeout
        self.max_attempts = max_attempts
        self.backoff_factor = backoff_factor
        self.min_delay = min_delay
        self._sleep = sleep
        self._clock = clock
        self._last_request_at: float | None = None

        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": DEFAULT_USER_AGENT})

    def get(self, url: str) -> str | None:
        for attempt in range(1, self.max_attempts + 1):
            self._throttle()

            logger.info(
                "Requesting %s (attempt %d/%d)",
                url,
                attempt,
                self.max_attempts,
            )

            try:
                response = self.session.get(url, timeout=self.timeout)
            except (requests.Timeout, requests.ConnectionError) as exc:
                logger.warning("Network error for %s: %s", url, exc)
            except requests.RequestException as exc:
                logger.error("Request failed for %s: %s", url, exc)
                return None
            else:
                if response.ok:
                    return response.text

                if response.status_code not in RETRYABLE_STATUS_CODES:
                    logger.error(
                        "HTTP %d for %s",
                        response.status_code,
                        url,
                    )
                    return None

                logger.warning(
                    "HTTP %d for %s; retrying",
                    response.status_code,
                    url,
                )

            if attempt < self.max_attempts:
                delay = self.backoff_factor * (2 ** (attempt - 1))
                logger.info("Retrying in %.1fs", delay)
                self._sleep(delay)

        logger.error(
            "Giving up on %s after %d attempts",
            url,
            self.max_attempts,
        )
        return None

    def _throttle(self) -> None:
        if self._last_request_at is not None:
            elapsed = self._clock() - self._last_request_at
            wait = self.min_delay - elapsed

            if wait > 0:
                self._sleep(wait)

        self._last_request_at = self._clock()