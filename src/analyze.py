import os
import sys
import json
import logging
import pandas as pd
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
from google.genai import types
from dotenv import load_dotenv
from tqdm import tqdm

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config_loader import load_config
from src.utils.logger import setup_logger, QuotaTracker
from src.utils.cache_manager import CacheManager
from src.utils.metadata_manager import MetadataManager
from src.temporal_analysis import save_historical_snapshot

# --- Core Functions ---

def get_transcript(video_id, cache_manager, logger):
    """Fetches the full transcript text for a given video ID."""
    # Check cache first
    cached_transcript = cache_manager.get_transcript(video_id)
    if cached_transcript:
        return cached_transcript

    # Fetch from YouTube
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        # Combine list of dictionaries into one big string
        full_text = " ".join([t['text'] for t in transcript_list])

        # Save to cache
        cache_manager.save_transcript(video_id, full_text)
        return full_text
    except Exception as e:
        # Transcript might be disabled or unavailable
        logger.debug(f"Transcript unavailable for {video_id}: {e}")
        return None

def analyze_transcript(client, video_id, video_title, transcript, cache_manager, config, logger, quota_tracker, cluster="unknown"):
    """Sends the transcript to Gemini 1.5 Flash for theme and sentiment analysis."""

    # Check cache first
    cached_analysis = cache_manager.get_analysis(video_id)
    if cached_analysis:
        return json.dumps(cached_analysis['data'])

    # Enhanced JSON schema with more fields
    response_schema = {
        "type": "object",
        "properties": {
            "core_themes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "A list of 3 to 5 core topics or themes discussed in the video"
            },
            "theme_categories": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["Political Issues", "Social Issues", "Economic Topics", "Cultural Topics", "International Affairs", "Technology & Science", "Other"]
                },
                "description": "Category for each theme in the same order"
            },
            "overall_sentiment": {
                "type": "string",
                "enum": ["Positive", "Neutral", "Negative", "Mixed"],
                "description": "The dominant emotional tone of the discussion"
            },
            "framing": {
                "type": "string",
                "enum": ["favorable", "critical", "neutral", "alarmist"],
                "description": "How the primary topic is presented"
            },
            "named_entities": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Key people, organizations, or events mentioned (up to 5)"
            },
            "one_sentence_summary": {
                "type": "string",
                "description": "A single, concise sentence summarizing the main takeaway"
            }
        },
        "required": ["core_themes", "theme_categories", "overall_sentiment", "framing", "named_entities", "one_sentence_summary"]
    }

    # Enhanced prompt with better instructions
    prompt = f"""
You are analyzing a YouTube video transcript to extract key themes, sentiment, and narrative framing.

Video Title: "{video_title}"
Channel Cluster: {cluster}

Please analyze the transcript carefully and extract the following information:

1. **Core Themes**: Identify 3-5 main topics or themes discussed (e.g., "Immigration Policy", "Economic Inequality", "Climate Change Action")

2. **Theme Categories**: Categorize each theme into one of these types:
   - Political Issues (elections, policy, governance)
   - Social Issues (culture, identity, social movements)
   - Economic Topics (markets, employment, inequality)
   - Cultural Topics (media, entertainment, values)
   - International Affairs (foreign policy, global events)
   - Technology & Science
   - Other

3. **Overall Sentiment**: The dominant emotional tone (Positive, Neutral, Negative, or Mixed)

4. **Framing**: How is the primary topic presented?
   - favorable (supportive, promotional tone)
   - critical (opposition, critique)
   - neutral (balanced, informative)
   - alarmist (crisis framing, urgent warnings)

5. **Named Entities**: Key people, organizations, or events mentioned (up to 5)

6. **One-Sentence Summary**: A concise summary of the main message

Follow the JSON schema provided exactly.

Transcript:
---
{transcript}
---
"""

    try:
        quota_tracker.log_gemini_api_call(f"analyze {video_title}")
        response = client.models.generate_content(
            model=config.analysis.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema
            )
        )
        # The response.text is already a valid JSON string
        result_json = response.text

        # Save to cache
        try:
            result_data = json.loads(result_json)
            cache_manager.save_analysis(video_id, result_data)
        except json.JSONDecodeError:
            logger.warning(f"Could not cache analysis for {video_id}: invalid JSON")

        return result_json

    except Exception as e:
        logger.error(f"LLM Error for {video_id}: {e}")
        return None


def process_video(row, client, cache_manager, config, logger, quota_tracker):
    """Worker function to process a single video (fetch transcript + analyze)."""
    video_id = row['video_id']
    video_title = row['title']
    cluster = row.get('cluster', 'unknown')

    result = {
        'video_id': video_id,
        'summary': None,
        'themes': None,
        'sentiment': None,
        'framing': None,
        'theme_categories': None,
        'named_entities': None
    }

    # 1. Get Transcript
    transcript = get_transcript(video_id, cache_manager, logger) if cache_manager else get_transcript_no_cache(video_id, logger)
    if not transcript or len(transcript) < 100:
        return result

    # 2. Analyze with Gemini
    analysis_json = analyze_transcript(client, video_id, video_title, transcript, cache_manager, config, logger, quota_tracker, cluster) if cache_manager else analyze_transcript_no_cache(client, video_id, video_title, transcript, config, logger, quota_tracker, cluster)

    if analysis_json:
        try:
            data = json.loads(analysis_json)
            result['summary'] = data.get('one_sentence_summary')
            result['sentiment'] = data.get('overall_sentiment')
            result['framing'] = data.get('framing')
            result['themes'] = " | ".join(data.get('core_themes', []))
            result['theme_categories'] = " | ".join(data.get('theme_categories', []))
            result['named_entities'] = " | ".join(data.get('named_entities', []))
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse Gemini JSON response for {video_id}")

    return result


def run_analysis():
    """Main function to orchestrate the transcript fetching and AI analysis."""
    import argparse

    # Parse CLI arguments
    parser = argparse.ArgumentParser(description='Run AI analysis on video transcripts')
    parser.add_argument('--incremental', action='store_true', help='Only analyze new videos since last run')
    parser.add_argument('--full-refresh', action='store_true', help='Analyze all videos (disable incremental mode)')
    parser.add_argument('--workers', type=int, default=10, help='Number of parallel workers (default: 10)')
    args = parser.parse_args()

    # Change to project root if running from src/
    if os.path.basename(os.getcwd()) == 'src':
        os.chdir('..')

    # Load environment and configuration
    load_dotenv()
    config = load_config()

    # Setup logger, metadata manager, and tools
    logger = setup_logger("analyze", level=logging.INFO)
    quota_tracker = QuotaTracker(logger)
    cache_manager = CacheManager(config.analysis.cache_dir, logger) if config.analysis.enable_caching else None
    metadata_mgr = MetadataManager(logger=logger)

    logger.info("="*60)
    logger.info("YouTube Vibes Tracker - AI Analysis")
    logger.info("="*60)

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not found in .env. Please check your file.")
        return

    # Initialize the Gemini Client
    client = genai.Client(api_key=GEMINI_API_KEY)

    try:
        df = pd.read_csv(config.paths.cluster_data)
    except FileNotFoundError:
        logger.error(f"Input data file not found at {config.paths.cluster_data}. Run ingest.py first.")
        return

    # Determine incremental mode
    incremental_mode = args.incremental or (not args.full_refresh and metadata_mgr.should_run_incremental("analysis"))

    # Filter to only new videos if incremental mode
    if incremental_mode:
        last_run = metadata_mgr.get_last_analysis_timestamp()
        if last_run:
            logger.info(f"🔄 Incremental mode: Only analyzing videos newer than {last_run}")
            original_count = len(df)
            df = df[df['run_timestamp'] > last_run] if 'run_timestamp' in df.columns else df
            logger.info(f"Filtered to {len(df)} new videos (was {original_count})")
        else:
            logger.info("First run - incremental mode disabled, analyzing all videos")
            incremental_mode = False
    else:
        logger.info("Mode: FULL REFRESH (all videos)")

    logger.info(f"Starting AI Analysis for {len(df)} videos with {args.workers} parallel workers...")
    if cache_manager:
        logger.info(f"Caching enabled at {config.analysis.cache_dir}")

    # Process videos in parallel
    results = {}
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Submit all videos for processing
        future_to_row = {
            executor.submit(process_video, row, client, cache_manager, config, logger, quota_tracker): row
            for _, row in df.iterrows()
        }

        # Process results as they complete with progress bar
        for future in tqdm(as_completed(future_to_row), total=len(df), desc="Analyzing videos"):
            row = future_to_row[future]
            try:
                result = future.result()
                results[result['video_id']] = result
            except Exception as e:
                logger.error(f"Error processing video {row['video_id']}: {e}")
                results[row['video_id']] = {
                    'video_id': row['video_id'],
                    'summary': None,
                    'themes': None,
                    'sentiment': None,
                    'framing': None,
                    'theme_categories': None,
                    'named_entities': None
                }

    # Map results back to dataframe
    df['summary'] = df['video_id'].map(lambda vid: results.get(vid, {}).get('summary'))
    df['themes'] = df['video_id'].map(lambda vid: results.get(vid, {}).get('themes'))
    df['sentiment'] = df['video_id'].map(lambda vid: results.get(vid, {}).get('sentiment'))
    df['framing'] = df['video_id'].map(lambda vid: results.get(vid, {}).get('framing'))
    df['theme_categories'] = df['video_id'].map(lambda vid: results.get(vid, {}).get('theme_categories'))
    df['named_entities'] = df['video_id'].map(lambda vid: results.get(vid, {}).get('named_entities'))
    df['analysis_timestamp'] = datetime.now(timezone.utc).isoformat()

    # In incremental mode, merge with existing data
    output_path = config.paths.analyzed_data
    if incremental_mode and os.path.exists(output_path):
        logger.info("Merging with existing analysis data...")
        existing_df = pd.read_csv(output_path)

        # Update existing rows and add new ones
        existing_df = existing_df[~existing_df['video_id'].isin(df['video_id'])]
        df = pd.concat([existing_df, df], ignore_index=True)
        logger.info(f"Combined dataset: {len(df)} total videos")

    # Save results
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)

    # Count successfully analyzed videos
    num_analyzed = df['summary'].notna().sum()

    logger.info(f"Analysis Complete! Saved enriched data to {output_path}")
    logger.info(f"Successfully analyzed: {num_analyzed}/{len(df)} videos")
    logger.info(f"\nSample Enriched Output:\n{df[['cluster', 'title', 'themes', 'sentiment']].head()}")

    # Update metadata
    metadata_mgr.update_analysis(len(df), num_analyzed)

    # Save historical snapshot for temporal analysis
    save_historical_snapshot(config, logger)

    # Log statistics
    if cache_manager:
        cache_manager.log_cache_stats()
    quota_tracker.log_summary()

    # Log pipeline stats
    stats = metadata_mgr.get_stats()
    logger.info(f"\n📊 Pipeline Stats:")
    logger.info(f"   Total analyzed: {stats['total_videos_analyzed']} videos")
    logger.info(f"   Total runs: {stats['total_runs']}")

    logger.info("="*60)


def get_transcript_no_cache(video_id, logger):
    """Fallback for when caching is disabled."""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([t['text'] for t in transcript_list])
    except Exception as e:
        logger.debug(f"Transcript unavailable for {video_id}: {e}")
        return None


def analyze_transcript_no_cache(client, video_id, video_title, transcript, config, logger, quota_tracker, cluster="unknown"):
    """Fallback for when caching is disabled."""
    response_schema = {
        "type": "object",
        "properties": {
            "core_themes": {"type": "array", "items": {"type": "string"}},
            "theme_categories": {"type": "array", "items": {"type": "string"}},
            "overall_sentiment": {"type": "string", "enum": ["Positive", "Neutral", "Negative", "Mixed"]},
            "framing": {"type": "string", "enum": ["favorable", "critical", "neutral", "alarmist"]},
            "named_entities": {"type": "array", "items": {"type": "string"}},
            "one_sentence_summary": {"type": "string"}
        },
        "required": ["core_themes", "theme_categories", "overall_sentiment", "framing", "named_entities", "one_sentence_summary"]
    }

    prompt = f"""
You are analyzing a YouTube video transcript to extract key themes, sentiment, and narrative framing.

Video Title: "{video_title}"
Channel Cluster: {cluster}

Please analyze the transcript carefully and extract:
1. Core Themes (3-5 main topics)
2. Theme Categories (Political Issues, Social Issues, Economic Topics, Cultural Topics, International Affairs, Technology & Science, Other)
3. Overall Sentiment (Positive, Neutral, Negative, Mixed)
4. Framing (favorable, critical, neutral, alarmist)
5. Named Entities (key people, organizations, events - up to 5)
6. One-Sentence Summary

Follow the JSON schema provided exactly.

Transcript:
---
{transcript}
---
"""

    try:
        quota_tracker.log_gemini_api_call(f"analyze {video_title}")
        response = client.models.generate_content(
            model=config.analysis.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema
            )
        )
        return response.text
    except Exception as e:
        logger.error(f"LLM Error for {video_id}: {e}")
        return None


if __name__ == "__main__":
    run_analysis()