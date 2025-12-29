# API Costs Explained - What Costs Money vs What's Free

## 🔑 Two Completely Different Systems

### 1️⃣ YouTube Data API (Costs Quota)
**Used by**: Automated daily collection script
**What it does**: Gets video metadata (titles, dates, channel info)
**Cost**: 198 units per monthly period
**Quota limit**: 10,000 units/day
**What you get**: Just basic info about videos

```python
# This COSTS quota
from googleapiclient.discovery import build
youtube = build('youtube', 'v3', developerKey=API_KEY)
result = youtube.playlistItems().list(...)  # Costs 1 unit per call
```

**Returns**:
```json
{
  "video_id": "qU6h3ki9-TY",
  "title": "Trump's body is a TEMPLE",
  "publish_date": "2025-12-29T18:01:04Z",
  "channel_name": "@PodSaveAmerica"
}
```

---

### 2️⃣ YouTube Transcript API (FREE)
**Used by**: Analysis script (you run manually)
**What it does**: Scrapes existing transcripts from YouTube's website
**Cost**: $0 - FREE - NO QUOTA
**Quota limit**: None (unlimited)
**What you get**: Full text of everything said in the video

```python
# This is FREE (web scraper, not an API with quota)
from youtube_transcript_api import YouTubeTranscriptApi
api = YouTubeTranscriptApi()
transcript = api.fetch(video_id)  # FREE - no quota used!
```

**Returns**:
```python
[
  {"text": "Oh, hey Satan.", "start": 0.08, "duration": 3.359},
  {"text": "You about to go into labor?", "start": 3.439, "duration": 2.0},
  {"text": "Okay, how about you go do everything...", "start": 5.439, "duration": 3.2}
]
```

---

## 💰 Cost Breakdown

### Historical Collection (Running Now)
```
Daily collection of 10 monthly periods:
├─ YouTube Data API calls: ~2,000 units
├─ Cost in money: $0 (free tier)
├─ Quota used: 2,000/10,000 daily limit
└─ Data collected: Just metadata (~500 KB per month)
```

### Analysis Phase (You Run Later)
```
Analyzing 2,703 videos:
├─ YouTube Transcript API calls: 2,703 requests
├─ Cost in money: $0 (FREE - no quota system)
├─ Quota used: 0 (doesn't use Data API quota)
├─ Ollama AI analysis: FREE (runs on your computer)
└─ Data collected: Full transcripts + analysis (~500-800 MB total)
```

---

## 🎯 Why YouTube Has Free Transcripts

YouTube provides transcripts for free because:

1. **They're already generated**: YouTube auto-transcribes most videos using their own AI
2. **Creators upload them**: Many creators provide their own subtitle files
3. **They're publicly visible**: Anyone can view transcripts on youtube.com
4. **It's just text scraping**: We're downloading existing text, not generating anything

### You Can See This Yourself!

1. Go to: https://www.youtube.com/watch?v=qU6h3ki9-TY
2. Click the **...** button under the video
3. Click **"Show transcript"**
4. See the text? That's what we fetch (for free!)

---

## 📊 The Two APIs Compared

| Feature | YouTube Data API | YouTube Transcript API |
|---------|-----------------|----------------------|
| **Purpose** | Get video metadata | Get video transcripts |
| **Cost** | 198 units/month | FREE |
| **Quota limit** | 10,000/day | Unlimited |
| **What you get** | Title, date, channel | Full transcript text |
| **Used when** | Daily collection | Analysis phase |
| **Library** | `googleapiclient` | `youtube-transcript-api` |
| **Requires API key** | Yes | No |

---

## 🤔 Common Misconceptions

### ❌ "Getting transcripts will cost a ton of API quota"
**Reality**: Transcripts use ZERO quota. They're fetched via web scraping, not the Data API.

### ❌ "We need to download and transcribe audio"
**Reality**: YouTube already has transcripts. We just download the existing text.

### ❌ "We need to use speech-to-text AI"
**Reality**: YouTube already did this. Their transcripts are public and free to access.

### ❌ "Analysis will cost API quota"
**Reality**: Analysis uses Ollama (local AI) and transcript scraping (free). Zero API quota.

---

## 💾 What's Actually Being Stored Right Now

Your automated script is storing this **tiny** data:

```csv
video_id,title,publish_date,channel_name,url,cluster,run_timestamp
qU6h3ki9-TY,Trump's body is a TEMPLE,2025-12-29T18:01:04Z,@PodSaveAmerica,https://...,libs,2025-12-29T20:21:19Z
```

**Size**: ~527 KB for 2,703 videos
**Per video**: ~200 bytes
**For 72 months**: ~2-3 MB total

This is just an **index** or **catalog** of videos. Like a library card catalog - it tells you what exists, but not the content itself.

---

## 🚀 What Happens During Analysis

```
For each video in the catalog:
├─ 1. Fetch transcript from YouTube (FREE)
│     └─ Uses: youtube-transcript-api (web scraper)
│     └─ Quota used: 0
│     └─ Time: ~1-2 seconds
│
├─ 2. Analyze with Ollama (FREE)
│     └─ Uses: Local AI model (llama3.1)
│     └─ Quota used: 0
│     └─ Time: ~5-15 seconds
│
└─ 3. Cache everything (FREE)
      └─ Saves transcript + analysis to disk
      └─ Never needs to re-fetch
```

**Total API quota used during analysis**: 0 units

---

## ✅ Summary

| What | API Quota Used | Money Cost | Time |
|------|---------------|-----------|------|
| **Daily collection** (metadata) | 198/month | $0 | Auto |
| **Fetching transcripts** | 0 | $0 | 4-8 hrs |
| **AI analysis** (Ollama) | 0 | $0 | 4-8 hrs |
| **Total for 5 years** | ~14,000 | $0 | ~7 days |

The only thing that costs API quota is the initial metadata collection (which is running automatically now). Everything else - transcripts, analysis, visualization - is completely free!
