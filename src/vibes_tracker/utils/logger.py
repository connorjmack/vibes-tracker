"""Logging configuration for vibes-tracker pipeline."""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional


def setup_logger(
    name: str = "vibes-tracker",
    log_file: Optional[str] = None,
    level: int = logging.INFO,
    log_to_console: bool = True,
    log_to_file: bool = True
) -> logging.Logger:
    """
    Set up a logger with both console and file handlers.

    Args:
        name: Logger name
        log_file: Path to log file. If None, uses 'logs/vibes-tracker.log'
        level: Logging level (logging.DEBUG, logging.INFO, etc.)
        log_to_console: Whether to log to console
        log_to_file: Whether to log to file

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # File handler with rotation
    if log_to_file:
        if log_file is None:
            # Default log file location
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            log_file = log_dir / "vibes-tracker.log"

        # Create log directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Rotating file handler (max 10MB per file, keep 5 backups)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "vibes-tracker") -> logging.Logger:
    """
    Get an existing logger or create a new one with default settings.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger = setup_logger(name)
    return logger


class QuotaExceededException(Exception):
    """Exception raised when API quota is exceeded."""
    pass


class QuotaTracker:
    """Helper class to track API quota usage and rate limiting metrics."""

    def __init__(self, logger: logging.Logger, daily_limit: int = 10000):
        self.logger = logger
        self.daily_limit = daily_limit
        self.youtube_units = 0
        self.gemini_calls = 0

        # Rate limiting metrics
        self.api_calls_throttled = 0
        self.retry_attempts = 0
        self.rate_limit_errors = 0

    def log_youtube_api_call(self, units: int, operation: str):
        """Log a YouTube API call and track quota."""
        self.youtube_units += units
        self.logger.debug(f"YouTube API: {operation} ({units} units, total: {self.youtube_units})")

        self.check_quota()

    def check_quota(self):
        """Check if quota has been exceeded and raise exception if so."""
        if self.youtube_units >= self.daily_limit:
            self.logger.error(f"CRITICAL: YouTube API quota exceeded ({self.youtube_units} >= {self.daily_limit})")
            raise QuotaExceededException(f"YouTube API quota limit reached: {self.youtube_units}")

    def log_gemini_api_call(self, operation: str):
        """Log a Gemini API call."""
        self.gemini_calls += 1
        self.logger.debug(f"Gemini API: {operation} (total calls: {self.gemini_calls})")

    def log_throttle(self, delay_seconds: float):
        """Log when rate limiter delays a request."""
        self.api_calls_throttled += 1
        self.logger.debug(f"Rate limiter throttled request: {delay_seconds:.2f}s delay")

    def log_retry(self, attempt: int, error_type: str):
        """Log retry attempts."""
        self.retry_attempts += 1
        self.logger.warning(f"Retry attempt {attempt} due to {error_type}")

    def log_rate_limit_error(self):
        """Log rate limit errors."""
        self.rate_limit_errors += 1
        self.logger.error("Rate limit error encountered")

    def log_summary(self):
        """Log a summary of API usage and rate limiting metrics."""
        self.logger.info("="*60)
        self.logger.info("API Usage Summary:")
        self.logger.info(f"  YouTube: {self.youtube_units} units")
        self.logger.info(f"  Gemini: {self.gemini_calls} calls")

        # Rate limiting metrics
        if self.api_calls_throttled > 0 or self.retry_attempts > 0 or self.rate_limit_errors > 0:
            self.logger.info("Rate Limiting Stats:")
            if self.api_calls_throttled > 0:
                self.logger.info(f"  Requests throttled: {self.api_calls_throttled}")
            if self.retry_attempts > 0:
                self.logger.info(f"  Retry attempts: {self.retry_attempts}")
            if self.rate_limit_errors > 0:
                self.logger.warning(f"  Rate limit errors: {self.rate_limit_errors}")

        if self.youtube_units > 8000:
            self.logger.warning(f"YouTube API quota usage is high: {self.youtube_units}/10000 daily limit")

        self.logger.info("="*60)

    def reset(self):
        """Reset counters."""
        self.youtube_units = 0
        self.gemini_calls = 0
        self.api_calls_throttled = 0
        self.retry_attempts = 0
        self.rate_limit_errors = 0
