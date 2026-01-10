import os
import sys
import json
import logging
import pandas as pd
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from youtube_transcript_api import YouTubeTranscriptApi
import requests
from dotenv import load_dotenv
from tqdm import tqdm

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config_loader import load_config
from src.utils.logger import setup_logger, QuotaTracker
from src.utils.cache_manager import CacheManager
from src.utils.metadata_manager import MetadataManager
from src.utils.rate_limiter import TranscriptRateLimiter
from src.temporal_analysis import save_historical_snapshot

# --- Core Functions ---

def get_transcript(video_id, cache_manager, logger, rate_limiter=None):
    """Fetches the full transcript text for a given video ID."""
    # Check cache first
    cached_transcript = cache_manager.get_transcript(video_id)
    if cached_transcript:
        return cached_transcript

    # Fetch from YouTube
    try:
        @(rate_limiter.rate_limit_transcript_fetch if rate_limiter else lambda f: f)
        def _fetch_transcript():
            api = YouTubeTranscriptApi()

            # Use .fetch() with multiple language codes to catch auto-generated or variant English
            # This version of the library (1.2.3) uses .fetch() instead of .get_transcript()
            # and returns a list of snippet objects with a .text attribute.
            transcript_snippets = api.fetch(video_id, languages=['en', 'en-US', 'en-GB'])

            # Combine snippet text
            return " ".join([snippet.text for snippet in transcript_snippets])

        full_text = _fetch_transcript()

        # Save to cache
        cache_manager.save_transcript(video_id, full_text)
        return full_text

    except Exception as e:
        # Transcript might be disabled or unavailable
        logger.error(f"Transcript unavailable for {video_id}: {e}")
        return None

def analyze_transcript(ollama_url, video_id, video_title, transcript, cache_manager, config, logger, quota_tracker, cluster="unknown"):
    """Sends the transcript to Ollama for theme and sentiment analysis."""

    # Check cache first
    cached_analysis = cache_manager.get_analysis(video_id)
    if cached_analysis:
        return json.dumps(cached_analysis['data'])

    # Truncate transcript if too long (some models have context limits)
    max_chars = 8000  # Conservative limit for local models
    if len(transcript) > max_chars:
        transcript = transcript[:max_chars] + "..."

    # Enhanced prompt with JSON output instructions
    prompt = f"""Analyze this YouTube video transcript and respond ONLY with valid JSON in this exact format:

{{
  "core_themes": ["theme1", "theme2", "theme3"],
  "theme_categories": ["Political Issues", "Social Issues"],
  "overall_sentiment": "Neutral",
  "framing": "neutral",
  "named_entities": ["entity1", "entity2"],
  "one_sentence_summary": "Brief summary here"
}}

Video Title: "{video_title}"
Channel Cluster: {cluster}

Instructions:
1. **core_themes**: List 3-5 main topics discussed (e.g., "Immigration Policy", "Climate Change")
2. **theme_categories**: Categorize each theme. Choose from: "Political Issues", "Social Issues", "Economic Topics", "Cultural Topics", "International Affairs", "Technology & Science", "Other"
3. **overall_sentiment**: Choose ONE: "Positive", "Neutral", "Negative", or "Mixed"
4. **framing**: Choose ONE: "favorable", "critical", "neutral", or "alarmist"
5. **named_entities**: List up to 5 key people, organizations, or events mentioned
6. **one_sentence_summary**: A single concise sentence summarizing the main message

Transcript:
{transcript}

Respond ONLY with the JSON object, no other text:"""

    try:
        quota_tracker.log_gemini_api_call(f"analyze {video_title}")

        # Call Ollama API
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": config.analysis.model,
                "prompt": prompt,
                "stream": False,
                "format": "json"
            },
            timeout=120
        )

        if response.status_code != 200:
            logger.error(f"Ollama API error for {video_id}: {response.status_code}")
            return None

        result = response.json()
        result_json = result.get('response', '')

        # Validate JSON
        try:
            result_data = json.loads(result_json)

            # Validate required fields
            required = ["core_themes", "theme_categories", "overall_sentiment", "framing", "named_entities", "one_sentence_summary"]
            if not all(key in result_data for key in required):
                logger.warning(f"Incomplete analysis for {video_id}, missing fields")
                return None

            # Save to cache
            cache_manager.save_analysis(video_id, result_data)
            return result_json

        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON from Ollama for {video_id}: {e}")
            logger.debug(f"Response was: {result_json[:200]}")
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"Ollama connection error for {video_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"LLM Error for {video_id}: {e}")
        return None


def process_video(row, ollama_url, cache_manager, config, logger, quota_tracker, transcript_rate_limiter=None):
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
    transcript = get_transcript(video_id, cache_manager, logger, transcript_rate_limiter) if cache_manager else get_transcript_no_cache(video_id, logger)
    if not transcript or len(transcript) < 100:
        return result

    # 2. Analyze with Ollama
    analysis_json = analyze_transcript(ollama_url, video_id, video_title, transcript, cache_manager, config, logger, quota_tracker, cluster) if cache_manager else analyze_transcript_no_cache(ollama_url, video_id, video_title, transcript, config, logger, quota_tracker, cluster)

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
            logger.warning(f"Failed to parse Ollama JSON response for {video_id}")

    return result


def run_analysis():
    """Main function to orchestrate the transcript fetching and AI analysis."""
    import argparse

    # Change to project root if running from src/
    if os.path.basename(os.getcwd()) == 'src':
        os.chdir('..')

    # Load environment and configuration first to get defaults
    load_dotenv()
    config = load_config()

    # Parse CLI arguments
    parser = argparse.ArgumentParser(description='Run AI analysis on video transcripts')
    parser.add_argument('--incremental', action='store_true', help='Only analyze new videos since last run')
    parser.add_argument('--full-refresh', action='store_true', help='Analyze all videos (disable incremental mode)')
    default_workers = config.rate_limiting.batch_operations.max_parallel_workers
    parser.add_argument('--workers', type=int, default=default_workers, help=f'Number of parallel workers (default: {default_workers})')
    args = parser.parse_args()

    # Setup logger, metadata manager, and tools
    logger = setup_logger("analyze", level=logging.INFO)
    quota_tracker = QuotaTracker(logger, daily_limit=config.rate_limiting.youtube_api.daily_quota_limit)
    cache_manager = CacheManager(config.analysis.cache_dir, logger) if config.analysis.enable_caching else None
    metadata_mgr = MetadataManager(logger=logger)

    logger.info("="*60)
    logger.info("YouTube Vibes Tracker - AI Analysis (Ollama)")
    logger.info("="*60)

    # Get Ollama URL from environment or use default
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")

    # Test Ollama connection
    try:
        test_response = requests.get(f"{ollama_url}/api/tags", timeout=5)
        if test_response.status_code == 200:
            models = test_response.json().get('models', [])
            model_names = [m['name'] for m in models]
            logger.info(f"✓ Connected to Ollama at {ollama_url}")
            logger.info(f"  Available models: {', '.join(model_names)}")

            # Check if configured model is available
            if config.analysis.model not in model_names:
                logger.warning(f"⚠️  Model '{config.analysis.model}' not found in Ollama")
                logger.warning(f"   Available models: {', '.join(model_names)}")
                logger.warning(f"   Please run: ollama pull {config.analysis.model}")
                return
        else:
            logger.error(f"Failed to connect to Ollama at {ollama_url}")
            return
    except requests.exceptions.RequestException as e:
        logger.error(f"Cannot connect to Ollama at {ollama_url}: {e}")
        logger.error("Please ensure Ollama is running: ollama serve")
        return

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

    # Initialize transcript rate limiter
    transcript_rate_limiter = TranscriptRateLimiter(config, logger)

    # Process videos in parallel
    results = {}
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Submit all videos for processing
        future_to_row = {
            executor.submit(process_video, row, ollama_url, cache_manager, config, logger, quota_tracker, transcript_rate_limiter): row
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
        api = YouTubeTranscriptApi()
        transcript_list = api.fetch(video_id)
        return " ".join([snippet.text for snippet in transcript_list])
    except Exception as e:
        logger.debug(f"Transcript unavailable for {video_id}: {e}")
        return None


def analyze_transcript_no_cache(ollama_url, video_id, video_title, transcript, config, logger, quota_tracker, cluster="unknown"):
    """Fallback for when caching is disabled - uses Ollama."""
    # Truncate transcript if too long
    max_chars = 8000
    if len(transcript) > max_chars:
        transcript = transcript[:max_chars] + "..."

    prompt = f"""Analyze this YouTube video transcript and respond ONLY with valid JSON in this exact format:

{{
  "core_themes": ["theme1", "theme2", "theme3"],
  "theme_categories": ["Political Issues", "Social Issues"],
  "overall_sentiment": "Neutral",
  "framing": "neutral",
  "named_entities": ["entity1", "entity2"],
  "one_sentence_summary": "Brief summary here"
}}

Video Title: "{video_title}"
Channel Cluster: {cluster}

Instructions:
1. **core_themes**: List 3-5 main topics discussed
2. **theme_categories**: Choose from: "Political Issues", "Social Issues", "Economic Topics", "Cultural Topics", "International Affairs", "Technology & Science", "Other"
3. **overall_sentiment**: Choose ONE: "Positive", "Neutral", "Negative", or "Mixed"
4. **framing**: Choose ONE: "favorable", "critical", "neutral", or "alarmist"
5. **named_entities**: List up to 5 key people, organizations, or events
6. **one_sentence_summary**: A single concise sentence

Transcript:
{transcript}

Respond ONLY with the JSON object, no other text:"""

    try:
        quota_tracker.log_gemini_api_call(f"analyze {video_title}")
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": config.analysis.model,
                "prompt": prompt,
                "stream": False,
                "format": "json"
            },
            timeout=120
        )
        if response.status_code == 200:
            result = response.json()
            return result.get('response', '')
        return None
    except Exception as e:
        logger.error(f"LLM Error for {video_id}: {e}")
        return None


if __name__ == "__main__":
    run_analysis()