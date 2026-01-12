# Claude.md - Working with Vibes Tracker

This document provides guidance for Claude Code when working with the YouTube Vibes Tracker project.

## Project Overview

YouTube Vibes Tracker is a Python-based tool that monitors and analyzes content patterns across YouTube channels over time. It helps track what different groups of YouTube channels are discussing, analyzing themes, sentiment, and narrative framing.

## Key Capabilities

- **Data Collection**: Fetches video metadata from YouTube channels using the YouTube Data API v3
- **AI Analysis**: Uses Google's Gemini API to extract themes, sentiment, and framing from video transcripts
- **Temporal Tracking**: Monitors how topics evolve over time
- **Cross-Cluster Comparison**: Identifies consensus topics vs echo chambers across different channel groups
- **Automated Reporting**: Generates daily word clouds and view statistics
- **Historical Analysis**: Can collect and analyze years of historical data

## Project Structure

```
vibes-tracker/
├── config/              # Configuration files
│   ├── clusters.json    # Channel definitions by cluster
│   ├── pipeline_config.yaml  # Pipeline settings
│   └── prompts.yaml     # AI prompt templates
├── src/                 # Source code (see src/Claude.md for details)
├── scripts/             # Utility scripts
├── data/                # Generated data (gitignored)
├── figures/             # Generated visualizations (gitignored)
├── logs/                # Log files (gitignored)
└── docs/                # Documentation
```

## Important Guidelines

### Environment Setup

1. **Python Version**: Python 3.8+
2. **Virtual Environment**: Always use `.venv`
3. **Dependencies**: Install via `pip install -r requirements.txt`
4. **API Keys**: Require both YouTube Data API v3 and Gemini API keys in `.env` file

### API Quota Awareness

- **YouTube API**: 10,000 units/day limit (resets at midnight PT)
  - First fetch of a channel: ~100 units
  - Subsequent fetches: ~2 units per channel
- **Gemini API**: 1,500 requests/day on free tier
  - Use caching to avoid re-analyzing videos
  - Use incremental mode for daily updates

### Code Style

- Follow PEP 8 conventions
- Use type hints where appropriate
- Add docstrings for modules, classes, and functions
- Keep functions focused and modular
- Use the existing logging infrastructure (`src/utils/logger.py`)

### Testing Changes

When making code changes:
1. Test the affected module individually if possible
2. For pipeline changes, run: `python src/main.py pipeline --incremental`
3. Check generated outputs in `figures/` and `data/`
4. Review logs in `logs/` for any errors or warnings

### Common Tasks

**Adding a new visualization:**
- Add plotting function to appropriate module in `src/visualizations/`
- Import and call from `src/visualize.py`
- Follow existing color schemes and style conventions

**Modifying analysis prompts:**
- Edit `config/prompts.yaml`
- Test with a small sample before full run
- Document any new fields extracted

**Adding configuration options:**
- Update `config/pipeline_config.yaml`
- Modify `src/utils/config_loader.py` to load the new settings
- Update documentation

### Performance Considerations

- **Incremental mode**: Use for daily updates (100x faster than full refresh)
- **Parallel processing**: Default 10 workers for analysis, adjustable via `--workers`
- **Caching**: Enabled by default for both transcripts and analysis
- **Historical collection**: Spread large historical collections across multiple days to manage API quotas

### Documentation

Before making significant changes, review:
- `README.md` - General usage and features
- `docs/TECHNICAL_GUIDE.md` - Architecture and advanced usage
- `docs/GETTING_STARTED.md` - Setup instructions
- `src/Claude.md` - Detailed module information

## Need More Details?

For detailed information about the source code modules and implementation specifics, see `src/Claude.md`.
