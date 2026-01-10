# Implementation Plan - API Safety & Quota Optimization

## Context & Reasoning
The user wants to ensure the project does not get blocked by YouTube due to API usage.
Currently, the codebase has a disconnect between documented optimizations (Playlist ID caching) and the actual implementation in `src/ingest.py`.
Additionally, there is no hard stop mechanism if the daily quota is accidentally exceeded, which poses a risk of a 403 block.
We need to sync the code with the documentation to reduce API calls by ~50% and implement a safety fuse for the daily quota.

## Objectives

1.  **[DONE] Implement Playlist ID Caching (`src/ingest.py`)**:
    *   Avoid fetching the "Uploads" playlist ID for every channel on every run.
    *   Persist this mapping in `data/playlist_ids.json`.
    *   **Impact**: Saves 1 API unit per channel per run. For 100 channels, this saves 100 units/run.

2.  **[DONE] Implement Hard Quota Safety Stop (`src/utils/logger.py` & `src/utils/rate_limiter.py`)**:
    *   Add a configurable `daily_quota_limit` (default: 9500, below the 10k free tier).
    *   Update `QuotaTracker` to raise a `QuotaExceededException` if this limit is hit.
    *   Catch this in the main loop to exit gracefully.

3.  **[DONE] Enhance Configuration (`config/pipeline_config.yaml` & `src/utils/config_loader.py`)**:
    *   Add `rate_limiting.daily_quota_limit` setting.
    *   Updated Pydantic models to support new fields.

## Affected Files

*   `config/pipeline_config.yaml`: Add `daily_quota_limit`.
*   `src/utils/logger.py`: Add exception class and check in `QuotaTracker`.
*   `src/utils/rate_limiter.py`: Ensure `YouTubeAPIRateLimiter` respects the tracker's state.
*   `src/ingest.py`: Implement Playlist ID caching logic.

## Pre-Flight Checks
*   `pip install -r requirements.txt` (Ensure dependencies are present)
*   `python src/main.py --help` (Verify CLI is working)

## Testing & Verification
*   **Test Command**: `python -m pytest tests/test_rate_limiter.py` (Need to create this if missing) or run a dry-run ingestion.
*   **Verification**:
    1.  Run `python src/ingest.py`.
    2.  Check `data/playlist_ids.json` is created.
    3.  Run `python src/ingest.py` again.
    4.  Logs should show "[CACHE HIT]" for playlist IDs and quota usage should be lower.

## Risk & Rollback
*   **Risk**: Caching stale playlist IDs (unlikely, as uploads playlist ID rarely changes).
*   **Rollback**: `git checkout src/ingest.py` and delete `data/playlist_ids.json`.
