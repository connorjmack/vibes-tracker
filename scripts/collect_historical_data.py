"""Collect historical YouTube data for multi-year temporal analysis."""

import os
import sys
import json
import logging
import argparse
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from googleapiclient.discovery import build
from dotenv import load_dotenv
from src.utils.config_loader import load_config
from src.utils.logger import setup_logger, QuotaTracker
from src.analyze import get_transcript
from src.utils.cache_manager import CacheManager
from src.utils.rate_limiter import TranscriptRateLimiter
from tqdm import tqdm

def fetch_transcripts_for_period(df, config, logger):
    """
    Fetch transcripts for all videos in the dataframe efficiently.
    
    Args:
        df: DataFrame containing video metadata (must have 'video_id')
        config: Configuration object
        logger: Logger instance
        
    Returns:
        DataFrame with added 'transcript' column
    """
    if 'video_id' not in df.columns:
        logger.error("DataFrame missing 'video_id' column")
        return df
        
    logger.info(f"Fetching transcripts for {len(df)} videos...")
    
    cache_manager = CacheManager(config.analysis.cache_dir, logger)
    transcript_rate_limiter = TranscriptRateLimiter(config, logger)
    
    transcripts = {}
    
    # Use tqdm for progress bar
    for video_id in tqdm(df['video_id'].unique(), desc="Fetching Transcripts"):
        text = get_transcript(video_id, cache_manager, logger, transcript_rate_limiter)
        if text:
            transcripts[video_id] = text
            
    # Map transcripts to dataframe
    df['transcript'] = df['video_id'].map(transcripts)
    
    success_count = df['transcript'].notna().sum()
    logger.info(f"Successfully fetched {success_count}/{len(df)} transcripts")
    
    return df

def fetch_videos_by_date_range(youtube, channel_id, channel_name,
                                published_after, published_before,
                                logger, quota_tracker, max_results=50):
    """
    Fetch videos from a channel within a specific date range.

    Args:
        youtube: YouTube API client
        channel_id: Channel ID
        channel_name: Channel name/handle
        published_after: ISO 8601 date string (e.g., "2024-01-01T00:00:00Z")
        published_before: ISO 8601 date string
        logger: Logger instance
        quota_tracker: QuotaTracker instance
        max_results: Maximum videos to fetch per channel

    Returns:
        List of video dictionaries
    """
    videos = []

    try:
        # Get the uploads playlist
        res = youtube.channels().list(id=channel_id, part='contentDetails').execute()
        quota_tracker.log_youtube_api_call(1, f"get uploads playlist for {channel_name}")
        playlist_id = res['items'][0]['contentDetails']['relatedPlaylists']['uploads']

        # Fetch videos with pagination
        page_token = None
        videos_fetched = 0

        while videos_fetched < max_results:
            request = youtube.playlistItems().list(
                playlistId=playlist_id,
                part='snippet',
                maxResults=min(50, max_results - videos_fetched),
                pageToken=page_token
            )
            res = request.execute()
            quota_tracker.log_youtube_api_call(1, f"get videos from {channel_name}")

            for item in res['items']:
                if item['snippet']['title'] in ["Private video", "Deleted video"]:
                    continue

                publish_date = item['snippet']['publishedAt']

                # Filter by date range
                if published_after and publish_date < published_after:
                    continue
                if published_before and publish_date >= published_before:
                    continue

                videos.append({
                    "video_id": item['snippet']['resourceId']['videoId'],
                    "title": item['snippet']['title'],
                    "publish_date": publish_date,
                    "channel_name": channel_name,
                    "url": f"https://www.youtube.com/watch?v={item['snippet']['resourceId']['videoId']}"
                })
                videos_fetched += 1

            # Check for more pages
            page_token = res.get('nextPageToken')
            if not page_token:
                break

        return videos

    except Exception as e:
        logger.error(f"Error fetching videos for {channel_name}: {e}")
        return []

def collect_historical_period(start_date, end_date, output_dir="data/historical", transcripts_only=False):
    """
    Collect data for a specific time period.

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        output_dir: Base directory for historical data
        transcripts_only: If True, only fetch transcripts for existing metadata
    """
    # Setup
    load_dotenv()
    config = load_config()
    logger = setup_logger("historical-collection", level=logging.INFO)
    quota_tracker = QuotaTracker(logger)

    snapshot_dir = Path(output_dir) / start_date
    output_file = snapshot_dir / "cluster_data.csv"

    # Transcripts Only Mode
    if transcripts_only:
        if not output_file.exists():
            logger.error(f"Metadata file not found at {output_file}. Cannot run --transcripts-only.")
            return
            
        logger.info(f"🔄 Mode: TRANSCRIPTS ONLY for {start_date}")
        df = pd.read_csv(output_file)
        
        df = fetch_transcripts_for_period(df, config, logger)
        
        # Save updated dataframe
        df.to_csv(output_file, index=False)
        logger.info(f"✅ Updated metadata with transcripts saved to {output_file}")
        return

    # Standard Mode (Fetch Metadata)
    API_KEY = os.getenv("YOUTUBE_API_KEY")
    if not API_KEY:
        logger.error("YOUTUBE_API_KEY not found in .env")
        return

    youtube = build('youtube', 'v3', developerKey=API_KEY)

    # Load clusters
    with open(config.paths.cluster_config, 'r') as f:
        clusters = json.load(f)

    # Load channel ID cache
    cache_path = config.ingest.channel_id_cache_path
    if os.path.exists(cache_path):
        with open(cache_path, 'r') as f:
            channel_id_cache = json.load(f)
    else:
        logger.error("Channel ID cache not found. Run ingest.py first to build cache.")
        return

    # Convert dates to ISO 8601
    published_after = f"{start_date}T00:00:00Z"
    published_before = f"{end_date}T00:00:00Z"

    logger.info("="*60)
    logger.info(f"Collecting Historical Data: {start_date} to {end_date}")
    logger.info("="*60)

    all_videos = []

    for cluster_name, handles in clusters.items():
        logger.info(f"\n📂 Processing Cluster: {cluster_name}")

        for handle in handles:
            channel_id = channel_id_cache.get(handle)
            if not channel_id:
                logger.warning(f"Channel ID not found for {handle} in cache")
                continue

            logger.info(f"  -> Fetching {handle} ({start_date} to {end_date})")

            videos = fetch_videos_by_date_range(
                youtube, channel_id, handle,
                published_after, published_before,
                logger, quota_tracker
            )

            # Tag with cluster
            for v in videos:
                v['cluster'] = cluster_name
                all_videos.append(v)

            logger.info(f"     Found {len(videos)} videos")

    # Save data
    if all_videos:
        df = pd.DataFrame(all_videos)
        df['run_timestamp'] = datetime.now(timezone.utc).isoformat()

        # Save to dated directory
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        df.to_csv(output_file, index=False)

        logger.info(f"\n✅ Saved {len(all_videos)} videos to {output_file}")
        logger.info(f"   Videos by cluster:")
        for cluster, count in df['cluster'].value_counts().items():
            logger.info(f"   - {cluster}: {count}")
    else:
        logger.warning(f"\n⚠️  No videos found for period {start_date} to {end_date}")

    quota_tracker.log_summary()
    logger.info("="*60)


def collect_multi_year_data(start_year, end_year, frequency='monthly', transcripts_only=False):
    """
    Collect data spanning multiple years.

    Args:
        start_year: Starting year (e.g., 2022)
        end_year: Ending year (e.g., 2024)
        frequency: 'monthly', 'quarterly', or 'yearly'
        transcripts_only: If True, only fetch transcripts for existing metadata
    """
    logger = setup_logger("multi-year-collection", level=logging.INFO)

    logger.info("="*60)
    logger.info(f"Multi-Year Historical Collection: {start_year}-{end_year}")
    logger.info(f"Frequency: {frequency}")
    if transcripts_only:
        logger.info("Mode: TRANSCRIPTS ONLY (Skipping YouTube API metadata fetch)")
    logger.info("="*60)

    periods = []

    if frequency == 'monthly':
        for year in range(start_year, end_year + 1):
            for month in range(1, 13):
                # Skip future months
                if year == datetime.now().year and month > datetime.now().month:
                    break

                start_date = f"{year}-{month:02d}-01"

                # Calculate end date (first day of next month)
                if month == 12:
                    end_date = f"{year + 1}-01-01"
                else:
                    end_date = f"{year}-{month + 1:02d}-01"

                periods.append((start_date, end_date))

    elif frequency == 'quarterly':
        for year in range(start_year, end_year + 1):
            for quarter in range(1, 5):
                start_month = (quarter - 1) * 3 + 1
                start_date = f"{year}-{start_month:02d}-01"

                if quarter == 4:
                    end_date = f"{year + 1}-01-01"
                else:
                    end_month = quarter * 3 + 1
                    end_date = f"{year}-{end_month:02d}-01"

                periods.append((start_date, end_date))

    elif frequency == 'yearly':
        for year in range(start_year, end_year + 1):
            periods.append((f"{year}-01-01", f"{year + 1}-01-01"))

    if not transcripts_only:
        logger.info(f"\n📅 Will collect {len(periods)} time periods")
        logger.info(f"   Estimated API units: {len(periods) * 120} (120 per period)")
        logger.info(f"   Within daily quota: {'✅ Yes' if len(periods) * 120 < 10000 else '❌ No - will take multiple days'}")

    # Collect each period
    for i, (start, end) in enumerate(periods, 1):
        logger.info(f"\n[{i}/{len(periods)}] Processing {start} to {end}")
        collect_historical_period(start, end, transcripts_only=transcripts_only)

    logger.info("\n✅ Multi-year collection complete!")


def collect_channel_history(channel_handle, start_date, end_date, output_dir="data/historical"):
    """
    Collect all transcripts for a specific channel over a time range.
    Saves individual transcript files and an index CSV.
    
    Args:
        channel_handle: Channel handle (e.g., "@joerogan")
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        output_dir: Base directory
    """
    # Setup
    load_dotenv()
    config = load_config()
    logger = setup_logger("channel-collection", level=logging.INFO)
    quota_tracker = QuotaTracker(logger)
    
    API_KEY = os.getenv("YOUTUBE_API_KEY")
    if not API_KEY:
        logger.error("YOUTUBE_API_KEY not found in .env")
        return

    youtube = build('youtube', 'v3', developerKey=API_KEY)
    
    # 1. Resolve Channel ID
    cache_path = config.ingest.channel_id_cache_path
    channel_id = None
    
    if os.path.exists(cache_path):
        with open(cache_path, 'r') as f:
            cache = json.load(f)
            channel_id = cache.get(channel_handle)
    
    if not channel_id:
        logger.info(f"Resolving Channel ID for {channel_handle}...")
        try:
            req = youtube.search().list(part="snippet", type="channel", q=channel_handle, maxResults=1)
            res = req.execute()
            if res['items']:
                channel_id = res['items'][0]['snippet']['channelId']
                logger.info(f"Found ID: {channel_id}")
            else:
                logger.error(f"Could not find channel: {channel_handle}")
                return
        except Exception as e:
            logger.error(f"API Error resolving channel: {e}")
            return

    # 2. Fetch Video List
    published_after = f"{start_date}T00:00:00Z"
    published_before = f"{end_date}T00:00:00Z"
    
    logger.info(f"Fetching video list for {channel_handle} ({start_date} to {end_date})...")
    
    # We use a large max_results because we want EVERYTHING in the period
    videos = fetch_videos_by_date_range(
        youtube, channel_id, channel_handle,
        published_after, published_before,
        logger, quota_tracker,
        max_results=5000 # Upper limit for safety, likely covers years
    )
    
    if not videos:
        logger.warning("No videos found in this date range.")
        return
        
    logger.info(f"Found {len(videos)} videos. Beginning transcript download...")
    
    # 3. Prepare Output Directory
    channel_dir = Path(output_dir) / channel_handle
    channel_dir.mkdir(parents=True, exist_ok=True)
    
    # 4. Fetch Transcripts
    cache_manager = CacheManager(config.analysis.cache_dir, logger)
    transcript_rate_limiter = TranscriptRateLimiter(config, logger)
    
    # Check for existing index to avoid re-downloading if interrupted
    index_path = channel_dir / "index.csv"
    existing_ids = set()
    if index_path.exists():
        try:
            existing_df = pd.read_csv(index_path)
            existing_ids = set(existing_df['video_id'].unique())
            logger.info(f"Resuming: Found {len(existing_ids)} existing entries in index.")
        except:
            pass

    results = []
    
    for video in tqdm(videos, desc=f"Downloading {channel_handle}"):
        vid = video['video_id']
        date_str = video['publish_date'].split('T')[0]
        safe_title = "".join([c for c in video['title'] if c.isalnum() or c in (' ', '-', '_')]).strip()
        filename = f"{date_str}_{vid}.txt"
        file_path = channel_dir / filename
        
        # Skip if already exists on disk
        if file_path.exists():
            results.append({
                'video_id': vid,
                'publish_date': video['publish_date'],
                'title': video['title'],
                'filename': filename,
                'status': 'exists'
            })
            continue
            
        # Get Transcript
        text = get_transcript(vid, cache_manager, logger, transcript_rate_limiter)
        
        if text:
            # Save Text File
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(text)
            
            results.append({
                'video_id': vid,
                'publish_date': video['publish_date'],
                'title': video['title'],
                'filename': filename,
                'status': 'downloaded'
            })
        else:
            results.append({
                'video_id': vid,
                'publish_date': video['publish_date'],
                'title': video['title'],
                'filename': None,
                'status': 'failed'
            })
            
    # 5. Save/Update Index
    new_df = pd.DataFrame(results)
    
    if index_path.exists():
        final_df = pd.concat([pd.read_csv(index_path), new_df]).drop_duplicates(subset=['video_id'], keep='last')
    else:
        final_df = new_df
        
    final_df.to_csv(index_path, index=False)
    
    downloaded = len(new_df[new_df['status'] == 'downloaded'])
    failed = len(new_df[new_df['status'] == 'failed'])
    
    logger.info(f"Collection Complete for {channel_handle}")
    logger.info(f"   Downloaded: {downloaded}")
    logger.info(f"   Failed/No Transcript: {failed}")
    logger.info(f"   Saved to: {channel_dir}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Collect historical YouTube data')
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--start-year', type=int, help='Start year for multi-year collection')
    parser.add_argument('--end-year', type=int, help='End year for multi-year collection')
    parser.add_argument('--frequency', type=str, default='monthly',
                       choices=['monthly', 'quarterly', 'yearly'],
                       help='Collection frequency for multi-year mode')
    parser.add_argument('--transcripts-only', action='store_true',
                       help='Only fetch transcripts for existing metadata (no YouTube API calls)')
    parser.add_argument('--channel', type=str,
                       help='Collect history for a specific channel (e.g. @joerogan). Overrides cluster mode.')

    args = parser.parse_args()

    if args.channel:
        # Channel-specific mode
        if args.start_year and args.end_year:
            s_date = f"{args.start_year}-01-01"
            e_date = f"{args.end_year}-12-31"
        elif args.start_date and args.end_date:
            s_date = args.start_date
            e_date = args.end_date
        else:
            print("Error: For --channel, you must provide --start-year/--end-year OR --start-date/--end-date")
            exit(1)
            
        collect_channel_history(args.channel, s_date, e_date)
        
    elif args.start_date and args.end_date:
        # Single period collection
        collect_historical_period(args.start_date, args.end_date, transcripts_only=args.transcripts_only)
    elif args.start_year and args.end_year:
        # Multi-year collection
        collect_multi_year_data(args.start_year, args.end_year, args.frequency, transcripts_only=args.transcripts_only)
    else:
        print("Usage:")
        print("  Channel History: python scripts/collect_historical_data.py --channel @joerogan --start-year 2020 --end-year 2023")
        print("  Single period:   python scripts/collect_historical_data.py --start-date 2024-01-01 --end-date 2024-02-01")
        print("  Multi-year:      python scripts/collect_historical_data.py --start-year 2022 --end-year 2024 --frequency monthly")
