## YouTube Vibes Tracker

## Cluster Analysis & Narrative Monitoring with Gemini AI

This project is an advanced AI agent designed to monitor, categorize, and analyze narrative trends across groups of ideologically similar YouTube channels. Instead of analyzing single creators, it detects the shared "zeitgeist" or "hive mind" of defined content clusters (e.g., `libs`, `manosphere`, `my-env`).

---

### Key Features and Professional Practices

| Feature | Description | Professional Skill Demonstrated |
| :--- | :--- | :--- |
| **Cluster Ingestion** | Fetches the latest 30 video titles/metadata for pre-defined channel clusters from `config/clusters.json`. | Config-driven development, ETL Pipeline |
| **Quota Optimization** | Uses a local JSON cache (`data/channel_ids.json`) to store permanent Channel IDs, bypassing expensive `search().list` API calls on subsequent runs to stay within the 10,000 unit daily limit. | Performance optimization, Cost-Aware Development |
| **AI Tagging (RAG)** | Fetches video transcripts and uses the **Gemini 1.5 Flash API** to assign structured tags: **Core Themes** and **Overall Sentiment** to every video. | Retrieval-Augmented Generation (RAG), LLM Tool Use |
| **Time Series Ready** | The final analyzed data is saved with `publish_date`, making it ready for trend visualization (Time Series Analysis). | Data preparation for statistical modeling |
| **Styled Visualization** | Generates custom-shaped, color-mapped word clouds to quickly visualize the semantic space of each cluster. | Data Visualization (Matplotlib, WordCloud) |

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