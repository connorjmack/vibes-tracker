import os
import sys
import argparse
import logging
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timezone
from tqdm import tqdm
from dotenv import load_dotenv
from googleapiclient.discovery import build

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config_loader import load_config
from src.utils.logger import setup_logger, QuotaTracker
from src.utils.cache_manager import CacheManager
from src.analyze import get_transcript
from src.ingest import ingest_clusters
from src.visualizations.word_clouds import generate_word_cloud

def fetch_video_stats(video_ids, api_key, logger, quota_tracker):
    """Fetches view counts for a list of video IDs in batches of 50."""
    youtube = build('youtube', 'v3', developerKey=api_key)
    stats_map = {}
    
    # Process in chunks of 50
    chunk_size = 50
    for i in range(0, len(video_ids), chunk_size):
        chunk = video_ids[i:i+chunk_size]
        try:
            quota_tracker.log_youtube_api_call(1, f"get stats for {len(chunk)} videos")
            response = youtube.videos().list(
                part="statistics",
                id=",".join(chunk)
            ).execute()
            
            for item in response.get('items', []):
                vid = item['id']
                views = int(item['statistics'].get('viewCount', 0))
                stats_map[vid] = views
                
        except Exception as e:
            logger.error(f"Error fetching stats for chunk: {e}")
            
    return stats_map

def plot_views_by_cluster(df, report_dir, target_date_iso):
    """Plots total views per channel, separated by cluster."""
    
    # Define color palettes for visual distinction
    cluster_palettes = {
        'libs': 'Blues_r',       # Blue reverse (darkest at top)
        'right': 'Reds_r',       # Red reverse
        'mainstream': 'Purples_r', # Purple reverse
        'my-env': 'Greens_r'     # Green for custom
    }
    
    # Iterate through each cluster present in the data
    for cluster in df['cluster'].unique():
        cluster_df = df[df['cluster'] == cluster]
        
        # Aggregate views by channel
        channel_views = cluster_df.groupby('channel_name')['view_count'].sum().sort_values(ascending=False)
        
        if channel_views.empty:
            continue

        plt.figure(figsize=(10, len(channel_views) * 0.6 + 2)) # Dynamic height
        
        # Select palette (default to 'viridis' if unknown cluster)
        palette = cluster_palettes.get(cluster, 'viridis')
        
        # Create bar plot
        ax = sns.barplot(x=channel_views.values, y=channel_views.index, palette=palette)
        
        plt.title(f"Views by Channel: {cluster.title()} ({target_date_iso})", fontsize=16)
        plt.xlabel("Total Views", fontsize=12)
        plt.ylabel("", fontsize=12)
        
        # Add view count labels
        for i, v in enumerate(channel_views.values):
            ax.text(v, i, f" {v:,.0f}", va='center', fontweight='bold')

        # Adjust x-axis to fit labels
        plt.xlim(right=channel_views.max() * 1.2)
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
    stats = fetch_video_stats(video_ids, API_KEY, logger, quota_tracker)
    
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
         cutoff_idx = int(len(daily_df) * 0.1) or 1
         filtered_df = daily_df.iloc[:cutoff_idx]
    else:
        last_idx = cutoff_mask[cutoff_mask].index[-1]
        loc = daily_df.index.get_loc(last_idx)
        filtered_df = daily_df.iloc[:loc+1]
    
    logger.info(f"📊 View Stats: Total Views = {total_views:,}")
    logger.info(f"   Filtered to Top {len(filtered_df)} videos (out of {count})")
    
    # Create Report Directory
    report_dir = os.path.join(config.paths.data_dir, "reports", target_date_iso)
    os.makedirs(report_dir, exist_ok=True)
    
    # Plot Distribution (Cluster Specific)
    plot_views_by_cluster(daily_df, report_dir, target_date_iso)
    
    # 4. Fetch Transcripts for Filtered Videos
    logger.info("Step 3: Fetching transcripts for top videos...")
    cache_manager = CacheManager(config.analysis.cache_dir, logger)
    
    cluster_texts = {}
    combined_text = []
    
    for cluster in filtered_df['cluster'].unique():
        cluster_videos = filtered_df[filtered_df['cluster'] == cluster]
        cluster_transcripts = []
        
        logger.info(f"  Processing cluster '{cluster}' ({len(cluster_videos)} top videos)...")
        
        for _, row in tqdm(cluster_videos.iterrows(), total=len(cluster_videos), leave=False):
            vid = row['video_id']
            text = get_transcript(vid, cache_manager, logger)
            if text:
                cluster_transcripts.append(text)
                combined_text.append(text)
        
        cluster_texts[cluster] = " ".join(cluster_transcripts)

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
        "never", "always", "long", "still", "may", "part", "call", "start", "every", "around", "put", "end", "guy", "guys"
    ]
    
    # Combined Cloud
    full_text = " ".join(combined_text)
    if full_text.strip():
        wc_module.generate_word_cloud(
            full_text,
            "daily_combined_transcripts.png",
            f"Daily Content (Weighted by Views): {target_date_iso}"
        )
        wc_module.generate_word_cloud(
            full_text,
            "daily_combined_transcripts_sig.png",
            f"Daily Content (Key Themes): {target_date_iso}",
            extra_stopwords=SIG_STOPWORDS
        )
    
    # Cluster Clouds
    for cluster, text in cluster_texts.items():
        if text.strip():
            wc_module.generate_word_cloud(
                text,
                f"daily_{cluster}_transcripts.png",
                f"Daily {cluster.title()}: {target_date_iso}"
            )
            wc_module.generate_word_cloud(
                text,
                f"daily_{cluster}_transcripts_sig.png",
                f"Daily {cluster.title()} (Key Themes): {target_date_iso}",
                extra_stopwords=SIG_STOPWORDS
            )

    logger.info("="*60)
    logger.info(f"✅ REPORT COMPLETE")
    logger.info(f"📂 Output saved to: {report_dir}")
    logger.info("="*60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate Daily Vibes Report')
    parser.add_argument('--date', type=str, help='Target date (YYYY-MM-DD), defaults to today', default=None)
    args = parser.parse_args()
    run_daily_report(args.date)
