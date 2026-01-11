"""Cache management for transcripts and analysis results."""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone


class CacheManager:
    """Manages caching for transcripts and analysis results."""

    def __init__(self, cache_dir: str = "data/cache", logger: Optional[logging.Logger] = None):
        """
        Initialize the cache manager.

        Args:
            cache_dir: Root directory for cache storage
            logger: Optional logger instance
        """
        self.cache_dir = Path(cache_dir)
        self.transcripts_dir = self.cache_dir / "transcripts"
        self.analysis_dir = self.cache_dir / "analysis"
        self.logger = logger or logging.getLogger(__name__)

        # Create cache directories
        self.transcripts_dir.mkdir(parents=True, exist_ok=True)
        self.analysis_dir.mkdir(parents=True, exist_ok=True)

        self.cache_hits = 0
        self.cache_misses = 0

    def get_transcript(self, video_id: str) -> Optional[str]:
        """
        Retrieve cached transcript for a video.

        Args:
            video_id: YouTube video ID

        Returns:
            Transcript text if cached, None otherwise
        """
        cache_file = self.transcripts_dir / f"{video_id}.txt"

        if cache_file.exists():
            self.cache_hits += 1
            self.logger.debug(f"Cache hit: transcript for {video_id}")
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                self.logger.error(f"Error reading cached transcript for {video_id}: {e}")
                return None
        else:
            self.cache_misses += 1
            self.logger.debug(f"Cache miss: transcript for {video_id}")
            return None

    def save_transcript(self, video_id: str, transcript: str) -> bool:
        """
        Save transcript to cache.

        Args:
            video_id: YouTube video ID
            transcript: Transcript text

        Returns:
            True if successful, False otherwise
        """
        cache_file = self.transcripts_dir / f"{video_id}.txt"

        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                f.write(transcript)
            self.logger.debug(f"Cached transcript for {video_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error caching transcript for {video_id}: {e}")
            return False

    def get_analysis(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached analysis for a video.

        Args:
            video_id: YouTube video ID

        Returns:
            Analysis data dict if cached, None otherwise
        """
        cache_file = self.analysis_dir / f"{video_id}.json"

        if cache_file.exists():
            self.cache_hits += 1
            self.logger.debug(f"Cache hit: analysis for {video_id}")
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Error reading cached analysis for {video_id}: {e}")
                return None
        else:
            self.cache_misses += 1
            self.logger.debug(f"Cache miss: analysis for {video_id}")
            return None

    def save_analysis(self, video_id: str, analysis_data: Dict[str, Any]) -> bool:
        """
        Save analysis results to cache.

        Args:
            video_id: YouTube video ID
            analysis_data: Analysis results dictionary

        Returns:
            True if successful, False otherwise
        """
        cache_file = self.analysis_dir / f"{video_id}.json"

        try:
            # Add cache metadata
            cache_entry = {
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "data": analysis_data
            }

            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_entry, f, indent=2, ensure_ascii=False)
            self.logger.debug(f"Cached analysis for {video_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error caching analysis for {video_id}: {e}")
            return False

    def clear_transcript_cache(self) -> int:
        """
        Clear all cached transcripts.

        Returns:
            Number of files deleted
        """
        count = 0
        for cache_file in self.transcripts_dir.glob("*.txt"):
            try:
                cache_file.unlink()
                count += 1
            except Exception as e:
                self.logger.error(f"Error deleting {cache_file}: {e}")
        self.logger.info(f"Cleared {count} cached transcripts")
        return count

    def clear_analysis_cache(self) -> int:
        """
        Clear all cached analysis results.

        Returns:
            Number of files deleted
        """
        count = 0
        for cache_file in self.analysis_dir.glob("*.json"):
            try:
                cache_file.unlink()
                count += 1
            except Exception as e:
                self.logger.error(f"Error deleting {cache_file}: {e}")
        self.logger.info(f"Cleared {count} cached analysis results")
        return count

    def clear_all_cache(self) -> int:
        """
        Clear all caches.

        Returns:
            Total number of files deleted
        """
        return self.clear_transcript_cache() + self.clear_analysis_cache()

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        transcript_count = len(list(self.transcripts_dir.glob("*.txt")))
        analysis_count = len(list(self.analysis_dir.glob("*.json")))

        # Calculate cache size
        transcript_size = sum(f.stat().st_size for f in self.transcripts_dir.glob("*.txt"))
        analysis_size = sum(f.stat().st_size for f in self.analysis_dir.glob("*.json"))

        stats = {
            "transcripts": {
                "count": transcript_count,
                "size_mb": transcript_size / (1024 * 1024)
            },
            "analysis": {
                "count": analysis_count,
                "size_mb": analysis_size / (1024 * 1024)
            },
            "session_stats": {
                "hits": self.cache_hits,
                "misses": self.cache_misses,
                "hit_rate": self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0
            }
        }

        return stats

    def log_cache_stats(self):
        """Log cache statistics."""
        stats = self.get_cache_stats()
        self.logger.info(f"Cache Stats - Transcripts: {stats['transcripts']['count']} files ({stats['transcripts']['size_mb']:.2f} MB)")
        self.logger.info(f"Cache Stats - Analysis: {stats['analysis']['count']} files ({stats['analysis']['size_mb']:.2f} MB)")

        if stats['session_stats']['hits'] + stats['session_stats']['misses'] > 0:
            hit_rate = stats['session_stats']['hit_rate'] * 100
            self.logger.info(f"Cache Hit Rate: {hit_rate:.1f}% ({stats['session_stats']['hits']} hits, {stats['session_stats']['misses']} misses)")
