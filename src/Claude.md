# src/Claude.md - Source Code Technical Details

This document provides detailed technical information about the source code modules in the YouTube Vibes Tracker project.

## Module Overview

### Core Pipeline Modules

#### `main.py` - CLI Entry Point
**Location**: `src/main.py`
**Purpose**: Unified command-line interface for all pipeline operations

**Key Functions**:
- Argument parsing for all subcommands (ingest, analyze, visualize, temporal, compare)
- Orchestrates the pipeline workflow
- Handles command routing to appropriate modules

**Commands**:
- `ingest` - Fetch video metadata from YouTube
- `analyze` - Run AI analysis on transcripts
- `visualize` - Generate all visualizations
- `temporal` - Run temporal trend analysis
- `compare` - Cross-cluster comparison
- `pipeline` - Run complete workflow

**Usage**:
```python
python src/main.py <command> [options]
```

#### `ingest.py` - Data Collection
**Location**: `src/ingest.py`
**Purpose**: Fetches video metadata and transcripts from YouTube channels

**Key Features**:
- Resolves channel handles to channel IDs
- Fetches recent videos using YouTube Data API v3
- Downloads transcripts using youtube-transcript-api
- Organizes data by cluster
- Saves to `data/cluster_data.csv`

**Important Details**:
- Caches channel IDs to minimize API usage (100 units → 2 units per fetch)
- Handles missing transcripts gracefully (many channels disable them)
- Supports incremental mode to only fetch new videos
- Uses `src/utils/rate_limiter.py` to manage API quotas

**Key Configuration** (in `config/pipeline_config.yaml`):
```yaml
ingest:
  videos_per_channel: 30  # Number of recent videos to fetch
```

#### `analyze.py` - AI Analysis
**Location**: `src/analyze.py`
**Purpose**: Analyzes video transcripts using Google's Gemini API

**Analysis Fields Extracted**:
- **Core Themes**: 3-5 main topics discussed in the video
- **Theme Categories**: Political, Social, Economic, Cultural, International, Tech, Other
- **Sentiment**: Positive, Neutral, Negative, Mixed
- **Framing**: favorable, critical, neutral, alarmist
- **Named Entities**: Key people, organizations, events mentioned
- **Summary**: One-sentence takeaway

**Key Features**:
- Parallel processing with configurable workers (default: 10)
- Caching to avoid re-analyzing the same video
- Incremental mode to only analyze new videos
- Progress tracking with detailed logging
- Saves to `data/analyzed_data.csv`

**Important Implementation Details**:
- Uses prompts from `config/prompts.yaml`
- Implements retry logic for API failures
- Uses `src/utils/cache_manager.py` for persistent caching
- Each analysis is independent - perfect for parallel processing

**Configuration**:
```yaml
analysis:
  model: "gemini-1.5-flash"
  enable_caching: true
  max_workers: 10
```

#### `visualize.py` - Visualization Orchestration
**Location**: `src/visualize.py`
**Purpose**: Generates all visualizations from analyzed data

**Generates 25+ Visualizations**:
- Word clouds (titles and themes, per cluster + combined)
- Sentiment distribution charts
- Framing distribution charts
- View statistics
- All saved to `figures/` directory

**Dependencies**:
- Imports plotting functions from `src/visualizations/` modules
- Reads from `data/analyzed_data.csv`
- Uses color schemes defined in the visualization modules

#### `temporal_analysis.py` - Temporal Tracking
**Location**: `src/temporal_analysis.py`
**Purpose**: Analyzes how topics and sentiment evolve over time

**Key Features**:
- Theme prevalence over time
- Sentiment evolution tracking
- Emerging vs declining topics identification
- Configurable time window (e.g., `--days-back 30`)

**Data Requirements**:
- Needs historical snapshots in `data/historical/YYYY-MM-DD/`
- Use `scripts/collect_historical_data.py` to build historical dataset

#### `cross_cluster_analysis.py` - Cluster Comparison
**Location**: `src/cross_cluster_analysis.py`
**Purpose**: Compares what different clusters are focusing on

**Analysis Types**:
- Similarity heatmap between clusters
- Consensus topics (discussed across all clusters)
- Echo chamber topics (unique to one cluster)
- Theme distribution comparison

**Output**:
- Visualizations in `figures/`
- Comparative statistics

#### `daily_report.py` - Daily Reporting
**Location**: `src/daily_report.py`
**Purpose**: Generates daily word clouds and view statistics

**Features**:
- Word clouds for videos published on a specific date
- Filters by top 67% of views for quality content
- Cluster-specific visualizations with custom color schemes
- View distribution charts showing individual videos as stacked segments
- Saves to `data/reports/YYYY-MM-DD/`

**Usage**:
```bash
# Generate report for today
python src/daily_report.py

# Generate report for specific date
python src/daily_report.py --date 2025-01-10
```

### Utility Modules (`src/utils/`)

#### `config_loader.py`
**Purpose**: Loads and validates configuration files

**Loads**:
- `config/clusters.json` - Channel definitions
- `config/pipeline_config.yaml` - Pipeline settings
- `config/prompts.yaml` - AI prompt templates

**Key Functions**:
- `load_clusters()` - Returns cluster definitions
- `load_pipeline_config()` - Returns pipeline configuration
- `load_prompts()` - Returns AI prompts

#### `logger.py`
**Purpose**: Centralized logging infrastructure

**Features**:
- Console output with color coding
- File logging to `logs/` directory
- Configurable log levels
- Timestamps and module names in logs

**Usage**:
```python
from src.utils.logger import get_logger
logger = get_logger(__name__)
logger.info("Processing video...")
```

#### `cache_manager.py`
**Purpose**: Manages persistent caching for transcripts and analysis results

**Key Features**:
- File-based caching in `data/cache/`
- Separate caches for transcripts and analysis
- Cache hit/miss tracking
- Automatic cache directory creation

**Cache Structure**:
```
data/cache/
├── transcripts/
│   └── {video_id}.json
└── analysis/
    └── {video_id}.json
```

**Key Functions**:
- `get_cached_transcript(video_id)` - Retrieve cached transcript
- `cache_transcript(video_id, transcript)` - Store transcript
- `get_cached_analysis(video_id)` - Retrieve cached analysis
- `cache_analysis(video_id, analysis)` - Store analysis

#### `metadata_manager.py`
**Purpose**: Manages video metadata and incremental processing

**Key Features**:
- Tracks which videos have been processed
- Identifies new videos for incremental mode
- Maintains metadata consistency

**Usage in Incremental Mode**:
1. Load existing data from CSV
2. Fetch new videos from YouTube
3. Compare to find new videos
4. Only process the delta

#### `rate_limiter.py`
**Purpose**: Manages API rate limiting and quota tracking

**Features**:
- Tracks YouTube API quota usage
- Enforces rate limits to prevent quota exhaustion
- Provides quota usage statistics
- Implements exponential backoff for retries

**Key Implementation**:
- Token bucket algorithm for rate limiting
- Per-API endpoint quota tracking
- Configurable limits and time windows

### Visualization Modules (`src/visualizations/`)

#### `word_clouds.py`
**Purpose**: Generates word cloud visualizations

**Functions**:
- `generate_title_wordcloud(cluster_name, data)` - Word cloud from video titles
- `generate_theme_wordcloud(cluster_name, data)` - Word cloud from extracted themes
- `generate_combined_wordcloud(data)` - Combined word cloud across all clusters

**Styling**:
- Cluster-specific color schemes
- Custom stopwords to filter common words
- Configurable dimensions (default: 1200x800)

**Configuration**:
```yaml
visualization:
  wordcloud_width: 1200
  wordcloud_height: 800
  custom_stopwords: ["video", "podcast", "episode"]
```

#### `sentiment_plots.py`
**Purpose**: Creates sentiment and framing visualizations

**Visualizations**:
- Sentiment distribution (Positive/Neutral/Negative/Mixed)
- Framing distribution (Favorable/Critical/Neutral/Alarmist)
- Per-cluster comparisons

**Chart Types**:
- Bar charts
- Stacked bar charts
- Pie charts (optional)

#### `temporal_plots.py`
**Purpose**: Creates time-series visualizations

**Visualizations**:
- Theme prevalence over time (line charts)
- Sentiment evolution (time series)
- Emerging vs declining topics (trend analysis)
- Heatmaps of theme intensity over time

**Time Windows**:
- Configurable via `--days-back` parameter
- Supports daily, weekly, monthly aggregation

#### `cluster_comparison.py`
**Purpose**: Creates cross-cluster comparison visualizations

**Visualizations**:
- Similarity heatmap (cluster-to-cluster)
- Consensus vs echo chamber topics (Venn-style diagrams)
- Theme distribution comparison (side-by-side bar charts)
- Unique topic identification

**Similarity Metrics**:
- Jaccard similarity on themes
- Cosine similarity on theme vectors
- Overlap coefficients

## Data Flow

### Standard Pipeline Flow

1. **Ingest** (`ingest.py`):
   - Input: `config/clusters.json`
   - Process: Fetch from YouTube API
   - Output: `data/cluster_data.csv`

2. **Analyze** (`analyze.py`):
   - Input: `data/cluster_data.csv`
   - Process: AI analysis with Gemini
   - Output: `data/analyzed_data.csv`

3. **Visualize** (`visualize.py`):
   - Input: `data/analyzed_data.csv`
   - Process: Generate plots
   - Output: `figures/*.png`

### Incremental Pipeline Flow

1. **Ingest --incremental**:
   - Load existing `data/cluster_data.csv`
   - Fetch new videos only
   - Append to CSV

2. **Analyze --incremental**:
   - Load existing `data/analyzed_data.csv`
   - Check cache for each video
   - Only analyze new/uncached videos
   - Append to CSV

3. **Visualize**:
   - Regenerate all visualizations from complete dataset

## Performance Optimization

### Caching Strategy

**Transcript Caching**:
- Never re-fetch the same video transcript
- Saves YouTube API quota
- Stored in `data/cache/transcripts/`

**Analysis Caching**:
- Never re-analyze the same video
- Saves Gemini API quota
- Stored in `data/cache/analysis/`

### Parallel Processing

**Analyze Module**:
```python
# Default: 10 workers
python src/main.py analyze --workers 10

# Increase for faster processing (if API quota allows)
python src/main.py analyze --workers 20
```

**Implementation**:
- Uses `concurrent.futures.ThreadPoolExecutor`
- Each video analysis is independent
- Progress tracking with thread-safe counters

### Incremental Mode

**Benefits**:
- 100x faster than full refresh
- Minimal API usage
- Perfect for daily monitoring

**Usage**:
```bash
python src/main.py pipeline --incremental
```

**How It Works**:
1. Loads existing data
2. Identifies new videos by comparing video IDs
3. Only processes the delta
4. Appends to existing datasets

## Configuration Files

### `config/clusters.json`
Defines channel groups for analysis:
```json
{
  "cluster_name": ["@channel1", "@channel2", "@channel3"]
}
```

### `config/pipeline_config.yaml`
Pipeline settings:
```yaml
ingest:
  videos_per_channel: 30

analysis:
  model: "gemini-1.5-flash"
  enable_caching: true
  max_workers: 10

visualization:
  wordcloud_width: 1200
  wordcloud_height: 800
  custom_stopwords: ["video", "podcast", "episode"]
```

### `config/prompts.yaml`
AI analysis prompts:
- Defines the structure and instructions for Gemini API
- Specifies expected output format
- Customizable for different analysis needs

## Error Handling

### Common Error Scenarios

**Transcript Not Available**:
- Many channels disable transcripts
- The pipeline skips these videos gracefully
- Logged as INFO, not ERROR

**API Quota Exceeded**:
- YouTube API: 10,000 units/day
- Gemini API: 1,500 requests/day (free tier)
- Use incremental mode to minimize usage
- Rate limiter prevents exceeding quotas

**API Failures**:
- Automatic retry with exponential backoff
- Logs failures for debugging
- Continues processing other videos

### Logging

All modules use centralized logging:
```python
from src.utils.logger import get_logger
logger = get_logger(__name__)

logger.info("Processing started")
logger.warning("Transcript not available")
logger.error("API request failed")
```

Logs are written to:
- Console (INFO and above)
- `logs/vibes_tracker.log` (all levels)

## Testing Recommendations

### Unit Testing
- Test individual functions in isolation
- Mock API calls to avoid quota usage
- Focus on data processing logic

### Integration Testing
- Test with small sample dataset
- Verify end-to-end pipeline flow
- Check output file formats

### Performance Testing
- Measure processing time for different dataset sizes
- Monitor API quota usage
- Validate caching effectiveness

## Common Development Tasks

### Adding a New Analysis Field

1. Update `config/prompts.yaml` to request the new field
2. Modify `analyze.py` to parse the new field from Gemini response
3. Update CSV column names in `analyze.py`
4. Add visualization for the new field if needed

### Adding a New Visualization

1. Create plotting function in appropriate `src/visualizations/` module
2. Import function in `visualize.py`
3. Call function in the visualization pipeline
4. Add configuration options to `config/pipeline_config.yaml` if needed

### Modifying Cluster Definitions

1. Edit `config/clusters.json`
2. Add or remove channel handles
3. Run full pipeline to regenerate data for new clusters

### Changing AI Model

1. Update `config/pipeline_config.yaml`:
   ```yaml
   analysis:
     model: "gemini-1.5-pro"  # or other available model
   ```
2. Clear analysis cache: `rm -rf data/cache/analysis/`
3. Re-run analysis: `python src/main.py analyze --full-refresh`

## Best Practices

1. **Always use incremental mode** for daily updates
2. **Enable caching** to minimize API usage
3. **Monitor API quotas** before large historical collections
4. **Test prompts** with small samples before full runs
5. **Back up data** before major pipeline changes
6. **Use logging** for debugging and monitoring
7. **Document configuration** changes in comments
8. **Spread historical collections** across multiple days for quota management

## Additional Resources

- See `../Claude.md` for general project guidelines
- See `../README.md` for user-facing documentation
- See `../docs/TECHNICAL_GUIDE.md` for architecture details
- See `../docs/GETTING_STARTED.md` for setup instructions
