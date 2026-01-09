import os
import sys
import json
import logging
import pandas as pd
from datetime import datetime, timezone
from googleapiclient.discovery import build
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config_loader import load_config, get_project_root
from src.utils.logger import setup_logger, QuotaTracker
from src.utils.metadata_manager import MetadataManager
from src.utils.rate_limiter import YouTubeAPIRateLimiter
from src.temporal_analysis import save_historical_snapshot

# --- Helper Functions ---

def load_channel_id_cache(cache_path):
    """Loads the stored Channel ID cache from the data directory."""
    if os.path.exists(cache_path):
        with open(cache_path, 'r') as f:
            return json.load(f)
    return {}

def save_channel_id_cache(cache, cache_path):
    """Saves the updated Channel ID cache to the data directory."""
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, 'w') as f:
        json.dump(cache, f, indent=4)

def resolve_channel_id(youtube, handle, cache, logger, quota_tracker, rate_limiter):
    """Checks cache first, then resolves handle to Channel ID using search API (100 units)."""
    if handle in cache:
        return cache[handle]

    logger.info(f"     [CACHE MISS] Resolving handle {handle} (100 units)...")
    quota_tracker.log_youtube_api_call(100, f"search for {handle}")

    try:
        @rate_limiter.rate_limit_youtube_api
        def _search_channel():
            request = youtube.search().list(
                part="snippet",
                type="channel",
                q=handle,
                maxResults=1
            )
            return request.execute()

        response = _search_channel()
        if response.get('items'):
            cid = response['items'][0]['snippet']['channelId']
            cache[handle] = cid  # Update cache
            return cid
        return None
    except Exception as e:
        logger.error(f"Error resolving handle {handle}: {e}")
        return None

def get_recent_videos(youtube, channel_id, channel_name, limit, logger, quota_tracker, rate_limiter):
    """Fetches the most recent X videos from a specific channel ID."""
    videos = []

    try:
        # 1. Get the 'Uploads' Playlist ID (1 unit)
        @rate_limiter.rate_limit_youtube_api
        def _get_uploads_playlist():
            res = youtube.channels().list(id=channel_id, part='contentDetails').execute()
            quota_tracker.log_youtube_api_call(1, f"get uploads playlist for {channel_name}")
            return res

        res = _get_uploads_playlist()
        playlist_id = res['items'][0]['contentDetails']['relatedPlaylists']['uploads']

        # 2. Get videos from that playlist (1 unit, up to 50 results)
        @rate_limiter.rate_limit_youtube_api
        def _get_playlist_items():
            res = youtube.playlistItems().list(
                playlistId=playlist_id,
                part='snippet',
                maxResults=limit
            ).execute()
            quota_tracker.log_youtube_api_call(1, f"get {limit} videos from {channel_name}")
            return res

        res = _get_playlist_items()

        for item in res['items']:
            if item['snippet']['title'] in ["Private video", "Deleted video"]:
                continue

            videos.append({
                "video_id": item['snippet']['resourceId']['videoId'],
                "title": item['snippet']['title'],
                "publish_date": item['snippet']['publishedAt'],
                "channel_name": channel_name,
                "url": f"https://www.youtube.com/watch?v={item['snippet']['resourceId']['videoId']}"
            })
        return videos

    except Exception as e:
        logger.error(f"Error fetching videos for {channel_name}: {e}")
        return []

# --- Main Ingestion Logic ---

def ingest_clusters(clusters_config, api_key, config, logger, quota_tracker, incremental=False, metadata_mgr=None):
    """Main function to process clusters and fetch video metadata."""
    if not api_key:
        logger.error("YOUTUBE_API_KEY not found. Please check your .env file.")
        return pd.DataFrame()

    youtube = build('youtube', 'v3', developerKey=api_key)
    rate_limiter = YouTubeAPIRateLimiter(config, quota_tracker, logger)
    all_videos = []

    # Load cache using config path
    cache_path = config.ingest.channel_id_cache_path
    channel_id_cache = load_channel_id_cache(cache_path)

    # Check for incremental mode
    last_run = None
    if incremental and metadata_mgr:
        last_run = metadata_mgr.get_last_ingest_timestamp()
        if last_run:
            logger.info(f"🔄 Incremental mode: Only fetching videos newer than {last_run}")
        else:
            logger.info("First run - incremental mode disabled, fetching all videos")
            incremental = False

    logger.info(f"Starting Quota-Optimized Ingestion for {len(clusters_config)} clusters...")

    try:
        for cluster_name, handles in clusters_config.items():
            logger.info(f"Processing Cluster: {cluster_name}")

            for handle in handles:
                logger.info(f"  -> Fetching data for: {handle}")

                # 1. Resolve Handle to ID (Cached call)
                cid = resolve_channel_id(youtube, handle, channel_id_cache, logger, quota_tracker, rate_limiter)
                if not cid:
                    continue

                # 2. Fetch Videos (Cheap calls: 2 units per channel)
                videos = get_recent_videos(youtube, cid, handle, config.ingest.videos_per_channel, logger, quota_tracker, rate_limiter)

                # 3. Filter to new videos only if incremental
                if incremental and last_run:
                    original_count = len(videos)
                    videos = [v for v in videos if v['publish_date'] > last_run]
                    if len(videos) < original_count:
                        logger.info(f"     Filtered to {len(videos)} new videos (was {original_count})")

                # 4. Tag with Cluster Name and append
                for v in videos:
                    v['cluster'] = cluster_name
                    all_videos.append(v)
    finally:
        # Always save the cache even if an error occurs mid-run
        if config.ingest.cache_channel_ids:
            save_channel_id_cache(channel_id_cache, cache_path)

    df = pd.DataFrame(all_videos)
    return df

# --- Execution Block ---

if __name__ == "__main__":
    import argparse

    # Change to project root if running from src/
    if os.path.basename(os.getcwd()) == 'src':
        os.chdir('..')

    # Parse arguments
    parser = argparse.ArgumentParser(description='Ingest YouTube video data')
    parser.add_argument('--incremental', action='store_true', help='Only fetch new videos since last run')
    parser.add_argument('--full-refresh', action='store_true', help='Fetch all videos (disable incremental mode)')
    args = parser.parse_args()

    # Load environment and configuration
    load_dotenv()
    config = load_config()

    # Setup logger and metadata manager
    logger = setup_logger("ingest", level=logging.INFO)
    quota_tracker = QuotaTracker(logger)
    metadata_mgr = MetadataManager(logger=logger)

    logger.info("="*60)
    logger.info("YouTube Vibes Tracker - Data Ingestion")
    logger.info("="*60)

    # Determine incremental mode
    incremental_mode = args.incremental or (not args.full_refresh and metadata_mgr.should_run_incremental("ingest"))
    if incremental_mode:
        logger.info("Mode: INCREMENTAL (only new videos)")
    else:
        logger.info("Mode: FULL REFRESH (all videos)")

    # Get API key
    API_KEY = os.getenv("YOUTUBE_API_KEY")

    # Load cluster configuration
    try:
        with open(config.paths.cluster_config, 'r') as f:
            my_clusters = json.load(f)
    except FileNotFoundError:
        logger.error(f"Configuration file not found at {config.paths.cluster_config}. Did you create it?")
        exit(1)

    # Run ingestion
    df = ingest_clusters(my_clusters, API_KEY, config, logger, quota_tracker,
                        incremental=incremental_mode, metadata_mgr=metadata_mgr)

    if not df.empty:
        # Add timestamp for temporal analysis
        df['run_timestamp'] = datetime.now(timezone.utc).isoformat()

        # In incremental mode, append to existing data
        output_path = config.paths.cluster_data
        if incremental_mode and os.path.exists(output_path):
            logger.info("Appending to existing data...")
            existing_df = pd.read_csv(output_path)
            df = pd.concat([existing_df, df], ignore_index=True)
            # Deduplicate by video_id (keep most recent)
            df = df.drop_duplicates(subset=['video_id'], keep='last')
            logger.info(f"Combined dataset: {len(df)} total videos (added {len(df) - len(existing_df)} new)")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df.to_csv(output_path, index=False)

        logger.info(f"Success! Saved {len(df)} videos to {output_path}")
        logger.info(f"\nSample data:\n{df[['cluster', 'channel_name', 'title', 'publish_date']].head()}")

        # Update metadata
        metadata_mgr.update_ingest(len(df))

        # Save historical snapshot for temporal analysis
        save_historical_snapshot(config, logger)
    else:
        logger.warning("Ingestion complete, but no data was found.")

    # Log quota usage
    quota_tracker.log_summary()

    # Log metadata stats
    stats = metadata_mgr.get_stats()
    logger.info(f"\n📊 Pipeline Stats:")
    logger.info(f"   Total ingested: {stats['total_videos_ingested']} videos")
    logger.info(f"   Total analyzed: {stats['total_videos_analyzed']} videos")
    logger.info(f"   Total runs: {stats['total_runs']}")

    logger.info("="*60)