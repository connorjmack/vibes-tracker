# Retroactive Transcript Search

Build a complete dataset for a YouTube channel by retroactively downloading all available transcripts from a specific time period.

## Features

- **Smart Resume**: Checks for existing transcripts and only downloads missing ones
- **Resilient**: Saves each transcript immediately - no data loss if API ban occurs
- **Progress Tracking**: Maintains progress in JSON file, fully resumable
- **Rate Limited**: Respects API limits to avoid bans
- **Organized Storage**: Saves transcripts to `data/{channel}/` with clear naming

## Quick Start

### Basic Usage

Download all transcripts for a channel from 2020-2023:

```bash
python scripts/retroactive_search.py --channel @joerogan --start-year 2020 --end-year 2023
```

### Advanced Options

Limit downloads per run (useful for rate limiting):

```bash
# Download only 50 transcripts per run
python scripts/retroactive_search.py --channel @joerogan --start-year 2020 --end-year 2023 --max-per-run 50
```

Use specific date ranges:

```bash
python scripts/retroactive_search.py --channel @joerogan --start-date 2020-06-01 --end-date 2021-12-31
```

Custom output directory:

```bash
python scripts/retroactive_search.py --channel @joerogan --start-year 2020 --end-year 2023 --output-dir my_data
```

## How It Works

1. **Check Existing Data**: Scans `data/{channel}/` for existing transcripts
2. **Fetch Video List**: Gets all videos from YouTube in the date range (cached for future runs)
3. **Download Missing Transcripts**: Downloads transcripts one at a time, saving immediately
4. **Update Index**: Maintains `index.csv` with all video metadata
5. **Track Progress**: Saves progress after each transcript for resumability

## Output Structure

```
data/
└── {channel}/
    ├── index.csv                    # Video metadata and filenames
    ├── progress.json                # Collection progress tracking
    ├── video_list.json              # Cached video list from YouTube
    ├── 2020-01-15_{video_id}.txt   # Individual transcripts
    ├── 2020-01-16_{video_id}.txt
    └── ...
```

### index.csv

Contains metadata for all videos:

| Column | Description |
|--------|-------------|
| video_id | YouTube video ID |
| publish_date | ISO 8601 timestamp |
| title | Video title |
| filename | Transcript filename (or null if failed) |
| status | 'downloaded', 'exists', or 'failed' |

### progress.json

Tracks collection progress:

```json
{
  "last_run": "2026-01-11T10:00:00Z",
  "videos_processed": 150,
  "videos_downloaded": 120,
  "videos_failed": 30,
  "last_video_id": "dQw4w9WgXcQ"
}
```

## Handling API Limits

If you encounter rate limiting or API bans:

1. **Wait and Resume**: Just run the script again later - it will resume where it left off
2. **Use --max-per-run**: Limit downloads per run to stay under daily quotas
3. **Check Logs**: Monitor `logs/retroactive-search.log` for issues
4. **Rate Limiting Config**: Adjust delays in `config/pipeline_config.yaml` under `rate_limiting.transcript_api`

### Daily Limits

- **YouTube Data API**: 10,000 units/day
  - Resolving channel ID: ~100 units (one-time, cached)
  - Fetching video list: ~1 unit per 50 videos (one-time, cached)
  - Total for initial setup: Usually < 200 units
- **Transcript API**: No official limit, but rate limited by the script to avoid IP blocks

### Recommended Approach

For large collections (1000+ videos):

```bash
# Day 1: Fetch video list and first 100 transcripts
python scripts/retroactive_search.py --channel @joerogan --start-year 2020 --end-year 2023 --max-per-run 100

# Day 2+: Run again daily until complete
python scripts/retroactive_search.py --channel @joerogan --start-year 2020 --end-year 2023 --max-per-run 100
```

## Use Cases

### 1. Complete Channel Archive

Build a complete transcript archive for analysis:

```bash
python scripts/retroactive_search.py --channel @joerogan --start-year 2015 --end-year 2024
```

### 2. Event Analysis

Collect transcripts around a specific event:

```bash
python scripts/retroactive_search.py --channel @cnn --start-date 2024-11-01 --end-date 2024-11-30
```

### 3. Multiple Channels

Run for multiple channels sequentially:

```bash
for channel in @joerogan @lexfridman @hubermanlab; do
    python scripts/retroactive_search.py --channel $channel --start-year 2020 --end-year 2023 --max-per-run 50
    sleep 3600  # Wait 1 hour between channels
done
```

## Resumability

The script is fully resumable:

- **Stop anytime**: Press Ctrl+C to stop - progress is saved after each transcript
- **Resume later**: Run the same command again - it will skip existing transcripts
- **No data loss**: Each transcript is saved immediately to disk
- **API ban protection**: If rate limited, just wait and resume later

## Integration with Main Pipeline

After collecting transcripts, use them in analysis:

```bash
# 1. Collect transcripts
python scripts/retroactive_search.py --channel @joerogan --start-year 2020 --end-year 2023

# 2. Create cluster_data.csv from the transcripts
# (Manual step: Convert data/{channel}/index.csv to data/cluster_data.csv format)

# 3. Run analysis
python src/main.py analyze

# 4. Generate visualizations
python src/main.py visualize
```

## Troubleshooting

### No transcripts available

Many videos don't have transcripts enabled. The script will mark these as 'failed' in the index.

### API quota exceeded

If you hit YouTube API quota:
- Wait until midnight PT for quota reset
- Use `--max-per-run` to limit downloads
- The video list is cached, so subsequent runs use less quota

### Rate limited by transcript API

If you're blocked from fetching transcripts:
- Wait a few hours before resuming
- Increase delays in `config/pipeline_config.yaml`
- Use `--max-per-run` to download in smaller batches

### Script crashes mid-run

No problem! Just run it again - progress is saved after each transcript.

## Comparison with Existing Scripts

| Feature | retroactive_search.py | collect_historical_data.py | incremental_historical_collection.py |
|---------|----------------------|---------------------------|-------------------------------------|
| **Purpose** | Single channel deep dive | Multi-cluster time periods | Incremental multi-year collection |
| **Storage** | `data/{channel}/` | `data/historical/{date}/` | `data/historical/{date}/` |
| **Transcripts** | ✅ One-at-a-time | ❌ Batch processing | ❌ Batch processing |
| **Resumable** | ✅ Per-video | ✅ Per-period | ✅ Per-period |
| **Use Case** | Channel archives | Event analysis | Multi-year datasets |

## Tips

1. **Start with a small range** to test (e.g., one month)
2. **Use --max-per-run** for large collections to avoid rate limits
3. **Monitor logs** for any issues
4. **Check index.csv** to see what's been downloaded
5. **Run regularly** if building a complete archive over time

## Command Reference

```bash
python scripts/retroactive_search.py \
    --channel HANDLE \           # Required: Channel handle (e.g., @joerogan)
    [--start-year YEAR] \        # Start year (use with --end-year)
    [--end-year YEAR] \          # End year (use with --start-year)
    [--start-date DATE] \        # Start date YYYY-MM-DD (use with --end-date)
    [--end-date DATE] \          # End date YYYY-MM-DD (use with --start-date)
    [--max-per-run N] \          # Max transcripts per run (optional)
    [--output-dir DIR]           # Output directory (default: data)
```

## See Also

- [Multi-Year Analysis Guide](MULTI_YEAR_ANALYSIS_GUIDE.md)
- [Main README](../README.md)
