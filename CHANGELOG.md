# Changelog

All notable changes to the YouTube Vibes Tracker.

## [2.0.0] - 2025-12-28

Major overhaul with 3 phases of improvements.

### Added

**Phase 1: Foundation**
- Configuration management via `config/pipeline_config.yaml`
- Structured logging with rotating file handlers
- Transcript and analysis caching (10-50x speedup on re-runs)
- Timestamps on all data collection for temporal tracking
- Quota tracking for API usage monitoring

**Phase 2: Core Features**
- Temporal trend tracking and historical snapshots
- Cross-cluster narrative comparison
- Enhanced AI analysis (6 fields instead of 3)
  - Theme categories (Political, Social, Economic, etc.)
  - Framing detection (favorable/critical/neutral/alarmist)
  - Named entity extraction
- 25+ visualizations:
  - Word clouds for titles and themes
  - Sentiment distribution charts
  - Temporal trend plots
  - Cross-cluster heatmaps
- Multi-year data collection capability
  - Can collect 7+ years of monthly data in one day
  - Efficient quota usage (120 units per time period)

**Phase 3: Performance & Efficiency**
- Incremental processing (only process new videos on subsequent runs)
  - 100x faster on re-runs
  - Automatic detection of previous runs
- Parallel processing with ThreadPoolExecutor
  - 3-5x faster analysis
  - Configurable worker count
  - Real-time progress bars
- Unified CLI interface (`src/main.py`)
  - 7 subcommands: ingest, analyze, visualize, temporal, compare, collect-historical, pipeline
  - Argument parsing for all options
  - Help text and examples

### Changed

- Replaced all print statements with structured logging
- Moved hardcoded values to configuration files
- Enhanced Gemini prompts for better analysis quality
- Refactored visualization code into separate modules
- Updated all scripts to use new configuration system

### Fixed

- JSON serialization error in MetadataManager (int64 type handling)
- Improved error handling for missing transcripts
- Better API quota management

### Performance

- **10-50x faster** with caching (repeated runs)
- **3-5x faster** with parallel processing
- **100x faster** with incremental mode (daily updates)

## [1.0.0] - Initial Release

### Initial Features
- Basic data ingestion from YouTube channels
- AI-powered analysis with Gemini
- Simple word cloud visualizations
- Sequential processing
- Manual configuration
