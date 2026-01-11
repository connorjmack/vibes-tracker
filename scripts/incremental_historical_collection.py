#!/usr/bin/env python3
"""
Incremental Historical Data Collection

Collects historical YouTube data gradually over multiple days,
respecting API quota limits and tracking progress.
"""

import os
import sys
import json
import logging
import subprocess
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Tuple

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from googleapiclient.discovery import build
from src.utils.config_loader import load_config
from src.utils.logger import setup_logger, QuotaTracker
from src.utils.rate_limiter import YouTubeAPIRateLimiter

# Progress tracking file
PROGRESS_FILE = "data/historical_collection_progress.json"
PLAYLIST_CACHE_FILE = "data/playlist_ids_cache.json"
QUOTA_SAFETY_LIMIT = 8000  # Stop at 8000 units to leave buffer


def load_progress():
    """Load collection progress from file."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {
        "completed_periods": [],
        "failed_periods": [],
        "last_run": None,
        "total_videos_collected": 0
    }


def load_playlist_cache():
    """Load cached playlist IDs to save API quota."""
    if os.path.exists(PLAYLIST_CACHE_FILE):
        with open(PLAYLIST_CACHE_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_playlist_cache(cache):
    """Save playlist ID cache."""
    os.makedirs(os.path.dirname(PLAYLIST_CACHE_FILE), exist_ok=True)
    with open(PLAYLIST_CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)


def save_progress(progress):
    """Save collection progress to file."""
    os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)


def send_notification(title: str, message: str, sound: bool = True):
    """
    Send macOS system notification.

    Args:
        title: Notification title
        message: Notification message
        sound: Play notification sound
    """
    try:
        sound_arg = "sound name 'Glass'" if sound else ""
        applescript = f'''
        display notification "{message}" with title "{title}" {sound_arg}
        '''
        subprocess.run(['osascript', '-e', applescript],
                      capture_output=True,
                      timeout=5)
    except Exception as e:
        # Silently fail - notifications are nice-to-have
        pass


def create_status_dashboard(progress: dict, total_periods: int,
                            videos_this_run: int, quota_used: int):
    """
    Create an HTML status dashboard showing collection progress.

    Args:
        progress: Progress tracking dictionary
        total_periods: Total number of periods to collect
        videos_this_run: Videos collected in this run
        quota_used: API quota units used this run
    """
    completed = len(progress['completed_periods'])
    percentage = (completed / total_periods * 100) if total_periods > 0 else 0

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Vibes Tracker - Collection Status</title>
    <meta http-equiv="refresh" content="300">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            margin-top: 0;
        }}
        .progress-bar {{
            width: 100%;
            height: 30px;
            background: #e0e0e0;
            border-radius: 15px;
            overflow: hidden;
            margin: 20px 0;
        }}
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #4CAF50, #45a049);
            transition: width 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        .stat {{
            background: #f9f9f9;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #4CAF50;
        }}
        .stat-label {{
            color: #666;
            font-size: 14px;
            margin-bottom: 5px;
        }}
        .stat-value {{
            font-size: 28px;
            font-weight: bold;
            color: #333;
        }}
        .timestamp {{
            color: #999;
            font-size: 14px;
            margin-top: 20px;
        }}
        .status {{
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: bold;
        }}
        .status.active {{
            background: #4CAF50;
            color: white;
        }}
        .status.pending {{
            background: #FFC107;
            color: white;
        }}
        .status.complete {{
            background: #2196F3;
            color: white;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Historical Data Collection Status</h1>

        <div style="margin-bottom: 20px;">
            <span class="status {'complete' if percentage >= 100 else 'active' if videos_this_run > 0 else 'pending'}">
                {'✅ Complete' if percentage >= 100 else '🔄 Collecting' if videos_this_run > 0 else '⏸️ Pending'}
            </span>
        </div>

        <div class="progress-bar">
            <div class="progress-fill" style="width: {percentage}%">
                {percentage:.1f}%
            </div>
        </div>

        <div class="stats">
            <div class="stat">
                <div class="stat-label">Periods Completed</div>
                <div class="stat-value">{completed}/{total_periods}</div>
            </div>
            <div class="stat">
                <div class="stat-label">Total Videos Collected</div>
                <div class="stat-value">{progress['total_videos_collected']:,}</div>
            </div>
            <div class="stat">
                <div class="stat-label">Last Run Videos</div>
                <div class="stat-value">{videos_this_run}</div>
            </div>
            <div class="stat">
                <div class="stat-label">API Quota Used (Last Run)</div>
                <div class="stat-value">{quota_used}</div>
            </div>
        </div>

        <div class="timestamp">
            Last updated: {progress.get('last_run', 'Never')}
        </div>

        {'<p style="color: #4CAF50; font-weight: bold;">🎉 Collection complete! You can now run the full analysis.</p>' if percentage >= 100 else f'<p>Estimated days remaining: {((total_periods - completed) / 10):.1f} days (at 10 periods/day)</p>'}
    </div>
</body>
</html>
"""

    dashboard_path = "data/collection_status.html"
    with open(dashboard_path, 'w') as f:
        f.write(html)

    return dashboard_path


def generate_monthly_periods(start_year: int, end_year: int) -> List[Tuple[str, str]]:
    """Generate list of monthly periods to collect."""
    periods = []
    current = datetime.now()

    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            # Skip future months
            if year > current.year or (year == current.year and month > current.month):
                break

            start_date = f"{year}-{month:02d}-01"

            # Calculate end date (first day of next month)
            if month == 12:
                end_date = f"{year + 1}-01-01"
            else:
                end_date = f"{year}-{month + 1:02d}-01"

            periods.append((start_date, end_date))

    return periods


def period_already_collected(start_date: str, progress: dict) -> bool:
    """Check if a period has already been collected."""
    return start_date in progress["completed_periods"]


def collect_single_period(youtube, channel_id_cache, playlist_cache, clusters,
                          start_date: str, end_date: str,
                          logger, quota_tracker, rate_limiter=None) -> int:
    """
    Collect data for a single time period.

    Returns:
        Number of videos collected
    """
    published_after = f"{start_date}T00:00:00Z"
    published_before = f"{end_date}T00:00:00Z"

    all_videos = []
    cache_updated = False

    for cluster_name, handles in clusters.items():
        logger.info(f"  📂 {cluster_name} cluster...")

        for handle in handles:
            channel_id = channel_id_cache.get(handle)
            if not channel_id:
                continue

            # Fetch videos
            try:
                # OPTIMIZATION 1: Check playlist cache first
                playlist_id = playlist_cache.get(channel_id)

                if not playlist_id:
                    # Cache miss - fetch and cache playlist ID with rate limiting
                    @(rate_limiter.rate_limit_youtube_api if rate_limiter else lambda f: f)
                    def _get_playlist():
                        return youtube.channels().list(id=channel_id, part='contentDetails').execute()

                    res = _get_playlist()
                    quota_tracker.log_youtube_api_call(1, f"get playlist for {handle}")

                    if 'items' not in res or len(res['items']) == 0:
                        continue

                    playlist_id = res['items'][0]['contentDetails']['relatedPlaylists']['uploads']
                    playlist_cache[channel_id] = playlist_id
                    cache_updated = True

                # Get videos from playlist
                videos = []
                page_token = None

                # OPTIMIZATION 2: Reduced from 5 to 2 pages (100 videos max per channel per month)
                for _ in range(2):  # Max 2 pages (100 videos) per channel per period
                    @(rate_limiter.rate_limit_youtube_api if rate_limiter else lambda f: f)
                    def _get_playlist_items():
                        return youtube.playlistItems().list(
                            playlistId=playlist_id,
                            part='snippet',
                            maxResults=50,
                            pageToken=page_token
                        ).execute()

                    res = _get_playlist_items()
                    quota_tracker.log_youtube_api_call(1, f"get videos from {handle}")

                    for item in res['items']:
                        if item['snippet']['title'] in ["Private video", "Deleted video"]:
                            continue

                        publish_date = item['snippet']['publishedAt']

                        # Filter by date range
                        if publish_date < published_after or publish_date >= published_before:
                            continue

                        videos.append({
                            "video_id": item['snippet']['resourceId']['videoId'],
                            "title": item['snippet']['title'],
                            "publish_date": publish_date,
                            "channel_name": handle,
                            "url": f"https://www.youtube.com/watch?v={item['snippet']['resourceId']['videoId']}",
                            "cluster": cluster_name
                        })

                    page_token = res.get('nextPageToken')
                    if not page_token:
                        break

                if videos:
                    all_videos.extend(videos)

            except Exception as e:
                logger.warning(f"Error fetching {handle}: {e}")
                continue

    # Save playlist cache if updated
    if cache_updated:
        save_playlist_cache(playlist_cache)

    # Save collected data
    if all_videos:
        import pandas as pd
        df = pd.DataFrame(all_videos)
        df['run_timestamp'] = datetime.now(timezone.utc).isoformat()

        # Save to dated directory
        snapshot_dir = Path("data/historical") / start_date
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        output_file = snapshot_dir / "cluster_data.csv"
        df.to_csv(output_file, index=False)

        logger.info(f"  ✅ Saved {len(all_videos)} videos to {output_file}")

    return len(all_videos)


def run_incremental_collection(start_year: int, end_year: int, max_periods_per_run: int = 10):
    """
    Run incremental collection with quota limits and progress tracking.

    Args:
        start_year: Starting year (e.g., 2020)
        end_year: Ending year (e.g., 2025)
        max_periods_per_run: Maximum periods to collect in one run
    """
    # Setup
    load_dotenv()
    config = load_config()
    logger = setup_logger("incremental-collection", level=logging.INFO)
    quota_tracker = QuotaTracker(logger)

    API_KEY = os.getenv("YOUTUBE_API_KEY")
    if not API_KEY:
        logger.error("YOUTUBE_API_KEY not found in .env")
        return

    youtube = build('youtube', 'v3', developerKey=API_KEY)

    # Initialize rate limiter for YouTube API
    rate_limiter = YouTubeAPIRateLimiter(config, quota_tracker, logger)

    # Load clusters and channel cache
    with open(config.paths.cluster_config, 'r') as f:
        clusters = json.load(f)

    cache_path = config.ingest.channel_id_cache_path
    if not os.path.exists(cache_path):
        logger.error("Channel ID cache not found. Run ingest.py first.")
        return

    with open(cache_path, 'r') as f:
        channel_id_cache = json.load(f)

    # Load progress and playlist cache
    progress = load_progress()
    playlist_cache = load_playlist_cache()

    logger.info("="*70)
    logger.info("📊 INCREMENTAL HISTORICAL DATA COLLECTION (OPTIMIZED)")
    logger.info("="*70)
    logger.info(f"Playlist cache: {len(playlist_cache)} channels cached")
    logger.info(f"Target Period: {start_year}-{end_year}")
    logger.info(f"Previously completed: {len(progress['completed_periods'])} periods")
    logger.info(f"Total videos collected so far: {progress['total_videos_collected']}")
    logger.info("="*70)

    # Generate all periods
    all_periods = generate_monthly_periods(start_year, end_year)

    # Filter out already completed
    pending_periods = [
        (start, end) for start, end in all_periods
        if not period_already_collected(start, progress)
    ]

    logger.info(f"\n📅 Status:")
    logger.info(f"  Total periods: {len(all_periods)}")
    logger.info(f"  Completed: {len(progress['completed_periods'])}")
    logger.info(f"  Pending: {len(pending_periods)}")
    logger.info(f"  Will collect in this run: {min(max_periods_per_run, len(pending_periods))}")

    if not pending_periods:
        logger.info("\n✅ All periods already collected!")
        return

    # Collect up to max_periods_per_run
    periods_to_collect = pending_periods[:max_periods_per_run]

    total_videos_this_run = 0

    for i, (start_date, end_date) in enumerate(periods_to_collect, 1):
        logger.info(f"\n[{i}/{len(periods_to_collect)}] Collecting {start_date} to {end_date}")

        # Check quota before continuing
        if quota_tracker.youtube_units_used > QUOTA_SAFETY_LIMIT:
            logger.warning(f"\n⚠️  Approaching quota limit ({quota_tracker.youtube_units_used} units used)")
            logger.warning(f"   Stopping gracefully. Resume tomorrow!")
            break

        try:
            num_videos = collect_single_period(
                youtube, channel_id_cache, playlist_cache, clusters,
                start_date, end_date,
                logger, quota_tracker, rate_limiter
            )

            # Mark as completed
            progress["completed_periods"].append(start_date)
            progress["total_videos_collected"] += num_videos
            total_videos_this_run += num_videos

            logger.info(f"  Videos this period: {num_videos}")
            logger.info(f"  Quota used so far: {quota_tracker.youtube_units_used} units")

        except Exception as e:
            logger.error(f"  Failed to collect {start_date}: {e}")
            progress["failed_periods"].append({
                "period": start_date,
                "error": str(e)
            })

        # Save progress after each period
        progress["last_run"] = datetime.now(timezone.utc).isoformat()
        save_progress(progress)

    # Final summary
    logger.info("\n" + "="*70)
    logger.info("📊 COLLECTION RUN SUMMARY")
    logger.info("="*70)
    logger.info(f"Videos collected this run: {total_videos_this_run}")
    logger.info(f"Periods completed this run: {len(periods_to_collect)}")
    logger.info(f"Total periods completed: {len(progress['completed_periods'])}/{len(all_periods)}")
    logger.info(f"Total videos collected (all time): {progress['total_videos_collected']}")
    logger.info(f"Quota used this run: {quota_tracker.youtube_units_used} units")

    remaining = len(pending_periods) - len(periods_to_collect)

    # Create status dashboard
    dashboard_path = create_status_dashboard(
        progress,
        len(all_periods),
        total_videos_this_run,
        quota_tracker.youtube_units_used
    )
    logger.info(f"\n📊 Status dashboard updated: {dashboard_path}")

    # Send notification
    if remaining > 0:
        logger.info(f"\n📌 {remaining} periods remaining")
        logger.info(f"   Run this script again tomorrow to continue!")

        # Notification for partial completion
        send_notification(
            "Vibes Tracker Collection",
            f"✅ Collected {total_videos_this_run} videos from {len(periods_to_collect)} periods. {remaining} periods remaining."
        )
    else:
        logger.info(f"\n✅ All historical data collection COMPLETE!")

        # Notification for full completion
        send_notification(
            "Vibes Tracker Collection Complete! 🎉",
            f"Successfully collected {progress['total_videos_collected']:,} videos across {len(all_periods)} periods!"
        )

    logger.info("="*70)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Incrementally collect historical YouTube data with quota limits'
    )
    parser.add_argument('--start-year', type=int, default=2020,
                       help='Start year (default: 2020)')
    parser.add_argument('--end-year', type=int, default=2025,
                       help='End year (default: 2025)')
    parser.add_argument('--max-periods', type=int, default=10,
                       help='Maximum periods to collect per run (default: 10)')
    parser.add_argument('--reset', action='store_true',
                       help='Reset progress and start from beginning')

    args = parser.parse_args()

    if args.reset:
        if os.path.exists(PROGRESS_FILE):
            os.remove(PROGRESS_FILE)
            print("✓ Progress reset. Starting fresh!")

    run_incremental_collection(args.start_year, args.end_year, args.max_periods)
