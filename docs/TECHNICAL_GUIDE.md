# Technical Guide

For developers who want to understand or modify the codebase.

## Architecture Overview

The pipeline is built around 3 main stages that can run independently:

```
YouTube API → Ingest → CSV
CSV → Analyze (Gemini) → Enriched CSV
Enriched CSV → Visualize → Plots
```

Each stage reads from and writes to CSV files, making the pipeline easy to debug and restart.

## Key Components

### Data Flow

```
config/clusters.json
    ↓
src/ingest.py (YouTube API)
    ↓
data/cluster_data.csv
    ↓
src/analyze.py (Gemini API)
    ↓
data/analyzed_data.csv
    ↓
src/visualize.py
    ↓
figures/*.png
```

### Module Breakdown

**Core Pipeline:**
- `src/ingest.py` - YouTube data fetcher
- `src/analyze.py` - Gemini-based analysis
- `src/visualize.py` - Visualization orchestrator

**Analysis Modules:**
- `src/temporal_analysis.py` - Time-series analysis
- `src/cross_cluster_analysis.py` - Cluster comparison

**Utilities:**
- `src/utils/config_loader.py` - YAML config with Pydantic validation
- `src/utils/logger.py` - Logging setup and quota tracking
- `src/utils/cache_manager.py` - File-based caching
- `src/utils/metadata_manager.py` - Pipeline state tracking

**Visualizations:**
- `src/visualizations/word_clouds.py` - Word cloud generation
- `src/visualizations/temporal_plots.py` - Time-series plots
- `src/visualizations/cluster_comparison.py` - Heatmaps and comparisons
- `src/visualizations/sentiment_plots.py` - Sentiment charts

**CLI:**
- `src/main.py` - Argument parsing and command routing

## Configuration System

Uses Pydantic for type-safe configuration:

```python
from src.utils.config_loader import load_config

config = load_config()  # Loads config/pipeline_config.yaml

# Access config
videos_per_channel = config.ingest.videos_per_channel
model_name = config.analysis.model
cache_dir = config.analysis.cache_dir
```

Config is validated at load time - typos or invalid values will raise errors immediately.

## Caching Strategy

Two-level cache in `data/cache/`:

1. **Transcripts** (`data/cache/transcripts/{video_id}.txt`)
   - Raw transcript text
   - Saves YouTube API calls

2. **Analysis** (`data/cache/analysis/{video_id}.json`)
   - Full Gemini response
   - Saves Gemini API calls

Cache is checked before every API call. Delete the cache directory to force re-processing.

## Incremental Processing

`MetadataManager` tracks pipeline state in `data/metadata.json`:

```json
{
  "last_ingest_timestamp": "2025-12-28T12:00:00Z",
  "last_analysis_timestamp": "2025-12-28T12:15:00Z",
  "total_videos_ingested": 5000,
  "total_videos_analyzed": 4500,
  "pipeline_runs": [...]
}
```

On incremental runs:
1. Load last run timestamp
2. Filter videos: `df = df[df['run_timestamp'] > last_run]`
3. Process only new videos
4. Merge with existing CSV
5. Deduplicate by `video_id`

## Parallel Processing

Uses `ThreadPoolExecutor` for I/O-bound operations:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def process_video(row):
    # Fetch transcript, call Gemini, return results
    pass

with ThreadPoolExecutor(max_workers=10) as executor:
    futures = {executor.submit(process_video, row): row
               for _, row in df.iterrows()}

    for future in as_completed(futures):
        result = future.result()
```

Worker count is configurable via `--workers N` flag.

## API Integration

### YouTube Data API v3

Two main operations:

1. **Resolve channel handle to ID** (~100 units)
```python
youtube.search().list(
    part="snippet",
    type="channel",
    q=handle,
    maxResults=1
)
```

2. **Fetch recent videos** (~2 units)
```python
# Get uploads playlist ID
youtube.channels().list(id=channel_id, part='contentDetails')

# Get videos from playlist
youtube.playlistItems().list(
    playlistId=uploads_id,
    part='snippet',
    maxResults=30
)
```

Channel IDs are cached in `data/channel_ids.json` to avoid the expensive search operation.

### Gemini API

Structured output with JSON schema:

```python
response = client.models.generate_content(
    model="gemini-1.5-flash",
    contents=prompt,
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=schema  # Enforces structure
    )
)
```

The schema ensures consistent output format. Gemini returns valid JSON matching the schema.

## Temporal Analysis

Historical snapshots are saved after each run:

```
data/historical/
├── 2024-12-01/
│   ├── cluster_data.csv
│   └── analyzed_data.csv
├── 2024-12-02/
│   ├── cluster_data.csv
│   └── analyzed_data.csv
...
```

Temporal analysis loads multiple snapshots and compares:

```python
def compare_theme_trends(snapshots):
    # Extract themes from each snapshot
    # Count frequency over time
    # Identify rising/falling topics
    pass
```

## Data Schema

### cluster_data.csv (after ingest)
```
video_id, title, publish_date, channel_name, url, cluster, run_timestamp
```

### analyzed_data.csv (after analysis)
```
[all columns from cluster_data.csv] +
summary, themes, sentiment, framing, theme_categories, named_entities, analysis_timestamp
```

Themes are pipe-separated: `"Climate Change | Immigration | Economy"`

## Adding New Features

### Add a new visualization

1. Create function in `src/visualizations/`:
```python
def plot_my_chart(df, output_dir):
    # Create plot
    plt.savefig(f"{output_dir}/my_chart.png")
```

2. Import and call in `src/visualize.py`:
```python
from src.visualizations.my_module import plot_my_chart

def generate_all_visualizations(config, logger):
    # ...
    plot_my_chart(df, output_dir)
```

### Add a new AI analysis field

1. Update schema in `src/analyze.py`:
```python
response_schema = {
    "properties": {
        # ... existing fields ...
        "my_new_field": {
            "type": "string",
            "description": "What this field captures"
        }
    },
    "required": ["my_new_field", ...]
}
```

2. Update prompt to ask for it
3. Extract in `process_video()`:
```python
result['my_new_field'] = data.get('my_new_field')
```

4. Add column to DataFrame:
```python
df['my_new_field'] = df['video_id'].map(...)
```

### Add a CLI command

Add subparser in `src/main.py`:

```python
my_parser = subparsers.add_parser('my-command', help='Do something')
my_parser.add_argument('--option', help='An option')

# Add handler
def run_my_command(args):
    # Implementation
    pass

# Call in main()
elif args.command == 'my-command':
    run_my_command(args)
```

## Testing Strategy

No formal test suite (research tool), but:

1. **Incremental development** - test each module independently
2. **Sample data** - use small datasets for faster iteration
3. **Logging** - check `logs/` for detailed execution traces
4. **Caching** - speeds up repeated testing

To test without API calls:
- Use cached data
- Mock API responses
- Run on historical CSV files

## Performance Optimization

### Current bottlenecks

1. **Gemini API calls** - 0.5-1s per video
   - Parallelized with ThreadPoolExecutor
   - Cached after first analysis

2. **Transcript fetching** - 0.1-0.3s per video
   - Parallelized with ThreadPoolExecutor
   - Cached after first fetch

3. **YouTube API quota** - 10,000 units/day
   - Channel ID caching saves 98 units per channel
   - Incremental mode reduces calls dramatically

### Profiling

Add timing to any function:

```python
import time

start = time.time()
# ... code ...
logger.info(f"Operation took {time.time() - start:.2f}s")
```

## Common Patterns

### Reading config
```python
from src.utils.config_loader import load_config
config = load_config()
```

### Setting up logging
```python
from src.utils.logger import setup_logger, QuotaTracker
logger = setup_logger("my_module")
quota_tracker = QuotaTracker(logger)
quota_tracker.log_youtube_api_call(units, "description")
```

### Caching operations
```python
from src.utils.cache_manager import CacheManager
cache = CacheManager(config.analysis.cache_dir, logger)

cached = cache.get_transcript(video_id)
if cached:
    return cached

# ... fetch data ...
cache.save_transcript(video_id, data)
```

### Incremental processing
```python
from src.utils.metadata_manager import MetadataManager
metadata = MetadataManager(logger=logger)

if metadata.should_run_incremental("ingest"):
    last_run = metadata.get_last_ingest_timestamp()
    df = df[df['run_timestamp'] > last_run]

metadata.update_ingest(len(df))
```

## Debugging

### Common issues

**Import errors:**
- Make sure you're running from project root
- Virtual environment activated?
- Check `sys.path.insert(0, ...)` in script headers

**Config not loading:**
- Check `config/pipeline_config.yaml` syntax
- Pydantic will show validation errors
- Logger initialized before config?

**Cache not working:**
- Check permissions on `data/cache/`
- Check cache directory path in config
- Delete cache to force refresh

**Parallel processing failures:**
- Exceptions in worker threads are caught and logged
- Check logs for individual video failures
- Reduce `--workers` if hitting rate limits

### Useful log patterns

```bash
# Find errors
grep "ERROR" logs/analyze.log

# Find quota usage
grep "API Usage" logs/*.log

# Find cache stats
grep "Cache" logs/*.log

# See what videos were processed
grep "Analyzing:" logs/analyze.log
```

## Code Style

- Type hints on function signatures
- Docstrings for public functions
- Config over hardcoding
- Logging over print statements
- Early returns for error cases
- Descriptive variable names

Example:

```python
def process_video(row: pd.Series, client, cache_manager,
                  config, logger, quota_tracker) -> dict:
    """
    Process a single video: fetch transcript and analyze.

    Args:
        row: DataFrame row with video metadata
        client: Gemini API client
        cache_manager: Cache manager instance
        config: Pipeline configuration
        logger: Logger instance
        quota_tracker: API quota tracker

    Returns:
        dict: Analysis results
    """
    video_id = row['video_id']

    # Check cache first
    cached = cache_manager.get_analysis(video_id)
    if cached:
        return cached

    # ... implementation ...
```

## Deployment

### Production checklist

- [ ] Set up `.env` with production API keys
- [ ] Configure `config/clusters.json` with target channels
- [ ] Test with `--workers 5` first (conservative)
- [ ] Set up cron for incremental runs
- [ ] Monitor `logs/` for issues
- [ ] Back up `data/` directory periodically
- [ ] Set up log rotation (already configured)

### Cron example

```bash
# Daily at 2am
0 2 * * * cd /path/to/vibes-tracker && \
  source .venv/bin/activate && \
  python src/main.py pipeline --incremental >> /var/log/vibes-tracker.log 2>&1
```

## Further Reading

- [README](../README.md) - User documentation
- [Getting Started](GETTING_STARTED.md) - First run guide
- [Multi-Year Analysis](MULTI_YEAR_ANALYSIS_GUIDE.md) - Historical data collection
- [Implementation Summary](../results/IMPLEMENTATION_SUMMARY.md) - Feature details
