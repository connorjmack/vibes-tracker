# Migration Guide: v0.x → v1.0

This guide helps you adapt to the new professional package structure introduced in v1.0.

## Overview of Changes

Version 1.0 represents a complete reorganization of the codebase to follow professional Python packaging standards. The most significant changes are:

1. **New CLI command**: `vibes-tracker` instead of `python src/main.py`
2. **Proper package structure**: All code moved into `src/vibes_tracker/` package
3. **Cleaned imports**: Removed all `sys.path.insert()` hacks
4. **Organized documentation**: All docs moved to `docs/` subdirectories
5. **Removed GUI**: The incomplete Streamlit GUI has been removed
6. **Merged scripts**: Duplicate historical collection scripts unified

## Breaking Changes

### 1. CLI Command Format

**Before (v0.x):**
```bash
python src/main.py ingest --incremental
python src/main.py analyze --workers 10
python src/main.py visualize
python src/main.py temporal --days-back 30
python src/main.py compare
python src/main.py collect-historical --start-year 2022
python src/main.py pipeline --incremental
```

**After (v1.0):**
```bash
vibes-tracker ingest --incremental
vibes-tracker analyze --workers 10
vibes-tracker visualize
vibes-tracker temporal --days-back 30
vibes-tracker compare
vibes-tracker collect-historical --start-year 2022
vibes-tracker pipeline --incremental
```

### 2. Installation Required

**Before:** Just run scripts directly from the repository

**After:** Install the package first:
```bash
# Install in editable mode (recommended for development)
pip install -e .

# Or install normally
pip install .
```

This installs all dependencies and registers the `vibes-tracker` command.

### 3. Python Imports (For Custom Scripts)

If you have custom scripts that import from this package:

**Before (v0.x):**
```python
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.utils.config_loader import load_config
from src.ingest import ingest_clusters
from src.analyze import get_transcript
from src.temporal_analysis import save_historical_snapshot
```

**After (v1.0):**
```python
# No sys.path hacks needed!
from vibes_tracker.utils.config_loader import load_config
from vibes_tracker.core.ingest import ingest_clusters
from vibes_tracker.core.analyze import get_transcript
from vibes_tracker.analysis.temporal import save_historical_snapshot
```

### 4. Historical Collection

**Before:** Two separate scripts with different features
- `scripts/collect_historical_data.py`
- `scripts/incremental_historical_collection.py`

**After:** Unified command
```bash
vibes-tracker collect-historical --start-year 2022 --end-year 2024 --frequency monthly
```

### 5. Documentation Location

**Before:** Scattered across root directory

**After:** Organized in `docs/` directory
- User guides: `docs/GETTING_STARTED.md`, `docs/MULTI_YEAR_ANALYSIS_GUIDE.md`
- Technical docs: `docs/TECHNICAL_GUIDE.md`
- Implementation reports: `docs/reports/`

### 6. GUI Removed

The incomplete Streamlit GUI (`gui/app.py`) has been removed. If you were using it, you'll need to:
- Use the CLI commands instead
- Or implement your own interface using the package as a library

## Migration Steps

### Step 1: Update Your Virtual Environment

```bash
# Activate your virtual environment
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install the new package structure
pip install -e .
```

### Step 2: Update Your Scripts/Aliases

If you have shell scripts or aliases that use the old command format:

```bash
# Replace this:
alias vibes='python src/main.py'

# With this:
# (No alias needed! Just use vibes-tracker directly)
```

Or update your scripts:
```bash
# OLD
python src/main.py ingest --incremental

# NEW
vibes-tracker ingest --incremental
```

### Step 3: Update Custom Python Scripts

If you have custom Python scripts that import from vibes-tracker:

1. Remove all `sys.path.insert()` lines
2. Update imports from `src.*` to `vibes_tracker.*`
3. Update module paths:
   - `src.ingest` → `vibes_tracker.core.ingest`
   - `src.analyze` → `vibes_tracker.core.analyze`
   - `src.temporal_analysis` → `vibes_tracker.analysis.temporal`
   - `src.cross_cluster_analysis` → `vibes_tracker.analysis.cross_cluster`
   - `src.utils.*` → `vibes_tracker.utils.*`
   - `src.visualizations.*` → `vibes_tracker.visualizations.*`

### Step 4: Update Scheduled Jobs

If you have cron jobs or scheduled tasks:

```bash
# OLD cron job
0 0 * * * cd /path/to/vibes-tracker && python src/main.py pipeline --incremental

# NEW cron job
0 0 * * * cd /path/to/vibes-tracker && vibes-tracker pipeline --incremental
```

## What Didn't Change

These still work exactly the same:

- **Configuration files**: `config/clusters.json`, `config/pipeline_config.yaml`, `config/prompts.yaml`
- **Data outputs**: `data/cluster_data.csv`, `data/analyzed_data.csv`, etc.
- **Visualizations**: Output still goes to `figures/`
- **Logs**: Still in `logs/`
- **Environment variables**: `.env` file format unchanged
- **Command-line arguments**: All flags and options work the same
- **Functionality**: All features work identically

## Troubleshooting

### Command not found: vibes-tracker

**Problem:** After running `pip install -e .`, the command `vibes-tracker` is not recognized.

**Solutions:**
1. Make sure your virtual environment is activated
2. Try running with Python directly: `python -m vibes_tracker.cli <command>`
3. Reinstall: `pip uninstall vibes-tracker && pip install -e .`
4. Check if it's installed: `pip list | grep vibes-tracker`

### Import errors in custom scripts

**Problem:** `ModuleNotFoundError: No module named 'vibes_tracker'`

**Solution:** Install the package: `pip install -e .`

### Old command still works?

**Problem:** `python src/main.py` still works, but shouldn't it be removed?

**Answer:** The old `src/main.py` file was removed in v1.0. If it still exists, you may be on an old branch. Run `git status` to check.

### Tests failing after upgrade

**Problem:** Tests show import errors

**Solution:**
1. Make sure the package is installed: `pip install -e .`
2. Run tests with: `python -m pytest tests/ -v`
3. Check that test files import from `vibes_tracker.*` not `src.*`

## Additional Resources

- [Getting Started Guide](GETTING_STARTED.md)
- [Technical Architecture Guide](TECHNICAL_GUIDE.md)
- [Multi-Year Analysis Guide](MULTI_YEAR_ANALYSIS_GUIDE.md)

## Questions?

If you encounter issues not covered in this guide, please open an issue on GitHub.
