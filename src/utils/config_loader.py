"""Configuration loader for vibes-tracker pipeline."""

import os
import yaml
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field


class IngestConfig(BaseModel):
    """Configuration for data ingestion."""
    videos_per_channel: int = Field(default=30, description="Number of recent videos to fetch per channel")
    cache_channel_ids: bool = Field(default=True, description="Whether to cache channel ID lookups")
    channel_id_cache_path: str = Field(default="data/channel_ids.json", description="Path to channel ID cache")


class AnalysisConfig(BaseModel):
    """Configuration for AI analysis."""
    model: str = Field(default="gemini-1.5-flash", description="Gemini model to use")
    max_tokens: int = Field(default=64000, description="Maximum tokens for model context")
    enable_caching: bool = Field(default=True, description="Whether to cache transcripts and analysis")
    cache_dir: str = Field(default="data/cache", description="Directory for caching")


class VisualizationConfig(BaseModel):
    """Configuration for visualizations."""
    output_dir: str = Field(default="figures", description="Output directory for visualizations")
    wordcloud_width: int = Field(default=1200, description="Width of word cloud images")
    wordcloud_height: int = Field(default=800, description="Height of word cloud images")
    custom_stopwords: List[str] = Field(default_factory=list, description="Custom stopwords for word clouds")


class YouTubeAPIRateLimitConfig(BaseModel):
    """Configuration for YouTube Data API rate limiting."""
    enabled: bool = Field(default=True, description="Enable rate limiting for YouTube API")
    min_delay_seconds: float = Field(default=1.0, description="Minimum delay between requests (seconds)")
    max_delay_seconds: float = Field(default=60.0, description="Maximum backoff delay (seconds)")
    max_retries: int = Field(default=5, description="Maximum retry attempts")
    backoff_multiplier: float = Field(default=2.0, description="Exponential backoff multiplier")
    requests_per_second: float = Field(default=0.5, description="Token bucket rate (requests per second)")
    burst_size: int = Field(default=3, description="Token bucket burst size")


class TranscriptAPIRateLimitConfig(BaseModel):
    """Configuration for transcript API rate limiting."""
    enabled: bool = Field(default=True, description="Enable rate limiting for transcript fetching")
    min_delay_seconds: float = Field(default=0.5, description="Minimum delay between requests (seconds)")
    max_delay_seconds: float = Field(default=5.0, description="Maximum delay (seconds)")
    delay_jitter: float = Field(default=0.3, description="Random jitter (0-1 fraction of base delay)")
    max_retries: int = Field(default=3, description="Maximum retry attempts")


class BatchOperationsConfig(BaseModel):
    """Configuration for batch operations."""
    delay_between_batches: float = Field(default=2.0, description="Delay between batch operations (seconds)")
    max_parallel_workers: int = Field(default=5, description="Maximum parallel workers")


class RateLimitingConfig(BaseModel):
    """Configuration for rate limiting across all APIs."""
    youtube_api: YouTubeAPIRateLimitConfig = Field(default_factory=YouTubeAPIRateLimitConfig)
    transcript_api: TranscriptAPIRateLimitConfig = Field(default_factory=TranscriptAPIRateLimitConfig)
    batch_operations: BatchOperationsConfig = Field(default_factory=BatchOperationsConfig)


class PathsConfig(BaseModel):
    """Configuration for file paths."""
    data_dir: str = Field(default="data", description="Main data directory")
    config_dir: str = Field(default="config", description="Configuration directory")
    cluster_config: str = Field(default="config/clusters.json", description="Path to cluster configuration")
    cluster_data: str = Field(default="data/cluster_data.csv", description="Path to cluster data CSV")
    analyzed_data: str = Field(default="data/analyzed_data.csv", description="Path to analyzed data CSV")
    logs_dir: str = Field(default="logs", description="Directory for log files")


class PipelineConfig(BaseModel):
    """Main configuration for the entire pipeline."""
    ingest: IngestConfig = Field(default_factory=IngestConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    visualization: VisualizationConfig = Field(default_factory=VisualizationConfig)
    rate_limiting: RateLimitingConfig = Field(default_factory=RateLimitingConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)


def load_config(config_path: Optional[str] = None) -> PipelineConfig:
    """
    Load pipeline configuration from YAML file.

    Args:
        config_path: Path to configuration file. If None, uses default location.

    Returns:
        PipelineConfig object with loaded configuration.
    """
    if config_path is None:
        # Default path from project root
        config_path = "config/pipeline_config.yaml"

    config_file = Path(config_path)

    if not config_file.exists():
        print(f"Warning: Config file not found at {config_path}. Using defaults.")
        return PipelineConfig()

    with open(config_file, 'r') as f:
        config_dict = yaml.safe_load(f)

    return PipelineConfig(**config_dict)


def get_project_root() -> Path:
    """
    Get the project root directory.

    Returns:
        Path to project root.
    """
    # Find the project root by looking for config directory
    current = Path.cwd()

    # If we're in src/, go up one level
    if current.name == 'src':
        return current.parent

    # If we're at root (has config/ directory), use current
    if (current / 'config').exists():
        return current

    # Otherwise try parent
    if (current.parent / 'config').exists():
        return current.parent

    return current
