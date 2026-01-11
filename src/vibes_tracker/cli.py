#!/usr/bin/env python3
"""
YouTube Vibes Tracker - Main CLI Entry Point

Unified command-line interface for all pipeline operations.
"""

import os
import sys
import argparse
from pathlib import Path


def main():
    """Main CLI entry point with subcommands."""
    parser = argparse.ArgumentParser(
        description='YouTube Vibes Tracker - Analyze narrative ecosystems across YouTube channels',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline run
  vibes-tracker ingest
  vibes-tracker analyze --workers 10
  vibes-tracker visualize

  # Incremental updates
  vibes-tracker ingest --incremental
  vibes-tracker analyze --incremental

  # Temporal analysis
  vibes-tracker temporal --days-back 30

  # Cross-cluster comparison
  vibes-tracker compare

  # Combined workflow
  vibes-tracker pipeline --incremental
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # --- Ingest Command ---
    ingest_parser = subparsers.add_parser(
        'ingest',
        help='Fetch video metadata from YouTube API'
    )
    ingest_parser.add_argument(
        '--incremental',
        action='store_true',
        help='Only fetch new videos since last run'
    )
    ingest_parser.add_argument(
        '--full-refresh',
        action='store_true',
        help='Fetch all videos (disable incremental mode)'
    )

    # --- Analyze Command ---
    analyze_parser = subparsers.add_parser(
        'analyze',
        help='Run AI analysis on video transcripts'
    )
    analyze_parser.add_argument(
        '--incremental',
        action='store_true',
        help='Only analyze new videos since last run'
    )
    analyze_parser.add_argument(
        '--full-refresh',
        action='store_true',
        help='Analyze all videos (disable incremental mode)'
    )
    analyze_parser.add_argument(
        '--workers',
        type=int,
        default=10,
        help='Number of parallel workers (default: 10)'
    )

    # --- Visualize Command ---
    visualize_parser = subparsers.add_parser(
        'visualize',
        help='Generate all visualizations from analyzed data'
    )
    visualize_parser.add_argument(
        '--output-dir',
        type=str,
        default='figures',
        help='Output directory for figures (default: figures)'
    )

    # --- Temporal Command ---
    temporal_parser = subparsers.add_parser(
        'temporal',
        help='Run temporal trend analysis'
    )
    temporal_parser.add_argument(
        '--days-back',
        type=int,
        default=30,
        help='Number of days to analyze (default: 30)'
    )
    temporal_parser.add_argument(
        '--start-date',
        type=str,
        help='Start date for analysis (YYYY-MM-DD)'
    )
    temporal_parser.add_argument(
        '--end-date',
        type=str,
        help='End date for analysis (YYYY-MM-DD)'
    )

    # --- Compare Command ---
    compare_parser = subparsers.add_parser(
        'compare',
        help='Run cross-cluster comparison analysis'
    )
    compare_parser.add_argument(
        '--output',
        type=str,
        default='figures/comparison',
        help='Output directory for comparison plots (default: figures/comparison)'
    )

    # --- Collect Historical Command ---
    historical_parser = subparsers.add_parser(
        'collect-historical',
        help='Collect multi-year historical data'
    )
    historical_parser.add_argument(
        '--start-year',
        type=int,
        help='Start year (e.g., 2022)'
    )
    historical_parser.add_argument(
        '--end-year',
        type=int,
        help='End year (e.g., 2024)'
    )
    historical_parser.add_argument(
        '--start-date',
        type=str,
        help='Start date (YYYY-MM-DD)'
    )
    historical_parser.add_argument(
        '--end-date',
        type=str,
        help='End date (YYYY-MM-DD)'
    )
    historical_parser.add_argument(
        '--frequency',
        type=str,
        choices=['monthly', 'quarterly', 'yearly'],
        default='monthly',
        help='Collection frequency (default: monthly)'
    )

    # --- Pipeline Command (Run all stages) ---
    pipeline_parser = subparsers.add_parser(
        'pipeline',
        help='Run full pipeline: ingest → analyze → visualize'
    )
    pipeline_parser.add_argument(
        '--incremental',
        action='store_true',
        help='Use incremental mode for all stages'
    )
    pipeline_parser.add_argument(
        '--workers',
        type=int,
        default=10,
        help='Number of parallel workers for analysis (default: 10)'
    )

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Change to project root (cli.py is at src/vibes_tracker/cli.py)
    project_root = Path(__file__).parent.parent.parent
    os.chdir(project_root)

    # Execute command
    if args.command == 'ingest':
        run_ingest(args)
    elif args.command == 'analyze':
        run_analyze(args)
    elif args.command == 'visualize':
        run_visualize(args)
    elif args.command == 'temporal':
        run_temporal(args)
    elif args.command == 'compare':
        run_compare(args)
    elif args.command == 'collect-historical':
        run_collect_historical(args)
    elif args.command == 'pipeline':
        run_pipeline(args)


def run_ingest(args):
    """Run data ingestion."""
    print("🔄 Running data ingestion...")
    from vibes_tracker.core.ingest import ingest_clusters
    from vibes_tracker.utils.config_loader import load_config
    from vibes_tracker.utils.logger import setup_logger, QuotaTracker
    from vibes_tracker.utils.metadata_manager import MetadataManager
    from dotenv import load_dotenv
    import json
    import pandas as pd
    from datetime import datetime, timezone

    load_dotenv()
    config = load_config()
    logger = setup_logger("ingest")
    quota_tracker = QuotaTracker(logger)
    metadata_mgr = MetadataManager(logger=logger)

    # Load cluster configuration
    with open(config.paths.cluster_config, 'r') as f:
        clusters = json.load(f)

    api_key = os.getenv("YOUTUBE_API_KEY")

    # Determine mode
    incremental = args.incremental or (not args.full_refresh and metadata_mgr.should_run_incremental("ingest"))

    # Run ingestion
    df = ingest_clusters(clusters, api_key, config, logger, quota_tracker,
                        incremental=incremental, metadata_mgr=metadata_mgr)

    if not df.empty:
        df['run_timestamp'] = datetime.now(timezone.utc).isoformat()

        output_path = config.paths.cluster_data

        # Append or overwrite
        if incremental and os.path.exists(output_path):
            existing_df = pd.read_csv(output_path)
            df = pd.concat([existing_df, df], ignore_index=True)
            df = df.drop_duplicates(subset=['video_id'], keep='last')

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df.to_csv(output_path, index=False)

        metadata_mgr.update_ingest(len(df))

        from vibes_tracker.analysis.temporal import save_historical_snapshot
        save_historical_snapshot(config, logger)

        print(f"✅ Ingestion complete! Saved {len(df)} videos to {output_path}")
    else:
        print("⚠️  No data collected.")


def run_analyze(args):
    """Run AI analysis."""
    print("🤖 Running AI analysis...")
    sys.argv = ['analyze.py']
    if args.incremental:
        sys.argv.append('--incremental')
    if args.full_refresh:
        sys.argv.append('--full-refresh')
    sys.argv.extend(['--workers', str(args.workers)])

    from vibes_tracker.core.analyze import run_analysis
    run_analysis()
    print("✅ Analysis complete!")


def run_visualize(args):
    """Generate visualizations."""
    print("📊 Generating visualizations...")
    from vibes_tracker.core.visualize import generate_all_visualizations
    from vibes_tracker.utils.config_loader import load_config
    from vibes_tracker.utils.logger import setup_logger

    config = load_config()
    logger = setup_logger("visualize")

    generate_all_visualizations()
    print(f"✅ Visualizations saved to {args.output_dir}/")


def run_temporal(args):
    """Run temporal analysis."""
    print("📈 Running temporal trend analysis...")
    from vibes_tracker.analysis.temporal import run_temporal_analysis
    from vibes_tracker.utils.config_loader import load_config
    from vibes_tracker.utils.logger import setup_logger

    config = load_config()
    logger = setup_logger("temporal")

    run_temporal_analysis(
        config,
        logger,
        days_back=args.days_back,
        start_date=args.start_date,
        end_date=args.end_date
    )
    print("✅ Temporal analysis complete!")


def run_compare(args):
    """Run cross-cluster comparison."""
    print("🔍 Running cross-cluster comparison...")
    from vibes_tracker.analysis.cross_cluster import run_comparison_analysis
    from vibes_tracker.utils.config_loader import load_config
    from vibes_tracker.utils.logger import setup_logger

    config = load_config()
    logger = setup_logger("compare")

    run_comparison_analysis(config, logger, output_dir=args.output)
    print(f"✅ Comparison complete! Results saved to {args.output}/")


def run_collect_historical(args):
    """Collect multi-year historical data."""
    print("🕰️  Collecting historical data...")
    sys.argv = ['collect_historical_data.py']

    if args.start_year:
        sys.argv.extend(['--start-year', str(args.start_year)])
    if args.end_year:
        sys.argv.extend(['--end-year', str(args.end_year)])
    if args.start_date:
        sys.argv.extend(['--start-date', args.start_date])
    if args.end_date:
        sys.argv.extend(['--end-date', args.end_date])
    sys.argv.extend(['--frequency', args.frequency])

    # Import and run the script
    import importlib.util
    spec = importlib.util.spec_from_file_location("collect_historical_data", "scripts/collect_historical_data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    print("✅ Historical data collection complete!")


def run_pipeline(args):
    """Run full pipeline."""
    print("🚀 Running full pipeline: ingest → analyze → visualize")

    # Step 1: Ingest
    ingest_args = argparse.Namespace(
        incremental=args.incremental,
        full_refresh=not args.incremental
    )
    run_ingest(ingest_args)

    # Step 2: Analyze
    analyze_args = argparse.Namespace(
        incremental=args.incremental,
        full_refresh=not args.incremental,
        workers=args.workers
    )
    run_analyze(analyze_args)

    # Step 3: Visualize
    visualize_args = argparse.Namespace(output_dir='figures')
    run_visualize(visualize_args)

    print("✅ Full pipeline complete!")


if __name__ == "__main__":
    main()
