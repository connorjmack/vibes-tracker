## YouTube Vibes Tracker

## Cluster Analysis & Narrative Monitoring with Gemini AI

A tool for creating custom information ecosystems and tracking their content over time – gets the "vibe" of a user-defined set of youtube channels.

---

### Project Architecture

The agent operates in three distinct, modular stages:

1.  **Ingestion:** Reads `clusters.json` $\rightarrow$ Fetches Metadata.
2.  **Analysis:** Reads Metadata $\rightarrow$ Fetches Transcripts $\rightarrow$ **Gemini AI Tags** $\rightarrow$ Saves Enriched Data.
3.  **Visualization:** Reads Enriched Data $\rightarrow$ Generates Plots/Word Clouds.


---

### Installation & Setup

1.  **Clone the Repository**
    ```bash
    git clone [https://github.com/YOUR_USERNAME/vibes-tracker.git](https://github.com/YOUR_USERNAME/vibes-tracker.git)
    cd vibes-tracker
    ```

2.  **Create and Activate Virtual Environment**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # macOS/Linux
    # .venv\Scripts\activate.bat # Windows
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **API Authentication**
    Create a file named `.env` in the project root and add your two API keys. (This file is ignored by `.gitignore` for security).

    ```
    YOUTUBE_API_KEY=AIzaSy...
    GEMINI_API_KEY=AIzaSy...
    ```

---

### Usage

Run the scripts sequentially from the **project root directory** (`vibes-tracker/`):

#### 1. Ingest Data (Metadata Fetching)
This creates `data/cluster_data.csv` and the `data/channel_ids.json` cache.

```bash
python src/ingest.py


![Topics across all clusters](figures/combined_titles_wordcloud_styled.png)
