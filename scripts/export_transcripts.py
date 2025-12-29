#!/usr/bin/env python3
"""
Export cached transcripts to various formats after analysis is complete.

Usage:
    # Export all transcripts to JSON
    python scripts/export_transcripts.py --format json --output transcripts.json

    # Export specific cluster to CSV
    python scripts/export_transcripts.py --cluster libs --format csv --output libs_transcripts.csv

    # Export with metadata
    python scripts/export_transcripts.py --format json --include-metadata --output full_export.json
"""

import os
import sys
import json
import argparse
import pandas as pd
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_cached_transcripts(cache_dir="data/cache/transcripts"):
    """Load all cached transcripts."""
    transcripts = []

    if not os.path.exists(cache_dir):
        print(f"❌ Cache directory not found: {cache_dir}")
        print("   Run analysis first: .venv/bin/python src/analyze.py")
        return transcripts

    cache_files = [f for f in os.listdir(cache_dir) if f.endswith('.json')]

    if not cache_files:
        print(f"⚠️  No cached transcripts found in {cache_dir}")
        return transcripts

    print(f"📂 Found {len(cache_files)} cached transcripts")

    for filename in cache_files:
        filepath = os.path.join(cache_dir, filename)
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                transcripts.append({
                    'video_id': data.get('video_id'),
                    'transcript': data.get('transcript'),
                    'cached_at': data.get('timestamp')
                })
        except Exception as e:
            print(f"⚠️  Error loading {filename}: {e}")

    return transcripts


def merge_with_metadata(transcripts, analyzed_data_path="data/analyzed_data.csv"):
    """Merge transcripts with video metadata and analysis."""
    if not os.path.exists(analyzed_data_path):
        print(f"⚠️  Analyzed data not found: {analyzed_data_path}")
        return transcripts

    df = pd.read_csv(analyzed_data_path)

    # Create transcript lookup
    transcript_dict = {t['video_id']: t for t in transcripts}

    # Merge
    merged = []
    for _, row in df.iterrows():
        video_id = row['video_id']
        if video_id in transcript_dict:
            merged.append({
                'video_id': video_id,
                'title': row['title'],
                'publish_date': row['publish_date'],
                'channel_name': row['channel_name'],
                'cluster': row['cluster'],
                'transcript': transcript_dict[video_id]['transcript'],
                'sentiment': row.get('sentiment'),
                'themes': row.get('themes'),
                'summary': row.get('summary'),
                'named_entities': row.get('named_entities')
            })

    print(f"✅ Merged transcripts with metadata for {len(merged)} videos")
    return merged


def export_to_json(data, output_path):
    """Export data to JSON format."""
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"✅ Exported to JSON: {output_path}")


def export_to_csv(data, output_path):
    """Export data to CSV format."""
    df = pd.DataFrame(data)
    df.to_csv(output_path, index=False)
    print(f"✅ Exported to CSV: {output_path}")


def export_to_txt(data, output_path):
    """Export transcripts to plain text files (one per video)."""
    output_dir = Path(output_path).parent / (Path(output_path).stem + "_txt")
    output_dir.mkdir(exist_ok=True)

    for item in data:
        video_id = item['video_id']
        transcript = item.get('transcript', '')

        if transcript:
            txt_file = output_dir / f"{video_id}.txt"
            with open(txt_file, 'w') as f:
                if 'title' in item:
                    f.write(f"Title: {item['title']}\n")
                    f.write(f"Video ID: {video_id}\n")
                    f.write(f"Date: {item.get('publish_date', 'N/A')}\n")
                    f.write(f"Channel: {item.get('channel_name', 'N/A')}\n")
                    f.write("\n" + "="*60 + "\n\n")
                f.write(transcript)

    print(f"✅ Exported {len(data)} transcripts to: {output_dir}/")


def main():
    parser = argparse.ArgumentParser(description='Export cached transcripts')
    parser.add_argument('--format', choices=['json', 'csv', 'txt'], default='json',
                       help='Output format (default: json)')
    parser.add_argument('--output', type=str, required=True,
                       help='Output file path')
    parser.add_argument('--cluster', type=str,
                       help='Filter by cluster (libs, right, mainstream, etc.)')
    parser.add_argument('--include-metadata', action='store_true',
                       help='Include video metadata and analysis results')

    args = parser.parse_args()

    print("="*60)
    print("📝 TRANSCRIPT EXPORT TOOL")
    print("="*60)

    # Load transcripts
    transcripts = load_cached_transcripts()

    if not transcripts:
        print("\n❌ No transcripts to export!")
        print("\n💡 Next steps:")
        print("   1. Wait for historical collection to complete")
        print("   2. Run: .venv/bin/python src/analyze.py --full-refresh")
        print("   3. Then run this export script again")
        return

    # Merge with metadata if requested
    if args.include_metadata:
        data = merge_with_metadata(transcripts)
    else:
        data = transcripts

    # Filter by cluster if specified
    if args.cluster and args.include_metadata:
        original_count = len(data)
        data = [d for d in data if d.get('cluster') == args.cluster]
        print(f"🔍 Filtered to {args.cluster} cluster: {len(data)}/{original_count} videos")

    if not data:
        print("❌ No data to export after filtering!")
        return

    # Export
    if args.format == 'json':
        export_to_json(data, args.output)
    elif args.format == 'csv':
        export_to_csv(data, args.output)
    elif args.format == 'txt':
        export_to_txt(data, args.output)

    print("\n" + "="*60)
    print(f"✅ Export complete: {len(data)} items")
    print("="*60)


if __name__ == '__main__':
    main()
