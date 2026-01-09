"""Rate limiting utilities for YouTube API and transcript fetching."""

import time
import logging
import random
import threading
from functools import wraps
from typing import Optional, Callable, Any
from googleapiclient.errors import HttpError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
    before_sleep_log,
    RetryError
)


class RateLimiter:
    """
    Thread-safe rate limiter using token bucket algorithm.

    Implements a token bucket for smooth rate limiting across threads.
    Allows configurable requests per second with optional burst allowance.
    """

    def __init__(self, requests_per_second: float, burst_size: int, logger: logging.Logger):
        """
        Initialize the rate limiter.

        Args:
            requests_per_second: Maximum requests per second (e.g., 0.5 = 1 request per 2 seconds)
            burst_size: Maximum burst size (tokens available immediately)
            logger: Logger instance
        """
        self.logger = logger
        self.requests_per_second = requests_per_second
        self.burst_size = burst_size

        # Token bucket state
        self._tokens = float(burst_size)
        self._last_update = time.time()
        self._lock = threading.RLock()

    def _add_tokens(self):
        """Add tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self._last_update
        tokens_to_add = elapsed * self.requests_per_second
        self._tokens = min(self._tokens + tokens_to_add, self.burst_size)
        self._last_update = now

    def acquire(self, tokens: float = 1.0) -> float:
        """
        Block until tokens are available, then consume them.

        Args:
            tokens: Number of tokens to acquire (default: 1.0)

        Returns:
            Delay in seconds that was waited
        """
        with self._lock:
            start_time = time.time()

            while True:
                self._add_tokens()

                if self._tokens >= tokens:
                    self._tokens -= tokens
                    delay = time.time() - start_time
                    if delay > 0.01:  # Log significant delays
                        self.logger.debug(f"Rate limiter waited {delay:.2f}s")
                    return delay

                # Calculate wait time until enough tokens available
                deficit = tokens - self._tokens
                wait_time = deficit / self.requests_per_second

                # Release lock while sleeping
                self._lock.release()
                time.sleep(min(wait_time, 0.1))  # Sleep in small increments
                self._lock.acquire()


class YouTubeAPIRateLimiter:
    """
    Rate limiter and retry handler for YouTube Data API calls.

    Features:
    - Token bucket for smooth rate limiting
    - Exponential backoff with jitter for retries
    - Detection of 429/403 rate limit errors
    - Thread-safe for concurrent API calls
    - Integration with QuotaTracker for monitoring
    """

    def __init__(self, config, quota_tracker, logger: logging.Logger):
        """
        Initialize the YouTube API rate limiter.

        Args:
            config: Configuration object with rate_limiting settings
            quota_tracker: QuotaTracker instance for logging metrics
            logger: Logger instance
        """
        self.logger = logger
        self.quota_tracker = quota_tracker
        self.config = config

        # Extract settings
        yt_config = config.rate_limiting.youtube_api
        self.enabled = yt_config.enabled
        self.min_delay = yt_config.min_delay_seconds
        self.max_delay = yt_config.max_delay_seconds
        self.max_retries = yt_config.max_retries
        self.backoff_multiplier = yt_config.backoff_multiplier

        # Initialize token bucket
        self.rate_limiter = RateLimiter(
            requests_per_second=yt_config.requests_per_second,
            burst_size=yt_config.burst_size,
            logger=logger
        )

    def _is_rate_limit_error(self, error: Exception) -> bool:
        """
        Detect if error is a rate limit error (429 or 403 quota exceeded).

        Args:
            error: Exception to check

        Returns:
            True if this is a rate limit error, False otherwise
        """
        if isinstance(error, HttpError):
            status = error.resp.status

            # 429 = Too Many Requests
            if status == 429:
                return True

            # 403 might be quota exceeded
            if status == 403:
                try:
                    import json
                    error_content = json.loads(error.content.decode('utf-8'))
                    reason = error_content.get('error', {}).get('errors', [{}])[0].get('reason', '')
                    if reason in ['quotaExceeded', 'rateLimitExceeded', 'userRateLimitExceeded']:
                        return True
                except:
                    pass

        return False

    def _should_retry(self, exception: Exception) -> bool:
        """
        Determine if an error should trigger a retry.

        Args:
            exception: Exception to evaluate

        Returns:
            True if we should retry, False otherwise
        """
        if not isinstance(exception, HttpError):
            return False

        status = exception.resp.status

        # Retry on rate limit errors (429, 403 quota)
        if self._is_rate_limit_error(exception):
            return True

        # Retry on server errors (5xx)
        if status >= 500:
            return True

        # Don't retry on client errors (4xx except quota)
        return False

    def rate_limit_youtube_api(self, func: Callable) -> Callable:
        """
        Decorator for YouTube Data API calls.

        Applies rate limiting and exponential backoff with retry.

        Usage:
            @rate_limiter.rate_limit_youtube_api
            def api_call():
                return youtube.search().list(...).execute()

        Args:
            func: Function that makes a YouTube API call

        Returns:
            Decorated function with rate limiting
        """
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            if not self.enabled:
                return func(*args, **kwargs)

            # Apply tenacity retry decorator dynamically
            retry_decorator = retry(
                retry=retry_if_exception(self._should_retry),
                stop=stop_after_attempt(self.max_retries),
                wait=wait_exponential(
                    multiplier=self.backoff_multiplier,
                    min=self.min_delay,
                    max=self.max_delay
                ),
                before_sleep=before_sleep_log(self.logger, logging.WARNING),
                reraise=True
            )

            # Apply rate limiting first
            delay = self.rate_limiter.acquire()
            if delay > 0.01:
                self.quota_tracker.log_throttle(delay)

            # Then apply retry logic
            try:
                retried_func = retry_decorator(func)
                result = retried_func(*args, **kwargs)
                return result
            except RetryError as e:
                self.quota_tracker.log_rate_limit_error()
                raise e.last_attempt.exception()

        return wrapper


class TranscriptRateLimiter:
    """
    Rate limiter for YouTubeTranscriptApi (web scraping).

    Features:
    - Conservative delays to prevent IP blocking
    - Random jitter for human-like behavior
    - Simple retry logic without exponential backoff
    - Configuration-driven delays
    """

    def __init__(self, config, logger: logging.Logger):
        """
        Initialize the transcript rate limiter.

        Args:
            config: Configuration object with rate_limiting settings
            logger: Logger instance
        """
        self.logger = logger
        self.config = config

        # Extract settings
        ts_config = config.rate_limiting.transcript_api
        self.enabled = ts_config.enabled
        self.min_delay = ts_config.min_delay_seconds
        self.max_delay = ts_config.max_delay_seconds
        self.delay_jitter = ts_config.delay_jitter
        self.max_retries = ts_config.max_retries

        self._last_fetch_time = 0
        self._lock = threading.RLock()

    def _calculate_delay(self) -> float:
        """
        Calculate delay with jitter.

        Returns:
            Delay in seconds
        """
        # Base delay between min and max
        base_delay = (self.min_delay + self.max_delay) / 2

        # Add random jitter (±delay_jitter%)
        jitter_amount = base_delay * self.delay_jitter * random.random()
        return base_delay + jitter_amount

    def rate_limit_transcript_fetch(self, func: Callable) -> Callable:
        """
        Decorator for transcript fetching.

        Applies delays and retries for web scraping.

        Usage:
            @rate_limiter.rate_limit_transcript_fetch
            def fetch_transcript():
                return YouTubeTranscriptApi.fetch(video_id)

        Args:
            func: Function that fetches a transcript

        Returns:
            Decorated function with rate limiting
        """
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            if not self.enabled:
                return func(*args, **kwargs)

            with self._lock:
                # Calculate delay since last fetch
                now = time.time()
                time_since_last = now - self._last_fetch_time

                delay = self._calculate_delay()
                wait_time = delay - time_since_last

                if wait_time > 0:
                    self.logger.debug(f"Transcript fetch delay: {wait_time:.2f}s (jitter)")
                    time.sleep(wait_time)

                self._last_fetch_time = time.time()

            # Simple retry logic for transcript fetching
            last_error = None
            for attempt in range(1, self.max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    last_error = e

                    if attempt < self.max_retries:
                        # Simple backoff: 0.5s, 1s, 2s for retries
                        backoff_delay = self.min_delay * (2 ** (attempt - 1))
                        self.logger.warning(
                            f"Transcript fetch failed (attempt {attempt}), "
                            f"retrying in {backoff_delay:.1f}s: {str(e)[:100]}"
                        )
                        time.sleep(backoff_delay)
                    else:
                        self.logger.error(f"Transcript fetch failed after {self.max_retries} attempts: {e}")

            if last_error:
                raise last_error

            return None

        return wrapper
