"""Metadata management for incremental processing."""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any


class MetadataManager:
    """Manages pipeline execution metadata for incremental processing."""

    def __init__(self, metadata_path: str = "data/metadata.json", logger: Optional[logging.Logger] = None):
        """
        Initialize metadata manager.

        Args:
            metadata_path: Path to metadata JSON file
            logger: Optional logger instance
        """
        self.metadata_path = Path(metadata_path)
        self.logger = logger or logging.getLogger(__name__)
        self.metadata = self._load()

    def _load(self) -> Dict[str, Any]:
        """Load metadata from file."""
        if self.metadata_path.exists():
            try:
                with open(self.metadata_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Error loading metadata: {e}. Starting fresh.")
                return self._default_metadata()
        return self._default_metadata()

    def _default_metadata(self) -> Dict[str, Any]:
        """Return default metadata structure."""
        return {
            "last_ingest_timestamp": None,
            "last_analysis_timestamp": None,
            "total_videos_ingested": 0,
            "total_videos_analyzed": 0,
            "pipeline_runs": [],
            "created_at": datetime.now(timezone.utc).isoformat()
        }

    def save(self):
        """Save metadata to file."""
        try:
            self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.metadata_path, 'w') as f:
                json.dump(self.metadata, f, indent=2)
            self.logger.debug(f"Saved metadata to {self.metadata_path}")
        except Exception as e:
            self.logger.error(f"Error saving metadata: {e}")

    def get_last_ingest_timestamp(self) -> Optional[str]:
        """Get timestamp of last ingestion run."""
        return self.metadata.get("last_ingest_timestamp")

    def get_last_analysis_timestamp(self) -> Optional[str]:
        """Get timestamp of last analysis run."""
        return self.metadata.get("last_analysis_timestamp")

    def update_ingest(self, num_videos: int):
        """
        Update metadata after ingestion.

        Args:
            num_videos: Number of videos ingested
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        self.metadata["last_ingest_timestamp"] = timestamp
        self.metadata["total_videos_ingested"] += int(num_videos)

        self.metadata["pipeline_runs"].append({
            "type": "ingest",
            "timestamp": timestamp,
            "videos": int(num_videos)
        })

        self.save()
        self.logger.info(f"Updated ingest metadata: {num_videos} videos at {timestamp}")

    def update_analysis(self, num_videos: int, num_analyzed: int):
        """
        Update metadata after analysis.

        Args:
            num_videos: Total number of videos processed
            num_analyzed: Number successfully analyzed
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        self.metadata["last_analysis_timestamp"] = timestamp
        self.metadata["total_videos_analyzed"] += int(num_analyzed)

        self.metadata["pipeline_runs"].append({
            "type": "analysis",
            "timestamp": timestamp,
            "total_videos": int(num_videos),
            "analyzed": int(num_analyzed),
            "skipped": int(num_videos - num_analyzed)
        })

        self.save()
        self.logger.info(f"Updated analysis metadata: {num_analyzed}/{num_videos} analyzed at {timestamp}")

    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        return {
            "total_videos_ingested": self.metadata.get("total_videos_ingested", 0),
            "total_videos_analyzed": self.metadata.get("total_videos_analyzed", 0),
            "total_runs": len(self.metadata.get("pipeline_runs", [])),
            "last_ingest": self.metadata.get("last_ingest_timestamp"),
            "last_analysis": self.metadata.get("last_analysis_timestamp"),
            "created_at": self.metadata.get("created_at")
        }

    def should_run_incremental(self, mode: str = "ingest") -> bool:
        """
        Check if incremental mode should be used.

        Args:
            mode: 'ingest' or 'analysis'

        Returns:
            True if there's a previous run to build on
        """
        if mode == "ingest":
            return self.metadata.get("last_ingest_timestamp") is not None
        elif mode == "analysis":
            return self.metadata.get("last_analysis_timestamp") is not None
        return False
