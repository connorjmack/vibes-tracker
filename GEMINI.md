# YouTube Vibes Tracker

**Context for Gemini Agents**

## Project Overview
**YouTube Vibes Tracker** is a Python-based data pipeline designed to monitor, analyze, and visualize narrative patterns across clusters of YouTube channels (e.g., political "libs" vs "right", "tech", etc.). It fetches video metadata, downloads transcripts, extracts themes and sentiment using an LLM, and generates comparative visualizations.

**Crucial Note on AI Backend:**
While the `README.md` and `requirements.txt` mention Google Gemini, the **actual implementation (`src/analyze.py`) currently relies exclusively on a local Ollama instance** (defaulting to `llama3.1:latest`). Future plans appear to include Gemini integration.

## Technology Stack
*   **Language:** Python 3.x
*   **Data Sources:**
    *   **YouTube Data API v3:** For video metadata (requires API key).
    *   **`youtube-transcript-api`:** For fetching video transcripts (no API key required).
*   **AI/Analysis:**
    *   **Ollama:** Local LLM inference (requires running `ollama serve`).
    *   *Note:* `google-genai` libraries are present in requirements but unused in the current `src/analyze.py`.
*   **Data Processing:** `pandas`
*   **Visualization:** `matplotlib`, `seaborn`, `wordcloud`
*   **Configuration:** `pyyaml`, `pydantic`

## Architecture & Data Flow

1.  **Ingestion (`src/ingest.py`)**
    *   Reads channel lists from `config/clusters.json`.
    *   Fetches recent video metadata via YouTube Data API.
    *   Saves raw metadata to `data/cluster_data.csv`.

2.  **Analysis (`src/analyze.py`)**
    *   Reads metadata from `data/cluster_data.csv`.
    *   Fetches full transcripts using `youtube-transcript-api`.
    *   **Requires Ollama:** Sends transcripts to a local Ollama server (e.g., `http://localhost:11434`) for JSON-structured analysis (Themes, Sentiment, Framing, Entities).
    *   Caches results in `data/cache/` to avoid redundant processing.
    *   Saves enriched data to `data/analyzed_data.csv`.

3.  **Visualization (`src/visualize.py`)**
    *   Reads enriched data.
    *   Generates word clouds, trend charts, and cluster comparisons.
    *   Outputs images to `figures/`.

## Key Files & Directories
*   `src/main.py`: **CLI Entry Point.** Handles all commands (`pipeline`, `ingest`, `analyze`, `visualize`).
*   `config/pipeline_config.yaml`: Main configuration (model selection, paths, limits).
*   `config/clusters.json`: Defines the groups of YouTube channels to track.
*   `src/analyze.py`: Core analysis logic. **Inspect this file for prompt engineering and LLM interaction details.**
*   `data/`: Stores all generated data. `data/cache/` is critical for performance.

## Common Workflows & Commands
All commands are executed via `src/main.py`.

*   **Run Full Pipeline:**
    ```bash
    python src/main.py pipeline --incremental
    ```
*   **Run Individual Stages:**
    ```bash
    python src/main.py ingest
    python src/main.py analyze --workers 10  # Requires 'ollama serve' running
    python src/main.py visualize
    ```
*   **Historical Collection:**
    ```bash
    python scripts/collect_historical_data.py --start-year 2023 --end-year 2024
    ```

## Development Conventions
*   **Configuration:** All paths and tunable parameters should be in `config/pipeline_config.yaml`, not hardcoded.
*   **Error Handling:** The pipeline is designed to be resilient (e.g., skipping videos without transcripts) and uses extensive logging (`logs/`).
*   **Caching:** The system heavily relies on file-based caching (`src/utils/cache_manager.py`) to minimize API costs and processing time. Always check/respect the cache logic when modifying data retrieval code.
