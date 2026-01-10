"""Temporal visualization tools for tracking trends over time."""

import os
import sys
import logging
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
from datetime import datetime
from typing import Optional, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.temporal_analysis import load_historical_runs, compare_theme_trends, calculate_sentiment_trends


def plot_theme_trends(df_trends: pd.DataFrame,
                      top_n: int = 10,
                      cluster: Optional[str] = None,
                      output_path: str = "figures/theme_trends.png"):
    """
    Plot theme prevalence over time.

    Args:
        df_trends: DataFrame with dates and theme frequencies
        top_n: Number of top themes to plot
        cluster: Cluster name for title
        output_path: Where to save the plot
    """
    if df_trends.empty:
        print("No data to plot")
        return

    # Get top N themes from most recent data
    most_recent = df_trends.iloc[-1]
    top_themes = most_recent.nlargest(top_n).index.tolist()

    # Create plot
    fig, ax = plt.subplots(figsize=(14, 8))

    # Convert dates to datetime
    dates = [datetime.strptime(d, "%Y-%m-%d") for d in df_trends.index]

    # Plot each theme
    for theme in top_themes:
        values = df_trends[theme].values
        ax.plot(dates, values, marker='o', linewidth=2, label=theme)

    # Formatting
    ax.set_xlabel('Date', fontsize=12)
    ax.set_ylabel('Frequency (mentions)', fontsize=12)

    title = f'Top {top_n} Theme Trends Over Time'
    if cluster:
        title += f' - {cluster.title()} Cluster'
    ax.set_title(title, fontsize=14, fontweight='bold')

    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
    ax.grid(True, alpha=0.3)

    # Format x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates)//10)))
    plt.xticks(rotation=45)

    plt.tight_layout()

    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved theme trends plot to {output_path}")
    plt.close()


def plot_sentiment_trends(df_sentiment: pd.DataFrame,
                          cluster: Optional[str] = None,
                          output_path: str = "figures/sentiment_trends.png"):
    """
    Plot sentiment distribution over time as stacked area chart.

    Args:
        df_sentiment: DataFrame with sentiment percentages over time
        cluster: Cluster name for title
        output_path: Where to save the plot
    """
    if df_sentiment.empty:
        print("No sentiment data to plot")
        return

    # Create plot
    fig, ax = plt.subplots(figsize=(14, 8))

    # Convert dates to datetime
    dates = [datetime.strptime(d, "%Y-%m-%d") for d in df_sentiment.index]

    # Define colors for sentiments
    colors = {
        'Positive': '#2ecc71',   # Green
        'Neutral': '#95a5a6',    # Gray
        'Negative': '#e74c3c',   # Red
        'Mixed': '#f39c12'       # Orange
    }

    # Stack sentiments
    sentiments = ['Positive', 'Neutral', 'Negative', 'Mixed']
    data_to_plot = [df_sentiment[s].values for s in sentiments if s in df_sentiment.columns]
    labels = [s for s in sentiments if s in df_sentiment.columns]
    colors_to_plot = [colors[s] for s in labels]

    ax.stackplot(dates, *data_to_plot, labels=labels, colors=colors_to_plot, alpha=0.8)

    # Formatting
    ax.set_xlabel('Date', fontsize=12)
    ax.set_ylabel('Percentage (%)', fontsize=12)

    title = 'Sentiment Distribution Over Time'
    if cluster:
        title += f' - {cluster.title()} Cluster'
    ax.set_title(title, fontsize=14, fontweight='bold')

    ax.legend(loc='upper left', fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 100)

    # Format x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates)//10)))
    plt.xticks(rotation=45)

    plt.tight_layout()

    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved sentiment trends plot to {output_path}")
    plt.close()


def plot_theme_velocity(df_trends: pd.DataFrame,
                       output_path: str = "figures/theme_velocity.png"):
    """
    Plot theme "velocity" (rate of change) to identify surging/declining topics.

    Args:
        df_trends: DataFrame with dates and theme frequencies
        output_path: Where to save the plot
    """
    if df_trends.empty or len(df_trends) < 2:
        print("Need at least 2 time points to calculate velocity")
        return

    # Calculate change from previous period
    velocity = df_trends.iloc[-1] - df_trends.iloc[-2]

    # Sort by absolute velocity
    velocity_sorted = velocity.reindex(velocity.abs().sort_values(ascending=False).index)

    # Take top 15 positive and negative
    top_gainers = velocity_sorted[velocity_sorted > 0].head(10)
    top_decliners = velocity_sorted[velocity_sorted < 0].tail(10)

    combined = pd.concat([top_gainers, top_decliners])

    # Create horizontal bar plot
    fig, ax = plt.subplots(figsize=(12, 10))

    colors = ['#2ecc71' if v > 0 else '#e74c3c' for v in combined.values]
    ax.barh(range(len(combined)), combined.values, color=colors, alpha=0.7)

    ax.set_yticks(range(len(combined)))
    ax.set_yticklabels(combined.index, fontsize=9)
    ax.set_xlabel('Change in Frequency (velocity)', fontsize=12)
    ax.set_title('Theme Velocity: Surging vs. Declining Topics', fontsize=14, fontweight='bold')

    ax.axvline(x=0, color='black', linestyle='-', linewidth=0.8)
    ax.grid(True, alpha=0.3, axis='x')

    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#2ecc71', alpha=0.7, label='Surging'),
        Patch(facecolor='#e74c3c', alpha=0.7, label='Declining')
    ]
    ax.legend(handles=legend_elements, loc='lower right')

    plt.tight_layout()

    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved theme velocity plot to {output_path}")
    plt.close()


def generate_all_temporal_plots(days_back: int = 30,
                                clusters: Optional[List[str]] = None):
    """
    Generate all temporal visualizations.

    Args:
        days_back: Number of days to analyze
        clusters: List of clusters to analyze (None = all)
    """
    logger = logging.getLogger("temporal-plots")
    logger.info("Generating temporal visualizations...")

    # Load historical data
    historical_runs = load_historical_runs(days_back)

    if len(historical_runs) < 2:
        logger.warning("Need at least 2 historical runs for temporal plots")
        return

    # Overall plots (all clusters)
    logger.info("Generating overall trend plots...")
    theme_trends = compare_theme_trends(historical_runs)
    sentiment_trends = calculate_sentiment_trends(historical_runs)

    plot_theme_trends(theme_trends, output_path="figures/temporal/overall_theme_trends.png")
    plot_sentiment_trends(sentiment_trends, output_path="figures/temporal/overall_sentiment_trends.png")
    plot_theme_velocity(theme_trends, output_path="figures/temporal/overall_theme_velocity.png")

    # Per-cluster plots
    if clusters:
        for cluster in clusters:
            logger.info(f"Generating plots for {cluster} cluster...")
            cluster_theme_trends = compare_theme_trends(historical_runs, cluster=cluster)
            cluster_sentiment_trends = calculate_sentiment_trends(historical_runs, cluster=cluster)

            plot_theme_trends(
                cluster_theme_trends,
                cluster=cluster,
                output_path=f"figures/temporal/{cluster}_theme_trends.png"
            )
            plot_sentiment_trends(
                cluster_sentiment_trends,
                cluster=cluster,
                output_path=f"figures/temporal/{cluster}_sentiment_trends.png"
            )

    logger.info("Temporal visualization complete!")


if __name__ == "__main__":
    # Change to project root if running from src/
    if os.path.basename(os.getcwd()) == 'src' or os.path.basename(os.getcwd()) == 'visualizations':
        os.chdir('../..')

    # Setup logger
    from src.utils.logger import setup_logger
    logger = setup_logger("temporal-plots", level=logging.INFO)

    # Generate all plots
    generate_all_temporal_plots(
        days_back=30,
        clusters=['Left', 'right', 'my-env', 'mainstream', 'manosphere']
    )
