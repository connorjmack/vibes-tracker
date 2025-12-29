# Complete Data Pipeline Overview

## 📊 What Data You're Collecting

### Current Phase: Historical Collection (Running Daily)

**Metadata Only** - Saved to `data/historical/YYYY-MM-DD/cluster_data.csv`:
```csv
video_id,title,publish_date,channel_name,url,cluster,run_timestamp
qU6h3ki9-TY,Trump's body is a TEMPLE,2025-12-29T18:01:04Z,@PodSaveAmerica,https://...,libs,2025-12-29T20:21:19Z
```

**Fields**:
- `video_id`: YouTube video ID
- `title`: Video title
- `publish_date`: When video was published
- `channel_name`: YouTube channel handle
- `url`: Full YouTube URL
- `cluster`: Political cluster (libs/right/mainstream/my-env/manosphere)
- `run_timestamp`: When data was collected

**API Cost**: 198 units per monthly period (YouTube Data API)

---

## 🎯 Future Phase: Analysis (You Run Later)

### What Happens When You Run Analysis

```bash
.venv/bin/python src/analyze.py --full-refresh
```

### 1. **Fetch Transcripts** (FREE - no API quota)
- Uses `YouTubeTranscriptApi` (different from Data API)
- Fetches every word spoken in the video
- Saves to: `data/cache/transcripts/{video_id}.json`

**Example cached transcript**:
```json
{
  "video_id": "qU6h3ki9-TY",
  "transcript": "Oh, hey Satan. You about to go into labor? Okay, how about you go do everything and I'll do nothing...",
  "timestamp": "2025-12-29T22:15:30Z"
}
```

### 2. **AI Analysis with Ollama** (FREE - runs locally)
- Analyzes each transcript for:
  - **Sentiment**: Positive, Neutral, Negative, Mixed
  - **Themes**: Main topics discussed (e.g., "Immigration Policy", "Climate Change")
  - **Theme Categories**: Political Issues, Social Issues, Economic Topics, etc.
  - **Framing**: favorable, critical, neutral, alarmist
  - **Named Entities**: People, organizations, events mentioned
  - **Summary**: One-sentence summary of video

**Saves to**: `data/cache/analysis/{video_id}.json`

**Example analysis**:
```json
{
  "core_themes": ["Donald Trump", "Politics", "Health"],
  "theme_categories": ["Political Issues"],
  "overall_sentiment": "Negative",
  "framing": "critical",
  "named_entities": ["Donald Trump", "Satan"],
  "one_sentence_summary": "The video mocks Donald Trump's personal health and hygiene habits."
}
```

### 3. **Final Output**
Merges everything into: `data/analyzed_data.csv`

```csv
video_id,title,publish_date,channel_name,cluster,summary,themes,sentiment,framing,theme_categories,named_entities
qU6h3ki9-TY,Trump's body is a TEMPLE,2025-12-29T18:01:04Z,@PodSaveAmerica,libs,"The video mocks...",Donald Trump | Politics | Health,Negative,critical,Political Issues,Donald Trump | Satan
```

---

## 💾 Full Data Access After Analysis

### YES - You Can Extract Full Transcripts!

Once analysis is complete, you have **full access** to:

#### Option 1: Export All Transcripts to JSON
```bash
.venv/bin/python scripts/export_transcripts.py \
  --format json \
  --include-metadata \
  --output all_transcripts.json
```

**Output**: Single JSON file with all transcripts + metadata + analysis

#### Option 2: Export by Cluster to CSV
```bash
.venv/bin/python scripts/export_transcripts.py \
  --cluster libs \
  --format csv \
  --include-metadata \
  --output libs_transcripts.csv
```

**Output**: Spreadsheet with libs cluster transcripts

#### Option 3: Export to Individual Text Files
```bash
.venv/bin/python scripts/export_transcripts.py \
  --format txt \
  --include-metadata \
  --output transcripts.txt
```

**Output**: Folder with one `.txt` file per video

#### Option 4: Direct Access to Cache
Transcripts are stored as JSON files at:
```
data/cache/transcripts/
├── qU6h3ki9-TY.json
├── ZNkDgKpI-tk.json
├── 8X0eR9yKdOk.json
└── ...
```

Read them directly:
```python
import json

with open('data/cache/transcripts/qU6h3ki9-TY.json', 'r') as f:
    data = json.load(f)
    transcript = data['transcript']
    print(transcript)
```

---

## 📈 Complete Data Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│ PHASE 1: Historical Collection (Running Daily)             │
│ ────────────────────────────────────────────────────────── │
│ • Collects video metadata from YouTube Data API            │
│ • Saves to: data/historical/YYYY-MM-DD/cluster_data.csv    │
│ • Cost: 198 API units per monthly period                   │
│ • Time: ~7 days to complete 5 years                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 2: Analysis (You Run Manually)                       │
│ ────────────────────────────────────────────────────────── │
│ • Fetches transcripts (FREE - YouTubeTranscriptApi)        │
│ • Runs AI analysis (FREE - Ollama local)                   │
│ • Caches everything for fast re-access                     │
│ • Time: 4-8 hours for 2,703 videos                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ OUTPUT: Full Dataset                                        │
│ ────────────────────────────────────────────────────────── │
│ ✅ data/analyzed_data.csv - All data in one spreadsheet    │
│ ✅ data/cache/transcripts/ - Full transcripts (JSON)       │
│ ✅ data/cache/analysis/ - AI analysis (JSON)               │
│ ✅ Export scripts ready for any format you need            │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 Summary

### What You're Collecting NOW:
- ❌ NOT transcripts yet
- ✅ Video metadata (IDs, titles, dates, channels, URLs)

### What You'll Get After Running Analysis:
- ✅ Full transcripts (every word spoken)
- ✅ Sentiment analysis
- ✅ Theme extraction
- ✅ Named entities
- ✅ Summaries
- ✅ All exportable to JSON/CSV/TXT

### Timeline:
1. **Days 1-7**: Automatic historical collection (metadata only)
2. **Day 8**: Run analysis script (fetches transcripts + AI analysis)
3. **Day 8+**: Full dataset ready, export transcripts as needed

### Costs:
- **Historical collection**: Uses YouTube API quota (limited to 10k/day)
- **Transcript fetching**: FREE (no quota)
- **AI analysis**: FREE (Ollama runs locally)
- **Storage**: ~500-800 MB for all transcripts + analysis

---

## 🔑 Key Takeaways

1. **You WILL have full transcripts** - they're fetched during analysis
2. **Everything is cached** - won't need to re-fetch
3. **Analysis is free** - runs locally with Ollama
4. **Flexible export** - JSON, CSV, or individual text files
5. **Nothing is lost** - all data is permanently saved

The automatic collection is just building the **catalog** of videos.
The analysis phase will get you the **full content** (transcripts + AI insights).
