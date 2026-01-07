import os
import sys
import argparse
import logging
import pandas as pd
from datetime import datetime, timezone
from tqdm import tqdm

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config_loader import load_config
from src.utils.logger import setup_logger, QuotaTracker
from src.utils.cache_manager import CacheManager
from src.analyze import get_transcript
from src.ingest import ingest_clusters
from src.visualizations.word_clouds import generate_word_cloud

def run_daily_report(target_date_str=None):
    # 1. Setup & Configuration
    load_config() # Reload config if needed
    config = load_config()
    
    # Set target date
    if target_date_str:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    else:
        target_date = datetime.now().date()
        
    target_date_iso = target_date.isoformat()
    
    # Setup Logging
    logger = setup_logger("daily_report", level=logging.INFO)
    quota_tracker = QuotaTracker(logger)
    
    logger.info("="*60)
    logger.info(f"📅 DAILY VIBES REPORT: {target_date_iso}")
    logger.info("="*60)

    # 2. Ingest Data (Ensure we have metadata for the target date)
    # We run ingestion to ensure we haven't missed anything from today
    # We'll use a standard configuration but filter results later
    logger.info("Step 1: Checking for new videos...")
    
    # Load cluster config
    import json
    with open(config.paths.cluster_config, 'r') as f:
        clusters_config = json.load(f)
        
    API_KEY = os.getenv("YOUTUBE_API_KEY")
    if not API_KEY:
        logger.error("No API Key found.")
        return

    # Run ingestion (fetch recent videos)
    # We pass None for metadata_mgr to avoid messing with the global incremental state 
    # if the user wants to keep that separate, or we could use it. 
    # For a daily report, fetching the last 30 videos per channel (default) is usually enough to cover "today".
    df_all = ingest_clusters(clusters_config, API_KEY, config, logger, quota_tracker, incremental=False)
    
    if df_all.empty:
        logger.warning("No videos found during ingestion.")
        return

    # 3. Filter for Target Date
    # Convert publish_date to date object (handling UTC)
    df_all['publish_dt'] = pd.to_datetime(df_all['publish_date']).dt.date
    
    # Filter
    daily_df = df_all[df_all['publish_dt'] == target_date]
    
    count = len(daily_df)
    if count == 0:
        logger.warning(f"No videos found published on {target_date_iso}")
        return
        
    logger.info(f"Found {count} videos published on {target_date_iso}")
    
    # 4. Fetch Transcripts (Token Efficient: No LLM, just raw text)
    logger.info("Step 2: Fetching transcripts (Direct & Token-Free)...")
    
    # Initialize cache manager to store transcripts (avoid re-fetching if run multiple times)
    cache_manager = CacheManager(config.analysis.cache_dir, logger)
    
    cluster_texts = {} # Store big text blob per cluster
    combined_text = []
    
    # Process by cluster
    for cluster in daily_df['cluster'].unique():
        cluster_videos = daily_df[daily_df['cluster'] == cluster]
        cluster_transcripts = []
        
        logger.info(f"  Processing cluster '{cluster}' ({len(cluster_videos)} videos)...")
        
        for _, row in tqdm(cluster_videos.iterrows(), total=len(cluster_videos), leave=False):
            vid = row['video_id']
            # Reuse get_transcript from analyze.py
            # This handles caching automatically
            text = get_transcript(vid, cache_manager, logger)
            
            if text:
                cluster_transcripts.append(text)
                combined_text.append(text)
        
        cluster_texts[cluster] = " ".join(cluster_transcripts)

    # 5. Generate Word Clouds
    logger.info("Step 3: Generating Daily Word Clouds...")
    
    # Create specific directory for daily reports
    report_dir = os.path.join(config.paths.data_dir, "reports", target_date_iso)
    os.makedirs(report_dir, exist_ok=True)
    
    # Override the default FIGURES_DIR in the imported module or just use the full path logic
    # The generate_word_cloud function takes a filename, but saves to FIGURES_DIR (global in that module).
    # We need to be careful. The imported module uses `../figures`.
    # Let's manually set the output path by tricking the filename or modifying the function usage.
    # Actually, let's just use the `generate_word_cloud` function but we might need to move the file after, 
    # OR we can just monkey-patch the FIGURES_DIR in the imported module.
    
    import src.visualizations.word_clouds as wc_module
    wc_module.FIGURES_DIR = report_dir # Redirect output to our report folder
    
    # Combined Cloud
    full_text = " ".join(combined_text)
    if full_text.strip():
        wc_module.generate_word_cloud(
            full_text,
            "daily_combined_transcripts.png",
            f"Daily Content: {target_date_iso}"
        )
    else:
        logger.warning("No transcript text available for combined cloud.")

    # Cluster Clouds
    for cluster, text in cluster_texts.items():
        if text.strip():
            wc_module.generate_word_cloud(
                text,
                f"daily_{cluster}_transcripts.png",
                f"Daily {cluster.title()}: {target_date_iso}"
            )

    logger.info("="*60)
    logger.info(f"✅ REPORT COMPLETE")
    logger.info(f"📂 Output saved to: {report_dir}")
    logger.info(f"📊 Stats:")
    logger.info(f"   - Videos processed: {count}")
    logger.info(f"   - Clusters covered: {len(cluster_texts)}")
    logger.info("="*60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate Daily Vibes Report')
    parser.add_argument('--date', type=str, help='Target date (YYYY-MM-DD), defaults to today', default=None)
    args = parser.parse_args()
    
    run_daily_report(args.date)
