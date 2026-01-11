import sys
import os
import pytest
from unittest.mock import MagicMock, patch
import json

from vibes_tracker.utils.logger import QuotaTracker, QuotaExceededException
from vibes_tracker.utils.rate_limiter import YouTubeAPIRateLimiter
from vibes_tracker.utils.config_loader import load_config
from vibes_tracker.core.ingest import get_recent_videos, resolve_channel_id

# --- Fixtures ---

@pytest.fixture
def mock_logger():
    return MagicMock()

@pytest.fixture
def quota_tracker(mock_logger):
    return QuotaTracker(mock_logger, daily_limit=100)

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.rate_limiting.youtube_api.enabled = True
    config.rate_limiting.youtube_api.daily_quota_limit = 100
    config.rate_limiting.youtube_api.min_delay_seconds = 0.0
    config.rate_limiting.youtube_api.max_delay_seconds = 0.1
    config.rate_limiting.youtube_api.max_retries = 1
    config.rate_limiting.youtube_api.backoff_multiplier = 1.0
    config.rate_limiting.youtube_api.requests_per_second = 1000
    config.rate_limiting.youtube_api.burst_size = 10
    return config

# --- Tests ---

def test_quota_tracker_raises_exception(quota_tracker):
    """Test that QuotaTracker raises exception when limit is hit."""
    # Use 90 units (limit 100)
    quota_tracker.log_youtube_api_call(90, "op1")
    assert quota_tracker.youtube_units == 90
    
    # Use 10 more - hitting exact limit
    with pytest.raises(QuotaExceededException):
        quota_tracker.log_youtube_api_call(10, "op2")
    
    assert quota_tracker.youtube_units == 100

def test_rate_limiter_checks_quota(mock_config, quota_tracker, mock_logger):
    """Test that YouTubeAPIRateLimiter checks quota before execution."""
    # Exhaust quota first
    try:
        quota_tracker.log_youtube_api_call(100, "exhaust")
    except QuotaExceededException:
        pass
        
    limiter = YouTubeAPIRateLimiter(mock_config, quota_tracker, mock_logger)
    
    mock_api_call = MagicMock()
    decorated_func = limiter.rate_limit_youtube_api(mock_api_call)
    
    # Should raise exception and NOT call the function
    with pytest.raises(QuotaExceededException):
        decorated_func()
        
    mock_api_call.assert_not_called()

def test_playlist_caching(mock_logger):
    """Test that playlist IDs are cached and reused."""
    quota_tracker = MagicMock()
    rate_limiter = MagicMock()
    rate_limiter.rate_limit_youtube_api = lambda f: f
    
    youtube = MagicMock()
    
    # Mock responses
    youtube.channels.return_value.list.return_value.execute.return_value = {
        'items': [{'contentDetails': {'relatedPlaylists': {'uploads': 'UU123'}}}]
    }
    youtube.playlistItems.return_value.list.return_value.execute.return_value = {'items': []}
    
    playlist_cache = {}
    
    # 1. First call - Cache Miss
    get_recent_videos(
        youtube, "UC123", "TestChan", 10, mock_logger, quota_tracker, rate_limiter, 
        playlist_cache=playlist_cache
    )
    
    assert playlist_cache.get("UC123") == 'UU123'
    # channels().list() called once
    assert youtube.channels.return_value.list.call_count == 1
    
    # 2. Second call - Cache Hit
    get_recent_videos(
        youtube, "UC123", "TestChan", 10, mock_logger, quota_tracker, rate_limiter, 
        playlist_cache=playlist_cache
    )
    
    # channels().list() count should remain 1
    assert youtube.channels.return_value.list.call_count == 1

def test_resolve_channel_id_cache(mock_logger):
    """Test channel ID resolution caching."""
    quota_tracker = MagicMock()
    rate_limiter = MagicMock()
    rate_limiter.rate_limit_youtube_api = lambda f: f
    
    youtube = MagicMock()
    youtube.search.return_value.list.return_value.execute.return_value = {
        'items': [{'snippet': {'channelId': 'UC_NEW'}}]
    }
    
    cache = {"@known": "UC_KNOWN"}
    
    # 1. Cache Hit
    cid = resolve_channel_id(youtube, "@known", cache, mock_logger, quota_tracker, rate_limiter)
    assert cid == "UC_KNOWN"
    youtube.search.assert_not_called()
    
    # 2. Cache Miss
    cid = resolve_channel_id(youtube, "@unknown", cache, mock_logger, quota_tracker, rate_limiter)
    assert cid == "UC_NEW"
    assert cache["@unknown"] == "UC_NEW"
    youtube.search.assert_called_once()
