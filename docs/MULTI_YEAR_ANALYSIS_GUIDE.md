# Multi-Year Analysis Guide

## Overview

The YouTube Vibes Tracker can collect and analyze **years** of historical data while staying within YouTube API quota constraints.

---

## API Quota Efficiency

**Current Implementation:**
- ✅ **~120 units per time period** (60 channels × 2 units each)
- ✅ **10,000 units daily quota** = **83 time periods per day**
- ✅ **Can collect 7 years of monthly data in a single day!**

**Example Calculations:**

| Frequency | Periods/Year | Total Periods (3 years) | API Units | Days Needed |
|-----------|--------------|-------------------------|-----------|-------------|
| Monthly   | 12           | 36                      | 4,320     | 1 day       |
| Quarterly | 4            | 12                      | 1,440     | 1 day       |
| Yearly    | 1            | 3                       | 360       | 1 day       |

**Multi-Year Collection:**
- 2022-2024 (3 years monthly): **36 periods × 120 units = 4,320 units** ✅ Single day
- 2020-2024 (5 years monthly): **60 periods × 120 units = 7,200 units** ✅ Single day
- 2015-2024 (10 years monthly): **120 periods × 120 units = 14,400 units** ❌ 2 days needed

---

## Collection Methods

### Method 1: Single Time Period

Collect data for one specific month:

```bash
source .venv/bin/activate

# Example: Collect January 2024
python scripts/collect_historical_data.py \
  --start-date 2024-01-01 \
  --end-date 2024-02-01
```

**Output:** `data/historical/2024-01-01/cluster_data.csv`

---

### Method 2: Multi-Year Collection (Automated)

Collect multiple years automatically:

```bash
# Collect 2022-2024, monthly snapshots
python scripts/collect_historical_data.py \
  --start-year 2022 \
  --end-year 2024 \
  --frequency monthly

# Collect 2020-2024, quarterly snapshots
python scripts/collect_historical_data.py \
  --start-year 2020 \
  --end-year 2024 \
  --frequency quarterly

# Collect 2015-2024, yearly snapshots
python scripts/collect_historical_data.py \
  --start-year 2015 \
  --end-year 2024 \
  --frequency yearly
```

**Output:** Multiple directories in `data/historical/YYYY-MM-DD/`

---

### Method 3: Incremental Build-Up (Ongoing Monitoring)

Run daily/weekly going forward:

```bash
# Add to cron job (runs daily at 2am)
0 2 * * * cd /path/to/vibes-tracker && source .venv/bin/activate && python src/ingest.py
```

This automatically builds multi-year dataset over time.

---

## Data Structure

Historical data is organized by date:

```
data/historical/
├── 2022-01-01/
│   └── cluster_data.csv
├── 2022-02-01/
│   └── cluster_data.csv
├── 2022-03-01/
│   └── cluster_data.csv
...
├── 2024-12-01/
│   └── cluster_data.csv
└── 2024-12-28/
    ├── cluster_data.csv
    └── analyzed_data.csv  (after running analyze.py)
```

---

## Analysis Workflow

### 1. Collect Historical Data

```bash
# Collect 3 years of monthly data
python scripts/collect_historical_data.py \
  --start-year 2022 \
  --end-year 2024 \
  --frequency monthly
```

**Result:** 36 CSV files with video metadata

---

### 2. Analyze Historical Data (Optional)

You can analyze specific historical periods:

```bash
# Analyze January 2024 data
cp data/historical/2024-01-01/cluster_data.csv data/cluster_data.csv
python src/analyze.py
mv data/analyzed_data.csv data/historical/2024-01-01/

# Repeat for other periods...
```

**Note:** This would use Gemini API quota. For multi-year analysis, you might want to:
- Analyze only key periods (e.g., quarterly)
- Use sampling (analyze subset of videos)
- Focus on title/metadata analysis (no transcript needed)

---

### 3. Run Temporal Analysis

Once you have multiple historical snapshots:

```bash
# Analyze trends over past 2 years
python src/temporal_analysis.py --days-back 730

# Or analyze specific date range
python src/temporal_analysis.py \
  --start-date 2022-01-01 \
  --end-date 2024-12-31
```

---

## Use Cases

### Research Example 1: Presidential Election Cycles

```bash
# Collect monthly data for 2020 and 2024 elections
python scripts/collect_historical_data.py --start-year 2020 --end-year 2020 --frequency monthly
python scripts/collect_historical_data.py --start-year 2024 --end-year 2024 --frequency monthly

# Compare narrative patterns:
# - Pre-election period (Jan-Oct)
# - Election month (Nov)
# - Post-election (Dec-Jan)
```

**Research Questions:**
- How do themes shift during election cycles?
- What narratives emerge pre/post election?
- How do different clusters respond to election events?

---

### Research Example 2: Event-Based Analysis

```bash
# COVID-19 pandemic evolution
python scripts/collect_historical_data.py --start-date 2020-01-01 --end-date 2020-12-31
python scripts/collect_historical_data.py --start-date 2021-01-01 --end-date 2021-12-31
python scripts/collect_historical_data.py --start-date 2022-01-01 --end-date 2022-12-31
```

**Research Questions:**
- How did COVID narratives evolve 2020-2022?
- When did themes shift from "lockdowns" to "vaccines" to "endemic"?
- How did cluster framing differ over time?

---

### Research Example 3: Long-Term Polarization Study

```bash
# Track polarization 2015-2024
python scripts/collect_historical_data.py \
  --start-year 2015 \
  --end-year 2024 \
  --frequency quarterly
```

**Research Questions:**
- How has cluster similarity changed over 10 years?
- Are echo chambers strengthening or weakening?
- What themes show increasing divergence?

---

## Quota Management

### Daily Quota: 10,000 units

**Example Daily Collection Plans:**

**Plan A: Deep Historical Dive**
- Collect 80 months of data in one day
- 80 periods × 120 units = 9,600 units
- Leaves 400 units for analysis/testing

**Plan B: Conservative Approach**
- Collect 50 periods per day
- 50 × 120 = 6,000 units used
- Leaves 4,000 units buffer

**Plan C: Spread Over Multiple Days**
- Day 1: Collect 2022 (12 months = 1,440 units)
- Day 2: Collect 2023 (12 months = 1,440 units)
- Day 3: Collect 2024 (12 months = 1,440 units)
- Total: 3 days for 3 years monthly data

---

## Performance Tips

### 1. Batch by Year

```bash
# More organized approach
python scripts/collect_historical_data.py --start-year 2022 --end-year 2022 --frequency monthly
python scripts/collect_historical_data.py --start-year 2023 --end-year 2023 --frequency monthly
python scripts/collect_historical_data.py --start-year 2024 --end-year 2024 --frequency monthly
```

### 2. Test First

```bash
# Test with single month before committing to years
python scripts/collect_historical_data.py --start-date 2024-01-01 --end-date 2024-02-01
```

### 3. Monitor Quota

The script logs quota usage:
```
API Usage Summary - YouTube: 4,320 units, Gemini: 0 calls
```

### 4. Resume if Interrupted

The script saves each period independently, so you can resume:
- Check which periods exist in `data/historical/`
- Skip those dates
- Continue from where you left off

---

## Limitations & Considerations

### YouTube API Limitations:

1. **Maximum Results per Request:** 50 videos
   - For channels with >50 videos/month, you get the most recent 50
   - Very active channels might have gaps

2. **Pagination:** Currently fetches up to 50 videos per channel per period
   - Can be increased by modifying `max_results` parameter
   - More pages = more API units (1 unit per page)

3. **Deleted/Private Videos:** Not accessible
   - Historical data may have gaps for removed content

### Gemini API Costs:

- **Transcript analysis** uses Gemini quota
- For multi-year analysis of thousands of videos:
  - Option 1: Analyze only metadata (titles, publish dates) - NO Gemini cost
  - Option 2: Sample videos (e.g., 10 per cluster per month)
  - Option 3: Analyze in batches over time
  - Option 4: Use caching heavily (analyze once, cache forever)

---

## Recommended Workflow

**For Academic Research (2-3 year study):**

```bash
# Step 1: Collect all data (single day)
python scripts/collect_historical_data.py \
  --start-year 2022 \
  --end-year 2024 \
  --frequency monthly

# Step 2: Analyze strategically
# - Analyze every 3rd month (12 periods instead of 36)
# - Or analyze only key events (elections, major news)

# Step 3: Generate temporal visualizations
python src/temporal_analysis.py --days-back 1095  # 3 years

# Step 4: Cross-cluster comparison across time
python src/cross_cluster_analysis.py
```

**For Ongoing Monitoring:**

```bash
# Set up daily cron job
0 2 * * * cd /path/to/vibes-tracker && source .venv/bin/activate && python src/ingest.py && python src/analyze.py

# This builds historical dataset automatically
# After 1 year: 365 snapshots
# After 2 years: 730 snapshots
```

---

## Expected Results

### 3-Year Monthly Collection (36 periods):

**Data Collected:**
- ~1,000-2,000 videos per period
- 36,000-72,000 total videos
- Organized in 36 dated directories

**API Usage:**
- 4,320 YouTube units (within single day quota)
- No Gemini units (just metadata collection)

**Analysis Capabilities:**
- Track theme evolution over 36 months
- Identify long-term trends
- Compare election cycles (2022 midterms, 2024 election)
- Study event impacts (Ukraine invasion, COVID phases, etc.)
- Measure polarization changes

---

## Next Steps

1. **Collect Historical Data**
   ```bash
   python scripts/collect_historical_data.py --start-year 2022 --end-year 2024 --frequency monthly
   ```

2. **Verify Data**
   ```bash
   ls -l data/historical/
   ```

3. **Run Temporal Analysis**
   ```bash
   python src/temporal_analysis.py
   ```

4. **Generate Visualizations**
   ```bash
   python src/visualize.py
   ```

---

## Summary

✅ **YES, multi-year analysis is possible without breaking API constraints**

- **Collect 7+ years** of monthly data in a single day
- **120 API units per period** (very efficient)
- **10,000 daily quota** = 83 periods/day capacity
- **Automatic organization** by date
- **Full temporal analysis** once collected

The bottleneck is NOT the YouTube API (plenty of quota), but rather:
- **Transcript availability** (many channels disable)
- **Gemini analysis costs** (for thousands of videos)
- **Storage** (CSVs add up over years)

For most research use cases, collecting metadata for multi-year periods is fast, cheap, and within quota!
