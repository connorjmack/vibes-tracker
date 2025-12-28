"""Sentiment distribution visualizations."""

import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import logging
from pathlib import Path
from collections import Counter

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def plot_sentiment_distribution_by_cluster(df: pd.DataFrame,
                                           output_path: str = "figures/sentiment_distribution.png"):
    """
    Plot sentiment distribution as stacked bar chart by cluster.

    Args:
        df: DataFrame with 'cluster' and 'sentiment' columns
        output_path: Where to save the plot
    """
    # Group by cluster and sentiment
    sentiment_counts = df.groupby(['cluster', 'sentiment']).size().unstack(fill_value=0)

    # Convert to percentages
    sentiment_pct = sentiment_counts.div(sentiment_counts.sum(axis=1), axis=0) * 100

    # Create plot
    fig, ax = plt.subplots(figsize=(12, 6))

    # Define colors
    colors = {
        'Positive': '#2ecc71',
        'Neutral': '#95a5a6',
        'Negative': '#e74c3c',
        'Mixed': '#f39c12'
    }

    # Ensure columns exist
    for sent in ['Positive', 'Neutral', 'Negative', 'Mixed']:
        if sent not in sentiment_pct.columns:
            sentiment_pct[sent] = 0

    # Plot stacked bars
    sentiment_pct[['Positive', 'Neutral', 'Negative', 'Mixed']].plot(
        kind='bar',
        stacked=True,
        ax=ax,
        color=[colors[s] for s in ['Positive', 'Neutral', 'Negative', 'Mixed']],
        alpha=0.8
    )

    ax.set_xlabel('Cluster', fontsize=12)
    ax.set_ylabel('Percentage (%)', fontsize=12)
    ax.set_title('Sentiment Distribution by Cluster', fontsize=14, fontweight='bold')
    ax.legend(title='Sentiment', bbox_to_anchor=(1.05, 1), loc='upper left')
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3, axis='y')

    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved sentiment distribution plot to {output_path}")
    plt.close()


def plot_framing_distribution(df: pd.DataFrame,
                             output_path: str = "figures/framing_distribution.png"):
    """
    Plot framing distribution by cluster.

    Args:
        df: DataFrame with 'cluster' and 'framing' columns
        output_path: Where to save the plot
    """
    if 'framing' not in df.columns:
        print("No framing data available")
        return

    # Group by cluster and framing
    framing_counts = df.groupby(['cluster', 'framing']).size().unstack(fill_value=0)

    # Convert to percentages
    framing_pct = framing_counts.div(framing_counts.sum(axis=1), axis=0) * 100

    # Create plot
    fig, ax = plt.subplots(figsize=(12, 6))

    # Define colors
    colors = {
        'favorable': '#3498db',
        'critical': '#e74c3c',
        'neutral': '#95a5a6',
        'alarmist': '#f39c12'
    }

    # Plot stacked bars
    framings = ['favorable', 'critical', 'neutral', 'alarmist']
    available_framings = [f for f in framings if f in framing_pct.columns]

    framing_pct[available_framings].plot(
        kind='bar',
        stacked=True,
        ax=ax,
        color=[colors[f] for f in available_framings],
        alpha=0.8
    )

    ax.set_xlabel('Cluster', fontsize=12)
    ax.set_ylabel('Percentage (%)', fontsize=12)
    ax.set_title('Narrative Framing Distribution by Cluster', fontsize=14, fontweight='bold')
    ax.legend(title='Framing', bbox_to_anchor=(1.05, 1), loc='upper left')
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3, axis='y')

    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved framing distribution plot to {output_path}")
    plt.close()


def plot_theme_category_distribution(df: pd.DataFrame,
                                    output_path: str = "figures/theme_categories.png"):
    """
    Plot theme category distribution by cluster.

    Args:
        df: DataFrame with 'cluster' and 'theme_categories' columns
        output_path: Where to save the plot
    """
    if 'theme_categories' not in df.columns:
        print("No theme category data available")
        return

    # Extract categories by cluster
    category_data = []

    for _, row in df.iterrows():
        if pd.isna(row.get('theme_categories')):
            continue

        cluster = row['cluster']
        categories = [c.strip() for c in str(row['theme_categories']).split('|') if c.strip()]

        for category in categories:
            category_data.append({'cluster': cluster, 'category': category})

    if not category_data:
        print("No category data to plot")
        return

    df_cat = pd.DataFrame(category_data)

    # Group and count
    cat_counts = df_cat.groupby(['cluster', 'category']).size().unstack(fill_value=0)

    # Convert to percentages
    cat_pct = cat_counts.div(cat_counts.sum(axis=1), axis=0) * 100

    # Create plot
    fig, ax = plt.subplots(figsize=(14, 6))

    cat_pct.plot(kind='bar', ax=ax, alpha=0.8, width=0.8)

    ax.set_xlabel('Cluster', fontsize=12)
    ax.set_ylabel('Percentage (%)', fontsize=12)
    ax.set_title('Theme Category Distribution by Cluster', fontsize=14, fontweight='bold')
    ax.legend(title='Category', bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
    ax.set_ylim(0, cat_pct.max().max() * 1.1)
    ax.grid(True, alpha=0.3, axis='y')

    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved theme category distribution plot to {output_path}")
    plt.close()


def generate_all_sentiment_plots(df: pd.DataFrame):
    """
    Generate all sentiment and framing visualizations.

    Args:
        df: Analyzed data DataFrame
    """
    logger = logging.getLogger("sentiment-plots")
    logger.info("Generating sentiment and framing visualizations...")

    plot_sentiment_distribution_by_cluster(df, output_path="figures/enhanced/sentiment_distribution.png")
    plot_framing_distribution(df, output_path="figures/enhanced/framing_distribution.png")
    plot_theme_category_distribution(df, output_path="figures/enhanced/theme_categories.png")

    logger.info("Sentiment visualization complete!")


if __name__ == "__main__":
    # Change to project root if running from src/
    if os.path.basename(os.getcwd()) == 'src' or os.path.basename(os.getcwd()) == 'visualizations':
        os.chdir('../..')

    # Setup logger
    from src.utils.logger import setup_logger
    from src.utils.config_loader import load_config

    logger = setup_logger("sentiment-plots", level=logging.INFO)
    config = load_config()

    # Load data
    try:
        df = pd.read_csv(config.paths.analyzed_data)
        generate_all_sentiment_plots(df)
    except FileNotFoundError as e:
        logger.error(f"Analyzed data not found at {config.paths.analyzed_data}")
