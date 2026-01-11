"""Temporal trend analysis for tracking narrative evolution over time."""

import os
import sys
import json
import logging
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Optional

from vibes_tracker.utils.config_loader import load_config
from vibes_tracker.utils.logger import setup_logger


def save_historical_snapshot(config, logger):
    """
    Save current data to historical archive.

    Creates a dated directory and copies current CSV files.
    """
    # Get current date for directory name
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    historical_dir = Path("data/historical") / today
    historical_dir.mkdir(parents=True, exist_ok=True)

    # Copy current files to historical
    cluster_data_path = Path(config.paths.cluster_data)
    analyzed_data_path = Path(config.paths.analyzed_data)

    if cluster_data_path.exists():
        import shutil
        shutil.copy(cluster_data_path, historical_dir / "cluster_data.csv")
        logger.info(f"Saved cluster data snapshot to {historical_dir}")

    if analyzed_data_path.exists():
        import shutil
        shutil.copy(analyzed_data_path, historical_dir / "analyzed_data.csv")
        logger.info(f"Saved analyzed data snapshot to {historical_dir}")

    return historical_dir


def load_historical_runs(days_back: int = 30) -> List[Tuple[str, pd.DataFrame]]:
    """
    Load historical analyzed data from past N days.

    Args:
        days_back: Number of days to look back

    Returns:
        List of (date_string, dataframe) tuples
    """
    historical_dir = Path("data/historical")
    if not historical_dir.exists():
        return []

    runs = []
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

    for date_dir in sorted(historical_dir.iterdir()):
        if not date_dir.is_dir():
            continue

        try:
            # Parse directory name as date
            dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
            if dir_date.replace(tzinfo=timezone.utc) < cutoff_date:
                continue

            # Load analyzed data if it exists
            analyzed_file = date_dir / "analyzed_data.csv"
            if analyzed_file.exists():
                df = pd.read_csv(analyzed_file)
                runs.append((date_dir.name, df))
        except (ValueError, FileNotFoundError) as e:
            continue

    return runs


def extract_themes_by_cluster(df: pd.DataFrame) -> Dict[str, List[str]]:
    """
    Extract all themes grouped by cluster.

    Args:
        df: DataFrame with 'cluster' and 'themes' columns

    Returns:
        Dictionary mapping cluster name to list of themes
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


def calculate_theme_frequency(themes: List[str]) -> Dict[str, int]:
    """
    Calculate frequency of each theme.

    Args:
        themes: List of theme strings

    Returns:
        Dictionary mapping theme to count
    """
    return dict(Counter(themes))


def compare_theme_trends(historical_runs: List[Tuple[str, pd.DataFrame]],
                        cluster: Optional[str] = None) -> pd.DataFrame:
    """
    Compare theme prevalence over time.

    Args:
        historical_runs: List of (date, dataframe) tuples
        cluster: Optional cluster name to filter by

    Returns:
        DataFrame with dates as index and themes as columns
    """
    if not historical_runs:
        return pd.DataFrame()

    # Build time series of theme frequencies
    theme_series = []

    for date, df in historical_runs:
        if cluster:
            df = df[df['cluster'] == cluster]

        themes_by_cluster = extract_themes_by_cluster(df)
        all_themes = []
        for cluster_themes in themes_by_cluster.values():
            all_themes.extend(cluster_themes)

        freq = calculate_theme_frequency(all_themes)
        freq['date'] = date
        theme_series.append(freq)

    # Convert to DataFrame
    df_trends = pd.DataFrame(theme_series)
    df_trends = df_trends.set_index('date')
    df_trends = df_trends.fillna(0)

    return df_trends


def identify_emerging_themes(df_trends: pd.DataFrame, threshold: float = 2.0) -> List[str]:
    """
    Identify themes that are increasing in frequency.

    Args:
        df_trends: DataFrame with dates and theme frequencies
        threshold: Minimum increase ratio to be considered "emerging"

    Returns:
        List of emerging theme names
    """
    if len(df_trends) < 2:
        return []

    emerging = []

    # Compare most recent to previous period
    recent = df_trends.iloc[-1]
    previous = df_trends.iloc[-2]

    for theme in df_trends.columns:
        prev_count = previous.get(theme, 0)
        recent_count = recent.get(theme, 0)

        # Avoid division by zero
        if prev_count == 0:
            if recent_count > 0:
                emerging.append(theme)
        elif recent_count / prev_count >= threshold:
            emerging.append(theme)

    return emerging


def identify_declining_themes(df_trends: pd.DataFrame, threshold: float = 0.5) -> List[str]:
    """
    Identify themes that are decreasing in frequency.

    Args:
        df_trends: DataFrame with dates and theme frequencies
        threshold: Maximum ratio to be considered "declining"

    Returns:
        List of declining theme names
    """
    if len(df_trends) < 2:
        return []

    declining = []

    # Compare most recent to previous period
    recent = df_trends.iloc[-1]
    previous = df_trends.iloc[-2]

    for theme in df_trends.columns:
        prev_count = previous.get(theme, 0)
        recent_count = recent.get(theme, 0)

        # Theme must have existed before
        if prev_count > 0:
            if recent_count == 0:
                declining.append(theme)
            elif recent_count / prev_count <= threshold:
                declining.append(theme)

    return declining


def calculate_sentiment_trends(historical_runs: List[Tuple[str, pd.DataFrame]],
                               cluster: Optional[str] = None) -> pd.DataFrame:
    """
    Calculate sentiment distribution over time.

    Args:
        historical_runs: List of (date, dataframe) tuples
        cluster: Optional cluster name to filter by

    Returns:
        DataFrame with sentiment percentages over time
    """
    sentiment_series = []

    for date, df in historical_runs:
        if cluster:
            df = df[df['cluster'] == cluster]

        # Count sentiments
        total = len(df[df['sentiment'].notna()])
        if total == 0:
            continue

        sentiment_counts = df['sentiment'].value_counts()

        sentiment_pct = {
            'date': date,
            'Positive': (sentiment_counts.get('Positive', 0) / total) * 100,
            'Neutral': (sentiment_counts.get('Neutral', 0) / total) * 100,
            'Negative': (sentiment_counts.get('Negative', 0) / total) * 100,
            'Mixed': (sentiment_counts.get('Mixed', 0) / total) * 100
        }
        sentiment_series.append(sentiment_pct)

    df_sentiment = pd.DataFrame(sentiment_series)
    if not df_sentiment.empty:
        df_sentiment = df_sentiment.set_index('date')

    return df_sentiment


def generate_temporal_report(days_back: int = 30, cluster: Optional[str] = None) -> Dict:
    """
    Generate a comprehensive temporal analysis report.

    Args:
        days_back: Number of days to analyze
        cluster: Optional cluster to focus on

    Returns:
        Dictionary with analysis results
    """
    logger = logging.getLogger("temporal-analysis")

    # Load historical data
    historical_runs = load_historical_runs(days_back)

    if len(historical_runs) < 2:
        logger.warning(f"Need at least 2 historical runs for trend analysis. Found: {len(historical_runs)}")
        return {
            'status': 'insufficient_data',
            'runs_found': len(historical_runs),
            'message': 'Need at least 2 historical snapshots for trend analysis'
        }

    logger.info(f"Analyzing {len(historical_runs)} historical runs over {days_back} days")

    # Calculate theme trends
    theme_trends = compare_theme_trends(historical_runs, cluster)

    # Identify emerging and declining themes
    emerging = identify_emerging_themes(theme_trends)
    declining = identify_declining_themes(theme_trends)

    # Calculate sentiment trends
    sentiment_trends = calculate_sentiment_trends(historical_runs, cluster)

    # Get top themes from most recent run
    if theme_trends is not None and not theme_trends.empty:
        most_recent = theme_trends.iloc[-1]
        top_themes = most_recent.nlargest(10).to_dict()
    else:
        top_themes = {}

    report = {
        'status': 'success',
        'period': {
            'days_back': days_back,
            'start_date': historical_runs[0][0],
            'end_date': historical_runs[-1][0],
            'num_snapshots': len(historical_runs)
        },
        'cluster': cluster or 'all_clusters',
        'top_themes': top_themes,
        'emerging_themes': emerging[:10],  # Top 10
        'declining_themes': declining[:10],  # Top 10
        'theme_trends': theme_trends.to_dict() if not theme_trends.empty else {},
        'sentiment_trends': sentiment_trends.to_dict() if not sentiment_trends.empty else {}
    }

    return report


if __name__ == "__main__":
    # Change to project root if running from src/
    if os.path.basename(os.getcwd()) == 'src':
        os.chdir('..')

    # Load configuration
    config = load_config()
    logger = setup_logger("temporal-analysis", level=logging.INFO)

    logger.info("="*60)
    logger.info("YouTube Vibes Tracker - Temporal Trend Analysis")
    logger.info("="*60)

    # Generate report for all clusters
    report = generate_temporal_report(days_back=30)

    if report['status'] == 'success':
        logger.info(f"\n📊 Temporal Analysis Report ({report['period']['start_date']} to {report['period']['end_date']})")
        logger.info(f"   Snapshots analyzed: {report['period']['num_snapshots']}")

        logger.info(f"\n🔥 Top Current Themes:")
        for theme, count in list(report['top_themes'].items())[:5]:
            logger.info(f"   - {theme}: {count} mentions")

        logger.info(f"\n📈 Emerging Themes (increasing):")
        for theme in report['emerging_themes'][:5]:
            logger.info(f"   - {theme}")

        logger.info(f"\n📉 Declining Themes (decreasing):")
        for theme in report['declining_themes'][:5]:
            logger.info(f"   - {theme}")

        # Save report to JSON
        report_path = Path("data/temporal_report.json")
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        logger.info(f"\n💾 Full report saved to {report_path}")
    else:
        logger.warning(f"⚠️  {report['message']}")

    logger.info("="*60)
