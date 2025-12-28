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
