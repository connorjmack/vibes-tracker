import os
import sys
import time
import argparse
import logging
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timezone
from tqdm import tqdm
from dotenv import load_dotenv
from googleapiclient.discovery import build

from vibes_tracker.utils.config_loader import load_config
from vibes_tracker.utils.logger import setup_logger, QuotaTracker
from vibes_tracker.utils.cache_manager import CacheManager
from vibes_tracker.utils.rate_limiter import YouTubeAPIRateLimiter, TranscriptRateLimiter
from vibes_tracker.core.analyze import get_transcript
from vibes_tracker.core.ingest import ingest_clusters
from vibes_tracker.visualizations.word_clouds import generate_word_cloud

def fetch_video_stats(video_ids, api_key, logger, quota_tracker, config):
    """Fetches view counts for a list of video IDs in batches of 50."""
    youtube = build('youtube', 'v3', developerKey=api_key)
    rate_limiter = YouTubeAPIRateLimiter(config, quota_tracker, logger)
    stats_map = {}

    # Process in chunks of 50
    chunk_size = 50
    for i in range(0, len(video_ids), chunk_size):
        chunk = video_ids[i:i+chunk_size]
        try:
            @rate_limiter.rate_limit_youtube_api
            def _fetch_batch():
                quota_tracker.log_youtube_api_call(1, f"get stats for {len(chunk)} videos")
                response = youtube.videos().list(
                    part="statistics",
                    id=",".join(chunk)
                ).execute()
                return response

            response = _fetch_batch()

            for item in response.get('items', []):
                vid = item['id']
                views = int(item['statistics'].get('viewCount', 0))
                stats_map[vid] = views

        except Exception as e:
            logger.error(f"Error fetching stats for chunk: {e}")

        # Add delay between batches to prevent rate limiting
        if i + chunk_size < len(video_ids):
            delay = config.rate_limiting.batch_operations.delay_between_batches
            logger.debug(f"Batch delay: {delay}s before next batch")
            time.sleep(delay)

    return stats_map

def plot_views_by_cluster(df, report_dir, target_date_iso):
    """Plots total views per channel as a stacked bar of individual videos."""
    
    cluster_palettes = {
        'Left': 'Blues_r',
        'right': 'Reds_r',
        'mainstream': 'Purples_r',
        'manosphere': 'Oranges_r',
        'my-env': 'Greens_r'
    }
    
    for cluster in df['cluster'].unique():
        cluster_df = df[df['cluster'] == cluster].copy()
        
        # Sort channels by TOTAL views (Ascending for barh so largest is at top)
        channel_totals = cluster_df.groupby('channel_name')['view_count'].sum().sort_values(ascending=True)
        if channel_totals.empty:
            continue
            
        channels = channel_totals.index.tolist()
        
        # Dynamic height
        plt.figure(figsize=(12, max(4, len(channels) * 0.6 + 1.5)))
        
        # Get base color from palette (using a mid-dark shade)
        palette_name = cluster_palettes.get(cluster, 'viridis')
        try:
            # Try to get a nice color from seaborn
            colors = sns.color_palette(palette_name, n_colors=10)
            base_color = colors[4] # Mid-range color
        except:
            base_color = 'steelblue'

        # Plot each channel
        for i, channel in enumerate(channels):
            # Get videos for this channel, sorted by size
            videos = cluster_df[cluster_df['channel_name'] == channel].sort_values('view_count', ascending=False)
            
            left_offset = 0
            for _, video in videos.iterrows():
                views = video['view_count']
                # Plot segment with white border to show it's a separate video
                plt.barh(i, views, left=left_offset, color=base_color, edgecolor='white', linewidth=1.5)
                left_offset += views
            
            # Label the total
            plt.text(left_offset, i, f" {int(left_offset):,.0f}", va='center', fontweight='bold', fontsize=10)

        plt.title(f"Views by Channel: {cluster.title()} ({target_date_iso})", fontsize=16)
        plt.xlabel("Total Views (Segments = Individual Videos)", fontsize=12)
        plt.yticks(range(len(channels)), channels, fontsize=11)
        
        # Adjust x-axis limits to fit labels
        plt.xlim(right=channel_totals.max() * 1.3)
        plt.tight_layout()
        
        save_path = os.path.join(report_dir, f"views_by_channel_{cluster}.png")
        plt.savefig(save_path, bbox_inches='tight')
        plt.close()

def run_daily_report(target_date_str=None):
    # 1. Setup & Configuration
    load_dotenv()
    load_config() 
    config = load_config()
    
    if target_date_str:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    else:
        target_date = datetime.now().date()
    target_date_iso = target_date.isoformat()
    
    logger = setup_logger("daily_report", level=logging.INFO)
    quota_tracker = QuotaTracker(logger)
    
    logger.info("="*60)
    logger.info(f"📅 DAILY VIBES REPORT: {target_date_iso}")
    logger.info("="*60)

    # 2. Ingest Data
    import json
    with open(config.paths.cluster_config, 'r') as f:
        clusters_config = json.load(f)
        
    API_KEY = os.getenv("YOUTUBE_API_KEY")
    if not API_KEY:
        logger.error("No API Key found.")
        return

    # Ingest metadata
    logger.info("Step 1: Ingesting recent videos...")
    df_all = ingest_clusters(clusters_config, API_KEY, config, logger, quota_tracker, incremental=False)
    
    if df_all.empty:
        logger.warning("No videos found.")
        return

    # Filter for Target Date
    df_all['publish_dt'] = pd.to_datetime(df_all['publish_date']).dt.date
    daily_df = df_all[df_all['publish_dt'] == target_date].copy()
    
    count = len(daily_df)
    if count == 0:
        logger.warning(f"No videos found published on {target_date_iso}")
        return
        
    logger.info(f"Found {count} videos published on {target_date_iso}")

    # 3. Fetch View Counts & Filter
    logger.info("Step 2: Fetching view counts to identify top content...")
    video_ids = daily_df['video_id'].unique().tolist()
    stats = fetch_video_stats(video_ids, API_KEY, logger, quota_tracker, config)
    
    # Map views to dataframe
    daily_df['view_count'] = daily_df['video_id'].map(stats).fillna(0).astype(int)
    
    # Sort by views descending
    daily_df = daily_df.sort_values('view_count', ascending=False)
    
    # Calculate Cumulative Views
    total_views = daily_df['view_count'].sum()
    daily_df['cumulative_views'] = daily_df['view_count'].cumsum()
    daily_df['cumulative_percent'] = daily_df['cumulative_views'] / total_views
    
    # Filter: Keep videos that contribute to the top 67% (2/3) of views
    cutoff_mask = daily_df['cumulative_percent'] <= 0.67
    
    if not cutoff_mask.any():
         # Fallback if just one video dominates > 67%
         filtered_df = daily_df.iloc[:5]
    else:
        last_idx = cutoff_mask[cutoff_mask].index[-1]
        loc = daily_df.index.get_loc(last_idx)
        filtered_df = daily_df.iloc[:loc+1]

    # SAFETY NET: Ensure EVERY cluster is represented
    # If a cluster is missing from the top set (because another cluster dominated views),
    # explicitly add its top 5 videos so we generate charts/clouds for it.
    all_clusters = daily_df['cluster'].unique()
    present_clusters = filtered_df['cluster'].unique()
    missing_clusters = set(all_clusters) - set(present_clusters)
    
    if missing_clusters:
        logger.info(f"⚠️  Adding top videos for missing clusters: {missing_clusters}")
        extras = []
        for cluster in missing_clusters:
            # Get top 5 for this cluster
            top_cluster_vids = daily_df[daily_df['cluster'] == cluster].head(5)
            extras.append(top_cluster_vids)
        
        if extras:
            filtered_df = pd.concat([filtered_df] + extras).drop_duplicates()
    
    logger.info(f"📊 View Stats: Total Views = {total_views:,}")
    logger.info(f"   Filtered to Top {len(filtered_df)} videos (out of {count})")
    
    # Create Report Directory
    report_dir = os.path.join(config.paths.data_dir, "reports", target_date_iso)
    os.makedirs(report_dir, exist_ok=True)
    
    # Plot Distribution (Cluster Specific)
    # Use full daily_df to ensure all channels are represented in the charts, 
    # even if their views didn't make the 67% cutoff for word cloud analysis.
    plot_views_by_cluster(daily_df, report_dir, target_date_iso)
    
    # 4. Fetch Transcripts for Filtered Videos
    logger.info("Step 3: Fetching transcripts for top videos...")
    cache_manager = CacheManager(config.analysis.cache_dir, logger)
    transcript_rate_limiter = TranscriptRateLimiter(config, logger)

    cluster_texts = {}
    combined_text = []
    
    # Identify all unique clusters in the filtered set
    target_clusters = filtered_df['cluster'].unique()
    logger.info(f"Generating reports for clusters: {target_clusters}")
    
    for cluster in target_clusters:
        cluster_videos = filtered_df[filtered_df['cluster'] == cluster]
        cluster_transcripts = []
        
        logger.info(f"  Processing cluster '{cluster}' ({len(cluster_videos)} top videos)...")
        
        for _, row in tqdm(cluster_videos.iterrows(), total=len(cluster_videos), leave=False):
            vid = row['video_id']
            title = row['title']
            text = get_transcript(vid, cache_manager, logger, transcript_rate_limiter)
            
            if text:
                cluster_transcripts.append(text)
                combined_text.append(text)
            else:
                # Fallback to title if transcript is unavailable (e.g. IP blocked)
                cluster_transcripts.append(title)
                combined_text.append(title)
        
        full_text = " ".join(cluster_transcripts)
        cluster_texts[cluster] = full_text
        logger.info(f"    -> Collected {len(full_text):,} characters for '{cluster}'")

    # 5. Generate Word Clouds
    logger.info("Step 4: Generating Daily Word Clouds...")
    
    import src.visualizations.word_clouds as wc_module
    wc_module.FIGURES_DIR = report_dir 
    
    SIG_STOPWORDS = [
        "just", "like", "know", "think", "going", "really", "people", "get", "got", "make", "one", "go", "see", "say", "said", 
        "time", "thing", "things", "way", "well", "yeah", "right", "want", "take", "lot", "much", "even", "now", "back", "look", 
        "good", "first", "also", "would", "could", "actually", "probably", "something", "maybe", "kind", "mean", "dont", "cant", 
        "thats", "im", "youre", "hes", "shes", "theyre", "ive", "weve", "did", "us", "come", "need", "let", "many", "two", "day",
        "year", "years", "work", "world", "state", "country", "use", "used", "made", "point", "sure", "tell", "much", "little",
        "never", "always", "long", "still", "may", "part", "call", "start", "every", "around", "put", "end", "guy", "guys",
        "uh", "um", "uh-huh", "mhm", "hmm", "okay", "yeah", "yep", "guess", "video", "videos", "talk", "talking", "news", "story",
        "don't", "can't", "it's", "that's", "i'm", "you're", "he's", "she's", "we're", "they're", "i've", "we've", "didn't",
        "won't", "wouldn't", "couldn't", "shouldn't", "isn't", "aren't", "wasn't", "weren't", "hasn't", "haven't", "hadn't"
    ]
    
    # Define Colormaps per cluster
    cluster_colormaps = {
        'Left': 'ocean',       # Blue/Green tones
        'right': 'magma',      # Red/Purple/Black tones
        'mainstream': 'plasma',# Purple/Orange tones
        'manosphere': 'inferno', # Black/Red/Yellow
        'my-env': 'viridis'
    }
    
    # Combined Cloud
    full_text = " ".join(combined_text)
    if full_text.strip():
        wc_module.generate_word_cloud(
            full_text,
            "daily_combined_transcripts_sig.png",
            f"Daily Content (Key Themes): {target_date_iso}",
            extra_stopwords=SIG_STOPWORDS,
            colormap='viridis'
        )
    
    # Cluster Clouds
    for cluster, text in cluster_texts.items():
        if text.strip():
            cmap = cluster_colormaps.get(cluster, 'viridis')
            logger.info(f"  -> Generating significant cloud for '{cluster}' using colormap '{cmap}'")
            
            wc_module.generate_word_cloud(
                text,
                f"daily_{cluster}_transcripts_sig.png",
                f"Daily {cluster.title()} (Key Themes): {target_date_iso}",
                extra_stopwords=SIG_STOPWORDS,
                colormap=cmap
            )
        else:
            logger.warning(f"  -> Skipping cloud for '{cluster}': No text content found.")

    # 6. Statistical Word Comparison
    logger.info("Step 5: Comparing Word Frequencies (Right vs Libs)...")
    # compare_word_frequencies(cluster_texts, SIG_STOPWORDS, report_dir, target_date_iso)

    logger.info("="*60)
    logger.info(f"✅ REPORT COMPLETE")
    logger.info(f"📂 Output saved to: {report_dir}")
    logger.info("="*60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate Daily Vibes Report')
    parser.add_argument('--date', type=str, help='Target date (YYYY-MM-DD), defaults to today', default=None)
    args = parser.parse_args()
    run_daily_report(args.date)
