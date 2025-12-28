# Getting Started

This guide walks you through your first run of the YouTube Vibes Tracker.

## Prerequisites

- Python 3.8 or higher
- YouTube Data API key
- Gemini API key

## Setup (5 minutes)

### 1. Install

```bash
git clone https://github.com/YOUR_USERNAME/vibes-tracker.git
cd vibes-tracker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Get API Keys

**YouTube API:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable "YouTube Data API v3"
4. Create credentials → API key
5. Copy the key

**Gemini API:**
1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Click "Get API key"
3. Copy the key

### 3. Configure

Create `.env` file in the project root:

```
YOUTUBE_API_KEY=your_youtube_key_here
GEMINI_API_KEY=your_gemini_key_here
```

Edit `config/clusters.json` to add your channels:

```json
{
  "news": ["@cnn", "@foxnews", "@bbcnews"],
  "tech": ["@mkbhd", "@verge", "@linustechtips"]
}
```

Use channel handles (the @username format).

## First Run (10-15 minutes)

Run the complete pipeline:

```bash
python src/main.py pipeline
```

This will:
1. Fetch recent videos from your channels (~2 min)
2. Analyze transcripts with Gemini (~10 min for ~1000 videos)
3. Generate visualizations (~1 min)

## Check Your Results

**Visualizations:**
- Open `figures/` folder
- Look for word clouds, sentiment charts, trend plots

**Data:**
- `data/analyzed_data.csv` - Full analysis results
- Each row is a video with themes, sentiment, framing, etc.

**Logs:**
- `logs/` - Detailed logs of what happened
- Check here if something goes wrong

## Daily Updates (30 seconds)

After the first run, use incremental mode:

```bash
python src/main.py pipeline --incremental
```

This only processes new videos since your last run. Much faster.

## Common Commands

```bash
# Just fetch new videos
python src/main.py ingest --incremental

# Just run analysis
python src/main.py analyze

# Just generate plots
python src/main.py visualize

# See what themes are trending
python src/main.py temporal --days-back 7

# Compare your clusters
python src/main.py compare
```

## What the Data Means

For each video, you get:

- **Themes** - Main topics discussed (e.g., "Climate Change", "Immigration")
- **Sentiment** - Overall tone (Positive, Neutral, Negative, Mixed)
- **Framing** - How the topic is presented:
  - favorable - supportive, promotional
  - critical - opposing, critiquing
  - neutral - balanced, informative
  - alarmist - crisis framing, urgent
- **Named Entities** - People, organizations, events mentioned
- **Summary** - One sentence takeaway

## Customization

Edit `config/pipeline_config.yaml` to change:

```yaml
ingest:
  videos_per_channel: 30  # How many videos to fetch per channel

analysis:
  model: "gemini-1.5-flash"  # AI model to use
  enable_caching: true       # Cache results (recommended)

visualization:
  custom_stopwords: ["video", "podcast"]  # Words to ignore in word clouds
```

## Troubleshooting

**"GEMINI_API_KEY not found"**
- Check your `.env` file is in the project root
- Make sure it's named `.env` exactly (not `.env.txt`)

**"No data found"**
- Make sure your channel handles are correct (use @username format)
- Some channels may not have transcripts enabled
- Check `logs/` for details

**"API quota exceeded"**
- YouTube API has a 10,000 units/day limit
- Use incremental mode to reduce usage
- Limit goes away the next day

**Analysis takes forever**
- Use `--workers 20` to analyze faster
- First run is always slower (building cache)
- Incremental runs are much faster

**No transcripts available**
- This is normal - many channels disable transcripts
- The tool will skip those videos
- You'll see "Transcript unavailable" in logs

## Next Steps

- [Multi-Year Analysis](MULTI_YEAR_ANALYSIS_GUIDE.md) - Collect historical data
- [README](../README.md) - Full documentation
- [Implementation Summary](../results/IMPLEMENTATION_SUMMARY.md) - Technical details

## Need Help?

Check the logs in `logs/` - they're pretty detailed and will usually tell you what went wrong.
