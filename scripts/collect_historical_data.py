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


def collect_historical_period(start_date, end_date, output_dir="data/historical"):
    """
    Collect data for a specific time period.

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        output_dir: Base directory for historical data
    """
    # Setup
    load_dotenv()
    config = load_config()
    logger = setup_logger("historical-collection", level=logging.INFO)
    quota_tracker = QuotaTracker(logger)

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
        snapshot_dir = Path(output_dir) / start_date
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        output_file = snapshot_dir / "cluster_data.csv"
        df.to_csv(output_file, index=False)

        logger.info(f"\n✅ Saved {len(all_videos)} videos to {output_file}")
        logger.info(f"   Videos by cluster:")
        for cluster, count in df['cluster'].value_counts().items():
            logger.info(f"   - {cluster}: {count}")
    else:
        logger.warning(f"\n⚠️  No videos found for period {start_date} to {end_date}")

    quota_tracker.log_summary()
    logger.info("="*60)


def collect_multi_year_data(start_year, end_year, frequency='monthly'):
    """
    Collect data spanning multiple years.

    Args:
        start_year: Starting year (e.g., 2022)
        end_year: Ending year (e.g., 2024)
        frequency: 'monthly', 'quarterly', or 'yearly'
    """
    logger = setup_logger("multi-year-collection", level=logging.INFO)

    logger.info("="*60)
    logger.info(f"Multi-Year Historical Collection: {start_year}-{end_year}")
    logger.info(f"Frequency: {frequency}")
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

    logger.info(f"\n📅 Will collect {len(periods)} time periods")
    logger.info(f"   Estimated API units: {len(periods) * 120} (120 per period)")
    logger.info(f"   Within daily quota: {'✅ Yes' if len(periods) * 120 < 10000 else '❌ No - will take multiple days'}")

    # Collect each period
    for i, (start, end) in enumerate(periods, 1):
        logger.info(f"\n[{i}/{len(periods)}] Collecting {start} to {end}")
        collect_historical_period(start, end)

    logger.info("\n✅ Multi-year collection complete!")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Collect historical YouTube data')
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--start-year', type=int, help='Start year for multi-year collection')
    parser.add_argument('--end-year', type=int, help='End year for multi-year collection')
    parser.add_argument('--frequency', type=str, default='monthly',
                       choices=['monthly', 'quarterly', 'yearly'],
                       help='Collection frequency for multi-year mode')

    args = parser.parse_args()

    if args.start_date and args.end_date:
        # Single period collection
        collect_historical_period(args.start_date, args.end_date)
    elif args.start_year and args.end_year:
        # Multi-year collection
        collect_multi_year_data(args.start_year, args.end_year, args.frequency)
    else:
        print("Usage:")
        print("  Single period:  python scripts/collect_historical_data.py --start-date 2024-01-01 --end-date 2024-02-01")
        print("  Multi-year:     python scripts/collect_historical_data.py --start-year 2022 --end-year 2024 --frequency monthly")
