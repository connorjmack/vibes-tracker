"""Main visualization orchestrator for the vibes-tracker pipeline."""

import os
import sys
import logging
import pandas as pd
from pathlib import Path

from vibes_tracker.utils.config_loader import load_config
from vibes_tracker.utils.logger import setup_logger


def generate_all_visualizations():
    """Generate all available visualizations."""
    # Change to project root if needed
    if os.path.basename(os.getcwd()) == 'src':
        os.chdir('..')

    # Load configuration
    config = load_config()
    logger = setup_logger("visualize", level=logging.INFO)

    logger.info("="*60)
    logger.info("YouTube Vibes Tracker - Visualization Generation")
    logger.info("="*60)

    # Check if analyzed data exists
    if not Path(config.paths.analyzed_data).exists():
        logger.error(f"Analyzed data not found at {config.paths.analyzed_data}")
        logger.error("Please run analyze.py first.")
        return

    # Load data
    df = pd.read_csv(config.paths.analyzed_data)
    logger.info(f"Loaded {len(df)} analyzed videos from {len(df['cluster'].unique())} clusters")

    # Create output directories
    os.makedirs("figures/enhanced", exist_ok=True)
    os.makedirs("figures/comparison", exist_ok=True)
    os.makedirs("figures/temporal", exist_ok=True)

    # 1. Word Clouds
    logger.info("\n📊 Generating word clouds...")
    try:
        from vibes_tracker.visualizations.word_clouds import generate_word_clouds
        df_cluster = pd.read_csv(config.paths.cluster_data)
        generate_word_clouds(df_cluster)
    except Exception as e:
        logger.error(f"Error generating word clouds: {e}")

    # 2. Sentiment Plots
    logger.info("\n📈 Generating sentiment and framing plots...")
    try:
        from vibes_tracker.visualizations.sentiment_plots import generate_all_sentiment_plots
        generate_all_sentiment_plots(df)
    except Exception as e:
        logger.error(f"Error generating sentiment plots: {e}")

    # 3. Cross-Cluster Comparison
    logger.info("\n🌍 Generating cross-cluster comparison plots...")
    try:
        from vibes_tracker.visualizations.cluster_comparison import generate_all_comparison_plots
        generate_all_comparison_plots(df)
    except Exception as e:
        logger.error(f"Error generating comparison plots: {e}")

    # 4. Temporal Trends (if historical data exists)
    logger.info("\n📅 Generating temporal trend plots...")
    try:
        from vibes_tracker.visualizations.temporal_plots import generate_all_temporal_plots
        generate_all_temporal_plots(
            days_back=30,
            clusters=['Left', 'right', 'my-env', 'mainstream', 'manosphere']
        )
    except Exception as e:
        logger.warning(f"Temporal plots skipped (need historical data): {e}")

    logger.info("\n✅ Visualization generation complete!")
    logger.info("="*60)


if __name__ == "__main__":
    generate_all_visualizations()
