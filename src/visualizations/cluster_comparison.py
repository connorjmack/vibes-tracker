"""Visualizations for cross-cluster narrative comparison."""

import os
import sys
import logging
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import Dict, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.cross_cluster_analysis import (
    load_analyzed_data,
    extract_themes_by_cluster,
    calculate_cluster_similarity,
    calculate_theme_frequency_by_cluster,
    calculate_sentiment_divergence,
    identify_consensus_topics
)


def plot_cluster_similarity_heatmap(df_similarity: pd.DataFrame,
                                   output_path: str = "figures/cluster_similarity.png"):
    """
    Plot cluster similarity as a heatmap.

    Args:
        df_similarity: Similarity matrix from calculate_cluster_similarity
        output_path: Where to save the plot
    """
    fig, ax = plt.subplots(figsize=(10, 8))

    # Create heatmap
    sns.heatmap(
        df_similarity,
        annot=True,
        fmt='.2f',
        cmap='YlOrRd',
        square=True,
        cbar_kws={'label': 'Cosine Similarity'},
        ax=ax
    )

    ax.set_title('Cluster Similarity Based on Theme Overlap', fontsize=14, fontweight='bold')
    ax.set_xlabel('Cluster', fontsize=12)
    ax.set_ylabel('Cluster', fontsize=12)

    plt.tight_layout()

    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved cluster similarity heatmap to {output_path}")
    plt.close()


def plot_sentiment_comparison(df: pd.DataFrame,
                              theme: str,
                              output_path: str = "figures/sentiment_comparison.png"):
    """
    Plot sentiment comparison for a specific theme across clusters.

    Args:
        df: Analyzed data DataFrame
        theme: Theme to analyze
        output_path: Where to save the plot
    """
    divergence = calculate_sentiment_divergence(df, theme)

    if not divergence:
        print(f"No sentiment data found for theme: {theme}")
        return

    # Prepare data for plotting
    clusters = list(divergence.keys())
    sentiments = ['Positive', 'Neutral', 'Negative', 'Mixed']
    colors = {
        'Positive': '#2ecc71',
        'Neutral': '#95a5a6',
        'Negative': '#e74c3c',
        'Mixed': '#f39c12'
    }

    # Create stacked bar chart
    fig, ax = plt.subplots(figsize=(12, 6))

    bottom = [0] * len(clusters)
    for sentiment in sentiments:
        values = [divergence[cluster].get(sentiment, 0) for cluster in clusters]
        ax.bar(clusters, values, bottom=bottom, label=sentiment,
               color=colors[sentiment], alpha=0.8)
        bottom = [b + v for b, v in zip(bottom, values)]

    ax.set_xlabel('Cluster', fontsize=12)
    ax.set_ylabel('Percentage (%)', fontsize=12)
    ax.set_title(f'Sentiment Comparison for "{theme}"', fontsize=14, fontweight='bold')
    ax.legend(loc='upper right')
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3, axis='y')

    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved sentiment comparison plot to {output_path}")
    plt.close()


def plot_theme_distribution(themes_by_cluster: Dict[str, list],
                           top_n: int = 15,
                           output_path: str = "figures/theme_distribution.png"):
    """
    Plot theme frequency distribution across clusters.

    Args:
        themes_by_cluster: Dictionary mapping cluster to list of themes
        top_n: Number of top themes to show
        output_path: Where to save the plot
    """
    # Calculate frequency matrix
    df_freq = calculate_theme_frequency_by_cluster(themes_by_cluster)

    # Get top N themes overall
    total_freq = df_freq.sum(axis=0).sort_values(ascending=False)
    top_themes = total_freq.head(top_n).index.tolist()

    # Filter to top themes
    df_top = df_freq[top_themes].T

    # Create grouped bar chart
    fig, ax = plt.subplots(figsize=(14, 8))

    df_top.plot(kind='barh', ax=ax, width=0.8)

    ax.set_xlabel('Frequency (mentions)', fontsize=12)
    ax.set_ylabel('Theme', fontsize=12)
    ax.set_title(f'Top {top_n} Themes Across Clusters', fontsize=14, fontweight='bold')
    ax.legend(title='Cluster', bbox_to_anchor=(1.05, 1), loc='upper left')
    ax.grid(True, alpha=0.3, axis='x')

    plt.tight_layout()

    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved theme distribution plot to {output_path}")
    plt.close()


def plot_consensus_vs_echo_chamber(consensus_topics: list,
                                   echo_chamber: Dict[str, list],
                                   output_path: str = "figures/consensus_vs_echo.png"):
    """
    Plot consensus topics vs echo chamber themes.

    Args:
        consensus_topics: List of (theme, num_clusters, avg_freq) tuples
        echo_chamber: Dictionary mapping cluster to unique themes
        output_path: Where to save the plot
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # Left: Top consensus topics
    if consensus_topics:
        top_consensus = consensus_topics[:10]
        themes = [t[0][:40] for t in top_consensus]  # Truncate long themes
        clusters = [t[1] for t in top_consensus]

        ax1.barh(range(len(themes)), clusters, color='#3498db', alpha=0.7)
        ax1.set_yticks(range(len(themes)))
        ax1.set_yticklabels(themes, fontsize=9)
        ax1.set_xlabel('Number of Clusters', fontsize=12)
        ax1.set_title('Top Consensus Topics\n(Discussed Across Multiple Clusters)',
                     fontsize=12, fontweight='bold')
        ax1.grid(True, alpha=0.3, axis='x')

    # Right: Echo chamber theme counts
    if echo_chamber:
        clusters = list(echo_chamber.keys())
        counts = [len(themes) for themes in echo_chamber.values()]

        ax2.bar(range(len(clusters)), counts, color='#e74c3c', alpha=0.7)
        ax2.set_xticks(range(len(clusters)))
        ax2.set_xticklabels(clusters, rotation=45, ha='right', fontsize=10)
        ax2.set_ylabel('Number of Unique Themes', fontsize=12)
        ax2.set_title('Echo Chamber Themes\n(Cluster-Specific Topics)',
                     fontsize=12, fontweight='bold')
        ax2.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()

    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved consensus vs echo chamber plot to {output_path}")
    plt.close()


def generate_all_comparison_plots(df: pd.DataFrame):
    """
    Generate all cross-cluster comparison visualizations.

    Args:
        df: Analyzed data DataFrame
    """
    logger = logging.getLogger("cluster-comparison-plots")
    logger.info("Generating cross-cluster comparison visualizations...")

    # Extract data
    themes_by_cluster = extract_themes_by_cluster(df)
    df_freq = calculate_theme_frequency_by_cluster(themes_by_cluster)
    consensus_topics = identify_consensus_topics(themes_by_cluster, min_clusters=3)

    # Import echo chamber function
    from src.cross_cluster_analysis import find_echo_chamber_themes
    echo_chamber = find_echo_chamber_themes(themes_by_cluster)

    # Generate plots
    logger.info("Creating theme distribution plot...")
    plot_theme_distribution(themes_by_cluster,
                           output_path="figures/comparison/theme_distribution.png")

    logger.info("Creating consensus vs echo chamber plot...")
    plot_consensus_vs_echo_chamber(consensus_topics, echo_chamber,
                                   output_path="figures/comparison/consensus_vs_echo.png")

    # Try to create similarity heatmap (requires sklearn)
    try:
        logger.info("Creating cluster similarity heatmap...")
        df_similarity = calculate_cluster_similarity(df_freq)
        plot_cluster_similarity_heatmap(df_similarity,
                                       output_path="figures/comparison/cluster_similarity.png")
    except ImportError:
        logger.warning("scikit-learn not installed. Skipping similarity heatmap.")

    # Create sentiment comparison for top consensus topics
    if consensus_topics:
        logger.info("Creating sentiment comparison plots for top topics...")
        for i, (theme, num_clusters, avg_freq) in enumerate(consensus_topics[:3]):
            safe_filename = "".join(c if c.isalnum() else "_" for c in theme[:30])
            plot_sentiment_comparison(
                df, theme,
                output_path=f"figures/comparison/sentiment_{safe_filename}.png"
            )

    logger.info("Cross-cluster visualization complete!")


if __name__ == "__main__":
    # Change to project root if running from src/
    if os.path.basename(os.getcwd()) == 'src' or os.path.basename(os.getcwd()) == 'visualizations':
        os.chdir('../..')

    # Setup logger
    from src.utils.logger import setup_logger
    from src.utils.config_loader import load_config

    logger = setup_logger("cluster-comparison-plots", level=logging.INFO)
    config = load_config()

    # Load data
    try:
        df = load_analyzed_data(config)
        generate_all_comparison_plots(df)
    except FileNotFoundError as e:
        logger.error(str(e))
