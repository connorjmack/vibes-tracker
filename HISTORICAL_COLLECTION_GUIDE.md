# Gradual Historical Data Collection Guide

## Overview

Your YouTube API quota is limited to **10,000 units per day**. To collect 5 years of historical data without hitting limits, you'll need to run the collection incrementally over several days.

## Current Status

- **Completed**: January 2020 (568 videos)
- **Remaining**: 71 months (Feb 2020 - Dec 2025)
- **Estimated Time**: 3-5 days to complete all historical data

## Daily Collection Process

### 1. Run the incremental collector (do this once per day)

```bash
# Collect up to 10 monthly periods per day
.venv/bin/python scripts/incremental_historical_collection.py

# Or customize:
.venv/bin/python scripts/incremental_historical_collection.py \
    --start-year 2020 \
    --end-year 2025 \
    --max-periods 15
```

### 2. What happens automatically:

- ✅ Skips already-collected periods
- ✅ Tracks progress in `data/historical_collection_progress.json`
- ✅ Stops before hitting quota limit (at 8,000 units)
- ✅ Saves data to `data/historical/YYYY-MM-DD/cluster_data.csv`
- ✅ Resumes where it left off on next run

### 3. Check progress anytime:

```bash
cat data/historical_collection_progress.json
```

## Collection Strategy

### **Option A: Gradual (Recommended)**
Run the script once per day for 3-5 days until complete.

**Pros:**
- No quota issues
- Can analyze data incrementally as it arrives
- Low stress on API

**Schedule:**
- **Day 1**: Collect 10 months (2020-01 through 2020-10)
- **Day 2**: Collect 10 months (2020-11 through 2021-08)
- **Day 3**: Collect 10 months (2021-09 through 2022-06)
- **Day 4**: Collect remaining periods

### **Option B: Aggressive**
Run with `--max-periods 20` to collect 20 months per day.

```bash
.venv/bin/python scripts/incremental_historical_collection.py --max-periods 20
```

**Pros:**
- Finishes in 2-3 days

**Cons:**
- Might hit quota limit
- Less flexibility for other API usage

## Resuming After Completion

If you ever need to collect newer data (e.g., in January 2026):

```bash
# This will automatically detect new periods and collect them
.venv/bin/python scripts/incremental_historical_collection.py
```

## Resetting Progress

If something goes wrong and you want to start over:

```bash
.venv/bin/python scripts/incremental_historical_collection.py --reset
```

## After Collection Completes

Once all periods are collected, you can:

1. **Merge all historical data** into your main dataset
2. **Run Ollama analysis** on the complete dataset
3. **Generate comprehensive visualizations** showing 5-year trends

Commands coming in next steps!

## Troubleshooting

### "API quota exceeded" error
- **Solution**: Wait until tomorrow (quotas reset at midnight Pacific Time)
- The script saves progress, so just run it again tomorrow

### Missing channel IDs
- **Solution**: Run `src/ingest.py` first to build the channel ID cache

### Want to see what will be collected?
```bash
.venv/bin/python scripts/incremental_historical_collection.py --help
```
