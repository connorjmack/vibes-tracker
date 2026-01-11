#!/usr/bin/env python3
"""
QUOTA-FREE Data Collection using YouTube RSS Feeds

This script collects video data WITHOUT using any API quota:
- Uses RSS feeds to discover videos (NO quota)
- Fetches transcripts directly (NO quota)
- Analyzes with Ollama locally (NO quota)

Perfect for ongoing daily monitoring!

Limitation: RSS only shows ~15 most recent videos per channel
Good for: Daily/weekly monitoring, not historical collection
"""

import os
import sys
import json
import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi
from vibes_tracker.utils.config_loader import load_config
from vibes_tracker.utils.logger import setup_logger


def get_channel_id_from_handle(handle: str) -> str:
    """
    Convert @handle to channel_id by checking cache.

    Note: This still requires the channel_id_cache.json file which was
    built once using the Data API. But after that initial setup,
    no more API calls needed!
    """
    cache_path = "data/channel_ids.json"
    if os.path.exists(cache_path):
        with open(cache_path, 'r') as f:
            cache = json.load(f)
            return cache.get(handle)
    return None


def fetch_rss_feed(channel_id: str, logger) -> list:
    """
    Fetch latest videos from YouTube RSS feed (NO API QUOTA).

    Returns:
        List of video dictionaries with id, title, published date
    """
    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

    try:
        response = requests.get(rss_url, timeout=10)

        if response.status_code != 200:
            logger.warning(f"Failed to fetch RSS for {channel_id}: {response.status_code}")
            return []

        # Parse XML
        root = ET.fromstring(response.content)

        # XML namespaces
        ns = {
            'atom': 'http://www.w3.org/2005/Atom',
            'yt': 'http://www.youtube.com/xml/schemas/2015',
            'media': 'http://search.yahoo.com/mrss/'
        }

        # Get channel name
        channel_name = root.find('atom:title', ns).text

        # Get videos
        videos = []
        for entry in root.findall('atom:entry', ns):
            video_id = entry.find('yt:videoId', ns).text
            title = entry.find('atom:title', ns).text
            published = entry.find('atom:published', ns).text

            videos.append({
                'video_id': video_id,
                'title': title,
                'publish_date': published,
                'channel_name': channel_name,
                'url': f'https://www.youtube.com/watch?v={video_id}'
            })

        return videos

    except Exception as e:
        logger.error(f"Error fetching RSS for {channel_id}: {e}")
        return []


def fetch_transcript(video_id: str, logger) -> str:
    """Fetch transcript for a video (NO API QUOTA)."""
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.fetch(video_id)
        full_text = ' '.join([snippet.text for snippet in transcript_list])
        return full_text
    except Exception as e:
        logger.debug(f"No transcript for {video_id}: {e}")
        return None


def analyze_with_ollama(video_id: str, title: str, transcript: str,
                       cluster: str, logger) -> dict:
    """Analyze transcript with Ollama (NO API QUOTA)."""

    if not transcript or len(transcript) < 100:
        return None

    # Truncate if too long
    if len(transcript) > 8000:
        transcript = transcript[:8000] + "..."

    prompt = f"""Analyze this YouTube video transcript and respond ONLY with valid JSON in this exact format:

{{
  "core_themes": ["theme1", "theme2", "theme3"],
  "theme_categories": ["Political Issues", "Social Issues"],
  "overall_sentiment": "Neutral",
  "framing": "neutral",
  "named_entities": ["entity1", "entity2"],
  "one_sentence_summary": "Brief summary here"
}}

Video Title: "{title}"
Channel Cluster: {cluster}

Instructions:
1. **core_themes**: List 3-5 main topics
2. **theme_categories**: Choose from: "Political Issues", "Social Issues", "Economic Topics", "Cultural Topics", "International Affairs", "Technology & Science", "Other"
3. **overall_sentiment**: "Positive", "Neutral", "Negative", or "Mixed"
4. **framing**: "favorable", "critical", "neutral", or "alarmist"
5. **named_entities**: Up to 5 key people, organizations, or events
6. **one_sentence_summary**: A single concise sentence

Transcript:
{transcript}

Respond ONLY with the JSON object:"""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.1:latest",
                "prompt": prompt,
                "stream": False,
                "format": "json"
            },
            timeout=120
        )

        if response.status_code == 200:
            result = response.json()
            analysis_json = result.get('response', '')
            return json.loads(analysis_json)

    except Exception as e:
        logger.error(f"Ollama analysis failed for {video_id}: {e}")

    return None


def run_quota_free_collection():
    """Run completely quota-free collection and analysis."""

    logger = setup_logger("quota-free-collection", level=logging.INFO)
    config = load_config()

    logger.info("="*70)
    logger.info("🆓 QUOTA-FREE DATA COLLECTION")
    logger.info("="*70)
    logger.info("Uses: RSS feeds (free) + Transcripts (free) + Ollama (free)")
    logger.info("Quota used: 0 units")
    logger.info("="*70)

    # Load clusters
    with open(config.paths.cluster_config, 'r') as f:
        clusters = json.load(f)

    all_data = []

    for cluster_name, handles in clusters.items():
        logger.info(f"\n📂 Processing cluster: {cluster_name}")

        for handle in handles:
            # Get channel ID from cache
            channel_id = get_channel_id_from_handle(handle)
            if not channel_id:
                logger.warning(f"  ⚠️  No channel ID for {handle} (run ingest.py once to build cache)")
                continue

            logger.info(f"  📺 {handle}...")

            # Fetch latest videos from RSS (NO QUOTA!)
            videos = fetch_rss_feed(channel_id, logger)
            logger.info(f"     Found {len(videos)} videos from RSS feed")

            # Process each video
            for video in videos:
                video_id = video['video_id']

                # Fetch transcript (NO QUOTA!)
                logger.info(f"     📝 Fetching transcript for {video_id}...")
                transcript = fetch_transcript(video_id, logger)

                if transcript:
                    logger.info(f"        ✅ Got transcript ({len(transcript)} chars)")

                    # Analyze with Ollama (NO QUOTA!)
                    logger.info(f"        🤖 Analyzing with Ollama...")
                    analysis = analyze_with_ollama(
                        video_id,
                        video['title'],
                        transcript,
                        cluster_name,
                        logger
                    )

                    if analysis:
                        # Combine everything
                        all_data.append({
                            **video,
                            'cluster': cluster_name,
                            'transcript': transcript,
                            'summary': analysis.get('one_sentence_summary'),
                            'themes': ' | '.join(analysis.get('core_themes', [])),
                            'sentiment': analysis.get('overall_sentiment'),
                            'framing': analysis.get('framing'),
                            'theme_categories': ' | '.join(analysis.get('theme_categories', [])),
                            'named_entities': ' | '.join(analysis.get('named_entities', [])),
                            'collection_timestamp': datetime.now(timezone.utc).isoformat()
                        })
                        logger.info(f"        ✅ Analysis complete!")
                    else:
                        logger.warning(f"        ⚠️  Analysis failed")
                else:
                    logger.info(f"        ⚠️  No transcript available")

    # Save results
    if all_data:
        import pandas as pd
        df = pd.DataFrame(all_data)

        output_path = "data/quota_free_collection.csv"
        df.to_csv(output_path, index=False)

        logger.info(f"\n✅ COLLECTION COMPLETE!")
        logger.info(f"   Videos processed: {len(all_data)}")
        logger.info(f"   Saved to: {output_path}")
        logger.info(f"   API quota used: 0 units (FREE!)")
        logger.info(f"   Cost: $0.00")

        # Summary by cluster
        logger.info(f"\n📊 Videos by cluster:")
        for cluster, count in df['cluster'].value_counts().items():
            logger.info(f"   {cluster}: {count} videos")
    else:
        logger.warning("No data collected!")

    logger.info("="*70)


if __name__ == '__main__':
    run_quota_free_collection()
