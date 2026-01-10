---
description: Perform a health check on the YouTube Vibes Tracker project.
---

Please perform a health check on the project environment:

1.  **Core Files**: Verify that `src/main.py` and `config/pipeline_config.yaml` exist.
2.  **Ollama**: Check if the Ollama server is running and accessible (try `curl -s http://localhost:11434/api/tags` or check running processes).
3.  **Data**: Check if `data/cluster_data.csv` exists and report its file size / line count.
4.  **Python**: Check the active python version `python --version`.

Report the status of each component concisely.
