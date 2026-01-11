"""Cross-cluster narrative comparison for understanding information ecosystem fragmentation."""

import os
import sys
import json
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, List, Set, Tuple

from vibes_tracker.utils.config_loader import load_config
from vibes_tracker.utils.logger import setup_logger


def load_analyzed_data(config) -> pd.DataFrame:
    """Load the analyzed data CSV."""
    try:
        return pd.read_csv(config.paths.analyzed_data)
    except FileNotFoundError:
        raise FileNotFoundError(f"Analyzed data not found at {config.paths.analyzed_data}. Run analyze.py first.")


def extract_themes_by_cluster(df: pd.DataFrame) -> Dict[str, List[str]]:
    """
    Extract all themes grouped by cluster.

    Args:
        df: DataFrame with 'cluster' and 'themes' columns

    Returns:
        Dictionary mapping cluster name to list of all themes
    """
    themes_by_cluster = defaultdict(list)

    for _, row in df.iterrows():
        if pd.isna(row.get('themes')):
            continue

        cluster = row['cluster']
        # Split themes (format: "Theme 1 | Theme 2 | Theme 3")
        themes = [t.strip() for t in str(row['themes']).split('|') if t.strip()]
        themes_by_cluster[cluster].extend(themes)

    return dict(themes_by_cluster)


def normalize_theme(theme: str) -> str:
    """
    Normalize theme text for comparison (lowercase, strip whitespace).

    Args:
        theme: Theme string

    Returns:
        Normalized theme
    """
    return theme.lower().strip()


def find_shared_themes(themes_by_cluster: Dict[str, List[str]],
                      min_clusters: int = 2) -> Set[str]:
    """
    Find themes that appear in at least N clusters.

    Args:
        themes_by_cluster: Dictionary mapping cluster to list of themes
        min_clusters: Minimum number of clusters a theme must appear in

    Returns:
        Set of shared theme names
    """
    # Count how many clusters each theme appears in
    theme_cluster_count = defaultdict(set)

    for cluster, themes in themes_by_cluster.items():
        unique_themes = set(normalize_theme(t) for t in themes)
        for theme in unique_themes:
            theme_cluster_count[theme].add(cluster)

    # Filter to themes appearing in at least min_clusters
    shared = {
        theme for theme, clusters in theme_cluster_count.items()
        if len(clusters) >= min_clusters
    }

    return shared


def find_echo_chamber_themes(themes_by_cluster: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """
    Find themes unique to each cluster (echo chamber topics).

    Args:
        themes_by_cluster: Dictionary mapping cluster to list of themes

    Returns:
        Dictionary mapping cluster to list of unique themes
    """
    # Get all themes and count clusters
    theme_cluster_count = defaultdict(set)

    for cluster, themes in themes_by_cluster.items():
        unique_themes = set(normalize_theme(t) for t in themes)
        for theme in unique_themes:
            theme_cluster_count[theme].add(cluster)

    # Find themes appearing in only one cluster
    echo_chamber = defaultdict(list)

    for cluster, themes in themes_by_cluster.items():
        unique_themes = set(normalize_theme(t) for t in themes)
        for theme in unique_themes:
            if len(theme_cluster_count[theme]) == 1:
                echo_chamber[cluster].append(theme)

    return dict(echo_chamber)


def calculate_sentiment_divergence(df: pd.DataFrame,
                                   theme: str) -> Dict[str, Dict[str, float]]:
    """
    Calculate sentiment distribution for a theme across clusters.

    Args:
        df: DataFrame with analysis results
        theme: Theme to analyze

    Returns:
        Dictionary mapping cluster to sentiment distribution
    """
    theme_normalized = normalize_theme(theme)
    divergence = defaultdict(lambda: {'Positive': 0, 'Neutral': 0, 'Negative': 0, 'Mixed': 0})

    for _, row in df.iterrows():
        if pd.isna(row.get('themes')) or pd.isna(row.get('sentiment')):
            continue

        # Check if this video discusses the theme
        themes = [normalize_theme(t.strip()) for t in str(row['themes']).split('|')]
        if theme_normalized not in themes:
            continue

        cluster = row['cluster']
        sentiment = row['sentiment']
        divergence[cluster][sentiment] += 1

    # Convert counts to percentages
    for cluster in divergence:
        total = sum(divergence[cluster].values())
        if total > 0:
            for sentiment in divergence[cluster]:
                divergence[cluster][sentiment] = (divergence[cluster][sentiment] / total) * 100

    return dict(divergence)


def calculate_theme_frequency_by_cluster(themes_by_cluster: Dict[str, List[str]]) -> pd.DataFrame:
    """
    Create a frequency matrix of themes across clusters.

    Args:
        themes_by_cluster: Dictionary mapping cluster to list of themes

    Returns:
        DataFrame with clusters as index and themes as columns
    """
    # Get all unique themes
    all_themes = set()
    for themes in themes_by_cluster.values():
        all_themes.update(normalize_theme(t) for t in themes)

    # Build frequency matrix
    freq_matrix = []

    for cluster, themes in themes_by_cluster.items():
        normalized_themes = [normalize_theme(t) for t in themes]
        theme_counts = Counter(normalized_themes)

        row = {theme: theme_counts.get(theme, 0) for theme in all_themes}
        row['cluster'] = cluster
        freq_matrix.append(row)

    df_freq = pd.DataFrame(freq_matrix)
    df_freq = df_freq.set_index('cluster')

    return df_freq


def calculate_cluster_similarity(df_freq: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate similarity between clusters based on theme overlap.

    Uses cosine similarity.

    Args:
        df_freq: Frequency matrix from calculate_theme_frequency_by_cluster

    Returns:
        Similarity matrix as DataFrame
    """
    from sklearn.metrics.pairwise import cosine_similarity

    # Calculate cosine similarity
    similarity_matrix = cosine_similarity(df_freq.values)

    # Convert to DataFrame
    df_similarity = pd.DataFrame(
        similarity_matrix,
        index=df_freq.index,
        columns=df_freq.index
    )

    return df_similarity


def identify_consensus_topics(themes_by_cluster: Dict[str, List[str]],
                             min_clusters: int = 3) -> List[Tuple[str, int, float]]:
    """
    Identify consensus topics discussed across multiple clusters.

    Args:
        themes_by_cluster: Dictionary mapping cluster to list of themes
        min_clusters: Minimum number of clusters for consensus

    Returns:
        List of (theme, num_clusters, avg_frequency) tuples, sorted by coverage
    """
    # Count cluster coverage and frequency for each theme
    theme_stats = defaultdict(lambda: {'clusters': set(), 'total_count': 0})

    for cluster, themes in themes_by_cluster.items():
        normalized_themes = [normalize_theme(t) for t in themes]
        theme_counts = Counter(normalized_themes)

        for theme, count in theme_counts.items():
            theme_stats[theme]['clusters'].add(cluster)
            theme_stats[theme]['total_count'] += count

    # Filter and format consensus topics
    consensus = []
    for theme, stats in theme_stats.items():
        num_clusters = len(stats['clusters'])
        if num_clusters >= min_clusters:
            avg_freq = stats['total_count'] / num_clusters
            consensus.append((theme, num_clusters, avg_freq))

    # Sort by number of clusters, then by frequency
    consensus.sort(key=lambda x: (x[1], x[2]), reverse=True)

    return consensus


def generate_comparison_report(df: pd.DataFrame) -> Dict:
    """
    Generate comprehensive cross-cluster comparison report.

    Args:
        df: Analyzed data DataFrame

    Returns:
        Dictionary with comparison results
    """
    logger = logging.getLogger("cross-cluster-analysis")

    # Extract themes by cluster
    themes_by_cluster = extract_themes_by_cluster(df)

    logger.info(f"Analyzing {len(themes_by_cluster)} clusters")

    # Calculate metrics
    shared_themes = find_shared_themes(themes_by_cluster, min_clusters=2)
    echo_chamber = find_echo_chamber_themes(themes_by_cluster)
    consensus_topics = identify_consensus_topics(themes_by_cluster, min_clusters=3)
    freq_matrix = calculate_theme_frequency_by_cluster(themes_by_cluster)

    # Calculate similarity only if we have sklearn
    try:
        similarity_matrix = calculate_cluster_similarity(freq_matrix)
        similarity_data = similarity_matrix.to_dict()
    except ImportError:
        logger.warning("scikit-learn not installed. Skipping similarity matrix.")
        similarity_data = {}

    # Get sentiment divergence for top consensus topics
    sentiment_divergence = {}
    for theme, num_clusters, avg_freq in consensus_topics[:5]:
        sentiment_divergence[theme] = calculate_sentiment_divergence(df, theme)

    # Compile report
    report = {
        'total_clusters': len(themes_by_cluster),
        'shared_themes_count': len(shared_themes),
        'shared_themes': sorted(list(shared_themes))[:50],  # Top 50
        'echo_chamber_themes': {
            cluster: sorted(themes[:20])  # Top 20 per cluster
            for cluster, themes in echo_chamber.items()
        },
        'consensus_topics': [
            {'theme': theme, 'clusters': num_clusters, 'avg_frequency': round(avg_freq, 2)}
            for theme, num_clusters, avg_freq in consensus_topics[:20]
        ],
        'sentiment_divergence': sentiment_divergence,
        'cluster_similarity': similarity_data,
        'theme_frequency_matrix': freq_matrix.to_dict()
    }

    return report


if __name__ == "__main__":
    # Change to project root if running from src/
    if os.path.basename(os.getcwd()) == 'src':
        os.chdir('..')

    # Load configuration
    config = load_config()
    logger = setup_logger("cross-cluster-analysis", level=logging.INFO)

    logger.info("="*60)
    logger.info("YouTube Vibes Tracker - Cross-Cluster Analysis")
    logger.info("="*60)

    # Load data
    try:
        df = load_analyzed_data(config)
        logger.info(f"Loaded {len(df)} analyzed videos from {len(df['cluster'].unique())} clusters")
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    # Generate report
    report = generate_comparison_report(df)

    logger.info(f"\n📊 Cross-Cluster Comparison Report")
    logger.info(f"   Total clusters analyzed: {report['total_clusters']}")
    logger.info(f"   Shared themes (2+ clusters): {report['shared_themes_count']}")

    logger.info(f"\n🌍 Consensus Topics (3+ clusters):")
    for topic in report['consensus_topics'][:10]:
        logger.info(f"   - {topic['theme']} ({topic['clusters']} clusters, avg {topic['avg_frequency']} mentions)")

    logger.info(f"\n🔒 Echo Chamber Themes (cluster-specific):")
    for cluster, themes in report['echo_chamber_themes'].items():
        logger.info(f"   {cluster}: {len(themes)} unique themes")
        for theme in themes[:3]:
            logger.info(f"      - {theme}")

    logger.info(f"\n📈 Sentiment Divergence for Top Topics:")
    for theme, divergence in list(report['sentiment_divergence'].items())[:3]:
        logger.info(f"   {theme}:")
        for cluster, sentiments in divergence.items():
            pos = sentiments.get('Positive', 0)
            neg = sentiments.get('Negative', 0)
            logger.info(f"      {cluster}: {pos:.1f}% positive, {neg:.1f}% negative")

    # Save report
    report_path = Path("data/cross_cluster_report.json")
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    logger.info(f"\n💾 Full report saved to {report_path}")

    logger.info("="*60)
