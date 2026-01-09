#!/usr/bin/env python3
"""
Verification script to test rate limiting implementation.

This script verifies that:
1. Rate limiting modules import correctly
2. Configuration is valid
3. Rate limiter classes can be instantiated
4. Basic rate limiting logic works
"""

import os
import sys
import time
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from src.utils.config_loader import load_config
from src.utils.logger import setup_logger, QuotaTracker
from src.utils.rate_limiter import RateLimiter, YouTubeAPIRateLimiter, TranscriptRateLimiter


def test_imports():
    """Test that all rate limiting modules import correctly."""
    print("✓ Testing imports...")
    try:
        from src.utils.rate_limiter import RateLimiter, YouTubeAPIRateLimiter, TranscriptRateLimiter
        print("  ✓ Rate limiter classes imported successfully")
        return True
    except Exception as e:
        print(f"  ✗ Import error: {e}")
        return False


def test_config():
    """Test that configuration loads and has rate limiting settings."""
    print("\n✓ Testing configuration...")
    try:
        config = load_config()

        # Check rate_limiting section exists
        assert hasattr(config, 'rate_limiting'), "Missing rate_limiting in config"
        print("  ✓ rate_limiting section found in config")

        # Check YouTube API settings
        assert hasattr(config.rate_limiting, 'youtube_api'), "Missing youtube_api settings"
        yt_config = config.rate_limiting.youtube_api
        assert hasattr(yt_config, 'enabled'), "Missing enabled setting"
        assert hasattr(yt_config, 'min_delay_seconds'), "Missing min_delay_seconds"
        assert hasattr(yt_config, 'max_retries'), "Missing max_retries"
        print("  ✓ YouTube API rate limiting config valid")

        # Check transcript settings
        assert hasattr(config.rate_limiting, 'transcript_api'), "Missing transcript_api settings"
        ts_config = config.rate_limiting.transcript_api
        assert hasattr(ts_config, 'enabled'), "Missing enabled setting"
        assert hasattr(ts_config, 'min_delay_seconds'), "Missing min_delay_seconds"
        print("  ✓ Transcript API rate limiting config valid")

        # Check batch settings
        assert hasattr(config.rate_limiting, 'batch_operations'), "Missing batch_operations"
        batch_config = config.rate_limiting.batch_operations
        assert hasattr(batch_config, 'max_parallel_workers'), "Missing max_parallel_workers"
        print(f"  ✓ Batch operations config valid (max_workers={batch_config.max_parallel_workers})")

        return True
    except Exception as e:
        print(f"  ✗ Configuration error: {e}")
        return False


def test_rate_limiter_instantiation():
    """Test that rate limiter classes can be instantiated."""
    print("\n✓ Testing rate limiter instantiation...")
    try:
        logger = setup_logger("test", log_to_file=False)
        config = load_config()
        quota_tracker = QuotaTracker(logger)

        # Test RateLimiter
        limiter = RateLimiter(requests_per_second=1.0, burst_size=2, logger=logger)
        print("  ✓ RateLimiter instantiated successfully")

        # Test YouTubeAPIRateLimiter
        yt_limiter = YouTubeAPIRateLimiter(config, quota_tracker, logger)
        assert yt_limiter.enabled == True, "YouTube API rate limiter should be enabled"
        print("  ✓ YouTubeAPIRateLimiter instantiated successfully (enabled)")

        # Test TranscriptRateLimiter
        ts_limiter = TranscriptRateLimiter(config, logger)
        assert ts_limiter.enabled == True, "Transcript API rate limiter should be enabled"
        print("  ✓ TranscriptRateLimiter instantiated successfully (enabled)")

        return True
    except Exception as e:
        print(f"  ✗ Instantiation error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_token_bucket():
    """Test basic token bucket functionality."""
    print("\n✓ Testing token bucket algorithm...")
    try:
        logger = setup_logger("test", log_to_file=False)

        # Create a rate limiter: 2 requests per second
        limiter = RateLimiter(requests_per_second=2.0, burst_size=2, logger=logger)

        # Test 1: Should allow burst immediately
        start = time.time()
        limiter.acquire()
        limiter.acquire()
        burst_time = time.time() - start
        assert burst_time < 0.1, f"Burst should be fast (was {burst_time:.2f}s)"
        print(f"  ✓ Burst of 2 requests allowed immediately ({burst_time:.3f}s)")

        # Test 2: Next request should be delayed
        start = time.time()
        limiter.acquire()
        throttle_time = time.time() - start
        assert throttle_time >= 0.45, f"Should have delayed ~0.5s (was {throttle_time:.2f}s)"
        print(f"  ✓ Third request throttled as expected ({throttle_time:.3f}s)")

        return True
    except Exception as e:
        print(f"  ✗ Token bucket error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_decorator():
    """Test that rate limiter decorators work."""
    print("\n✓ Testing rate limiter decorators...")
    try:
        logger = setup_logger("test", log_to_file=False)
        config = load_config()
        quota_tracker = QuotaTracker(logger)

        yt_limiter = YouTubeAPIRateLimiter(config, quota_tracker, logger)

        # Test that decorator can be applied
        @yt_limiter.rate_limit_youtube_api
        def mock_api_call():
            return {"success": True}

        result = mock_api_call()
        assert result["success"] == True, "Decorated function should return result"
        print("  ✓ YouTubeAPIRateLimiter decorator works")

        # Test transcript decorator
        ts_limiter = TranscriptRateLimiter(config, logger)

        @ts_limiter.rate_limit_transcript_fetch
        def mock_transcript_fetch():
            return "test transcript"

        result = mock_transcript_fetch()
        assert result == "test transcript", "Decorated function should return result"
        print("  ✓ TranscriptRateLimiter decorator works")

        return True
    except Exception as e:
        print(f"  ✗ Decorator error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_quota_tracker_enhancements():
    """Test QuotaTracker enhancements for rate limiting."""
    print("\n✓ Testing QuotaTracker enhancements...")
    try:
        logger = setup_logger("test", log_to_file=False)
        quota_tracker = QuotaTracker(logger)

        # Test new methods exist
        assert hasattr(quota_tracker, 'log_throttle'), "Missing log_throttle method"
        assert hasattr(quota_tracker, 'log_retry'), "Missing log_retry method"
        assert hasattr(quota_tracker, 'log_rate_limit_error'), "Missing log_rate_limit_error method"
        print("  ✓ QuotaTracker has all new rate limiting methods")

        # Test logging methods work
        quota_tracker.log_youtube_api_call(100, "test search")
        quota_tracker.log_throttle(1.5)
        quota_tracker.log_retry(1, "429 error")
        quota_tracker.log_rate_limit_error()

        assert quota_tracker.youtube_units == 100, "YouTube units not tracked"
        assert quota_tracker.api_calls_throttled == 1, "Throttle count not tracked"
        assert quota_tracker.retry_attempts == 1, "Retry count not tracked"
        assert quota_tracker.rate_limit_errors == 1, "Rate limit error count not tracked"
        print("  ✓ QuotaTracker metrics tracking works correctly")

        return True
    except Exception as e:
        print(f"  ✗ QuotaTracker error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all verification tests."""
    print("="*60)
    print("Rate Limiting Implementation Verification")
    print("="*60)

    # Load environment
    load_dotenv()

    # Run tests
    tests = [
        test_imports,
        test_config,
        test_rate_limiter_instantiation,
        test_token_bucket,
        test_decorator,
        test_quota_tracker_enhancements,
    ]

    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"\n✗ Unexpected error in {test_func.__name__}: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)

    # Summary
    print("\n" + "="*60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")

    if all(results):
        print("\n✅ All verification tests passed!")
        print("\nRate limiting implementation is working correctly.")
        print("\nNext steps:")
        print("1. Run ingest to test YouTube API rate limiting")
        print("2. Run daily_report to test batch delays")
        print("3. Run analyze to test transcript rate limiting")
        print("\nMonitor logs for rate limiting messages:")
        print("  - 'Rate limiter throttled': API call delayed")
        print("  - 'Retry attempt': Error triggered retry logic")
        print("  - 'Rate limit error': Rate limit was exceeded")
        print("="*60)
        return 0
    else:
        print("\n❌ Some tests failed!")
        print("Please review the errors above.")
        print("="*60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
