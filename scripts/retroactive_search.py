#!/usr/bin/env python3
"""
Retroactive Transcript Search

Builds a dataset for a given channel by:
1. Checking for existing transcripts in /data/{channel}/ folder
2. Slowly fetching missing transcripts over time
3. Saving transcripts one at a time to preserve data if API ban happens
4. Resumable - can be stopped and restarted without losing progress

Usage:
    python scripts/retroactive_search.py --channel @joerogan --start-year 2020 --end-year 2023
    python scripts/retroactive_search.py --channel @joerogan --start-date 2020-01-01 --end-date 2023-12-31
    python scripts/retroactive_search.py --channel @joerogan --start-year 2020 --end-year 2023 --max-per-run 50
"""

import os
import sys
import json
import logging
import argparse
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from googleapiclient.discovery import build
from tqdm import tqdm

from src.utils.config_loader import load_config
from src.utils.logger import setup_logger, QuotaTracker
from src.utils.cache_manager import CacheManager
from src.utils.rate_limiter import YouTubeAPIRateLimiter, TranscriptRateLimiter
from src.analyze import get_transcript


class RetroactiveSearchManager:
    """Manages retroactive transcript collection for a single channel."""

    def __init__(self, channel_handle: str, output_dir: str, config, logger, quota_tracker):
        """
        Initialize the retroactive search manager.

        Args:
            channel_handle: Channel handle (e.g., "@joerogan")
            output_dir: Base directory for storing transcripts (e.g., "data")
            config: Configuration object
            logger: Logger instance
            quota_tracker: QuotaTracker instance
        """
        self.channel_handle = channel_handle
        self.config = config
        self.logger = logger
        self.quota_tracker = quota_tracker

        # Set up directory structure
        self.channel_dir = Path(output_dir) / channel_handle.lstrip('@')
        self.channel_dir.mkdir(parents=True, exist_ok=True)

        # File paths
        self.index_file = self.channel_dir / "index.csv"
        self.progress_file = self.channel_dir / "progress.json"
        self.video_list_file = self.channel_dir / "video_list.json"

        # Initialize managers
        self.cache_manager = CacheManager(config.analysis.cache_dir, logger)
        self.transcript_limiter = TranscriptRateLimiter(config, logger)

        self.logger.info(f"Initialized RetroactiveSearchManager for {channel_handle}")
        self.logger.info(f"Output directory: {self.channel_dir}")

    def load_progress(self) -> Dict:
        """Load progress from file."""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {
            "last_run": None,
            "videos_processed": 0,
            "videos_downloaded": 0,
            "videos_failed": 0,
            "last_video_id": None
        }

    def save_progress(self, progress: Dict):
        """Save progress to file."""
        progress["last_run"] = datetime.now(timezone.utc).isoformat()
        with open(self.progress_file, 'w') as f:
            json.dump(progress, f, indent=2)

    def check_existing_transcripts(self) -> Dict[str, str]:
        """
        Check for existing transcripts in the channel directory.

        Returns:
            Dictionary mapping video_id to filename
        """
        existing = {}

        # Check index file
        if self.index_file.exists():
            try:
                df = pd.read_csv(self.index_file)
                if 'video_id' in df.columns and 'filename' in df.columns:
                    for _, row in df.iterrows():
                        if pd.notna(row['filename']):
                            file_path = self.channel_dir / row['filename']
                            if file_path.exists():
                                existing[row['video_id']] = row['filename']
                    self.logger.info(f"Found {len(existing)} existing transcripts in index")
            except Exception as e:
                self.logger.warning(f"Could not read index file: {e}")

        # Also check for files directly
        for file_path in self.channel_dir.glob("*.txt"):
            # Extract video_id from filename (format: YYYY-MM-DD_VIDEO_ID.txt)
            parts = file_path.stem.split('_')
            if len(parts) >= 2:
                video_id = parts[-1]  # Last part is video_id
                if video_id not in existing:
                    existing[video_id] = file_path.name

        return existing

    def resolve_channel_id(self, youtube, rate_limiter) -> Optional[str]:
        """
        Resolve channel handle to channel ID.

        Args:
            youtube: YouTube API client
            rate_limiter: Rate limiter for YouTube API

        Returns:
            Channel ID or None if not found
        """
        # Check cache first
        cache_path = self.config.ingest.channel_id_cache_path
        if os.path.exists(cache_path):
            with open(cache_path, 'r') as f:
                cache = json.load(f)
                if self.channel_handle in cache:
                    self.logger.info(f"Found channel ID in cache: {cache[self.channel_handle]}")
                    return cache[self.channel_handle]

        # Resolve via API
        self.logger.info(f"Resolving channel ID for {self.channel_handle}...")
        try:
            @rate_limiter.rate_limit_youtube_api
            def _search_channel():
                return youtube.search().list(
                    part="snippet",
                    type="channel",
                    q=self.channel_handle,
                    maxResults=1
                ).execute()

            res = _search_channel()
            self.quota_tracker.log_youtube_api_call(100, f"search for {self.channel_handle}")

            if res.get('items'):
                channel_id = res['items'][0]['snippet']['channelId']
                self.logger.info(f"Found channel ID: {channel_id}")

                # Save to cache
                cache = {}
                if os.path.exists(cache_path):
                    with open(cache_path, 'r') as f:
                        cache = json.load(f)
                cache[self.channel_handle] = channel_id
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                with open(cache_path, 'w') as f:
                    json.dump(cache, f, indent=2)

                return channel_id
            else:
                self.logger.error(f"Channel not found: {self.channel_handle}")
                return None
        except Exception as e:
            self.logger.error(f"Error resolving channel: {e}")
            return None

    def fetch_video_list(self, youtube, channel_id: str, start_date: str, end_date: str, rate_limiter) -> List[Dict]:
        """
        Fetch list of videos from the channel in the date range.

        Args:
            youtube: YouTube API client
            channel_id: Channel ID
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            rate_limiter: Rate limiter for YouTube API

        Returns:
            List of video dictionaries
        """
        # Check if video list already exists
        if self.video_list_file.exists():
            self.logger.info(f"Loading video list from cache: {self.video_list_file}")
            with open(self.video_list_file, 'r') as f:
                videos = json.load(f)
            self.logger.info(f"Loaded {len(videos)} videos from cache")
            return videos

        self.logger.info(f"Fetching video list from YouTube ({start_date} to {end_date})...")

        # Get uploads playlist ID
        try:
            @rate_limiter.rate_limit_youtube_api
            def _get_uploads_playlist():
                return youtube.channels().list(
                    id=channel_id,
                    part='contentDetails'
                ).execute()

            res = _get_uploads_playlist()
            self.quota_tracker.log_youtube_api_call(1, f"get uploads playlist for {self.channel_handle}")

            if not res.get('items'):
                self.logger.error("Channel not found")
                return []

            playlist_id = res['items'][0]['contentDetails']['relatedPlaylists']['uploads']

            # Fetch videos with pagination
            videos = []
            page_token = None
            published_after = f"{start_date}T00:00:00Z"
            published_before = f"{end_date}T23:59:59Z"

            while True:
                @rate_limiter.rate_limit_youtube_api
                def _get_playlist_items():
                    return youtube.playlistItems().list(
                        playlistId=playlist_id,
                        part='snippet',
                        maxResults=50,
                        pageToken=page_token
                    ).execute()

                res = _get_playlist_items()
                self.quota_tracker.log_youtube_api_call(1, f"get videos from {self.channel_handle}")

                for item in res['items']:
                    title = item['snippet']['title']
                    if title in ["Private video", "Deleted video"]:
                        continue

                    publish_date = item['snippet']['publishedAt']

                    # Filter by date range
                    if publish_date < published_after or publish_date > published_before:
                        continue

                    videos.append({
                        "video_id": item['snippet']['resourceId']['videoId'],
                        "title": title,
                        "publish_date": publish_date,
                        "channel_name": self.channel_handle,
                        "url": f"https://www.youtube.com/watch?v={item['snippet']['resourceId']['videoId']}"
                    })

                page_token = res.get('nextPageToken')
                if not page_token:
                    break

                self.logger.info(f"Fetched {len(videos)} videos so far...")

            # Save video list to cache
            self.logger.info(f"Saving {len(videos)} videos to cache: {self.video_list_file}")
            with open(self.video_list_file, 'w') as f:
                json.dump(videos, f, indent=2)

            return videos

        except Exception as e:
            self.logger.error(f"Error fetching video list: {e}")
            return []

    def download_transcript(self, video_id: str, title: str, publish_date: str) -> tuple[Optional[str], str]:
        """
        Download a single transcript and save it immediately.

        Args:
            video_id: Video ID
            title: Video title
            publish_date: Publish date

        Returns:
            Tuple of (filename, status) where status is 'downloaded', 'exists', or 'failed'
        """
        # Generate filename
        date_str = publish_date.split('T')[0]
        filename = f"{date_str}_{video_id}.txt"
        file_path = self.channel_dir / filename

        # Check if already exists
        if file_path.exists():
            return filename, 'exists'

        # Fetch transcript
        try:
            text = get_transcript(video_id, self.cache_manager, self.logger, self.transcript_limiter)

            if text:
                # Save immediately
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(text)
                self.logger.info(f"✅ Downloaded: {filename}")
                return filename, 'downloaded'
            else:
                self.logger.warning(f"❌ No transcript available: {video_id}")
                return None, 'failed'
        except Exception as e:
            self.logger.error(f"❌ Error downloading {video_id}: {e}")
            return None, 'failed'

    def run_collection(self, start_date: str, end_date: str, max_per_run: Optional[int] = None) -> Dict:
        """
        Run the retroactive collection process.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            max_per_run: Maximum number of transcripts to download per run (None = unlimited)

        Returns:
            Summary statistics dictionary
        """
        self.logger.info("="*70)
        self.logger.info(f"RETROACTIVE TRANSCRIPT COLLECTION: {self.channel_handle}")
        self.logger.info(f"Date Range: {start_date} to {end_date}")
        if max_per_run:
            self.logger.info(f"Max per run: {max_per_run}")
        self.logger.info("="*70)

        # Load progress
        progress = self.load_progress()
        self.logger.info(f"Previous runs: {progress.get('videos_processed', 0)} videos processed")

        # Check for existing transcripts
        existing = self.check_existing_transcripts()
        self.logger.info(f"Found {len(existing)} existing transcripts")

        # Set up YouTube API
        API_KEY = os.getenv("YOUTUBE_API_KEY")
        if not API_KEY:
            self.logger.error("YOUTUBE_API_KEY not found in .env")
            return {}

        youtube = build('youtube', 'v3', developerKey=API_KEY)
        rate_limiter = YouTubeAPIRateLimiter(self.config, self.quota_tracker, self.logger)

        # Resolve channel ID
        channel_id = self.resolve_channel_id(youtube, rate_limiter)
        if not channel_id:
            return {}

        # Fetch video list
        videos = self.fetch_video_list(youtube, channel_id, start_date, end_date, rate_limiter)
        if not videos:
            self.logger.warning("No videos found in date range")
            return {}

        self.logger.info(f"Total videos in range: {len(videos)}")

        # Filter out existing transcripts
        videos_to_download = [v for v in videos if v['video_id'] not in existing]
        self.logger.info(f"Videos needing transcripts: {len(videos_to_download)}")

        if not videos_to_download:
            self.logger.info("✅ All transcripts already downloaded!")
            return {
                "total_videos": len(videos),
                "already_downloaded": len(existing),
                "newly_downloaded": 0,
                "failed": 0
            }

        # Limit if specified
        if max_per_run and len(videos_to_download) > max_per_run:
            self.logger.info(f"Limiting to {max_per_run} videos for this run")
            videos_to_download = videos_to_download[:max_per_run]

        # Download transcripts one at a time
        results = []
        downloaded_count = 0
        failed_count = 0

        self.logger.info(f"\nDownloading {len(videos_to_download)} transcripts...")

        for video in tqdm(videos_to_download, desc="Downloading transcripts"):
            filename, status = self.download_transcript(
                video['video_id'],
                video['title'],
                video['publish_date']
            )

            results.append({
                'video_id': video['video_id'],
                'publish_date': video['publish_date'],
                'title': video['title'],
                'filename': filename,
                'status': status
            })

            if status == 'downloaded':
                downloaded_count += 1
            elif status == 'failed':
                failed_count += 1

            # Update progress after each download
            progress['videos_processed'] = progress.get('videos_processed', 0) + 1
            if status == 'downloaded':
                progress['videos_downloaded'] = progress.get('videos_downloaded', 0) + 1
            elif status == 'failed':
                progress['videos_failed'] = progress.get('videos_failed', 0) + 1
            progress['last_video_id'] = video['video_id']
            self.save_progress(progress)

        # Update index file
        new_df = pd.DataFrame(results)
        if self.index_file.exists():
            existing_df = pd.read_csv(self.index_file)
            final_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=['video_id'], keep='last')
        else:
            final_df = new_df

        final_df.to_csv(self.index_file, index=False)
        self.logger.info(f"\n✅ Updated index: {self.index_file}")

        # Summary
        summary = {
            "total_videos": len(videos),
            "already_downloaded": len(existing),
            "newly_downloaded": downloaded_count,
            "failed": failed_count,
            "remaining": len(videos) - len(existing) - downloaded_count - failed_count
        }

        self.logger.info("\n" + "="*70)
        self.logger.info("COLLECTION SUMMARY")
        self.logger.info("="*70)
        self.logger.info(f"Total videos in date range: {summary['total_videos']}")
        self.logger.info(f"Already downloaded: {summary['already_downloaded']}")
        self.logger.info(f"Newly downloaded: {summary['newly_downloaded']}")
        self.logger.info(f"Failed: {summary['failed']}")
        self.logger.info(f"Remaining: {summary['remaining']}")
        self.logger.info("="*70)

        if summary['remaining'] > 0:
            self.logger.info(f"\n📌 Run this script again to continue downloading remaining transcripts")
        else:
            self.logger.info(f"\n🎉 All transcripts downloaded for {self.channel_handle}!")

        return summary


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Retroactively search and download transcripts for a YouTube channel'
    )
    parser.add_argument('--channel', type=str, required=True,
                       help='Channel handle (e.g., @joerogan)')
    parser.add_argument('--start-date', type=str,
                       help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str,
                       help='End date (YYYY-MM-DD)')
    parser.add_argument('--start-year', type=int,
                       help='Start year (alternative to --start-date)')
    parser.add_argument('--end-year', type=int,
                       help='End year (alternative to --end-date)')
    parser.add_argument('--max-per-run', type=int,
                       help='Maximum number of transcripts to download per run')
    parser.add_argument('--output-dir', type=str, default='data',
                       help='Output directory (default: data)')

    args = parser.parse_args()

    # Determine date range
    if args.start_year and args.end_year:
        start_date = f"{args.start_year}-01-01"
        end_date = f"{args.end_year}-12-31"
    elif args.start_date and args.end_date:
        start_date = args.start_date
        end_date = args.end_date
    else:
        print("Error: Must provide either --start-year/--end-year OR --start-date/--end-date")
        return 1

    # Setup
    load_dotenv()
    config = load_config()
    logger = setup_logger("retroactive-search", level=logging.INFO)
    quota_tracker = QuotaTracker(logger)

    # Run collection
    manager = RetroactiveSearchManager(
        args.channel,
        args.output_dir,
        config,
        logger,
        quota_tracker
    )

    summary = manager.run_collection(start_date, end_date, args.max_per_run)

    # Log quota usage
    quota_tracker.log_summary()

    return 0


if __name__ == '__main__':
    sys.exit(main())
