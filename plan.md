# Implementation Plan - Repository Restructuring & Professionalization

## Context & Reasoning
The user has requested a reorganization of the repository to address the issue of "too many moving parts." The current structure uses flat directories (`src/`, `scripts/`, `gui/`) with fragile `sys.path.insert` hacks for imports.
A professional Python project typically follows a `src`-layout package structure. This centralizes code, eliminates import hacks, and separates library logic from scripts and configuration.

**Proposed Architecture:**
1.  **Package Migration**: Move all source code into a proper Python package: `src/vibes_tracker/`.
2.  **Core Separation**: Organize `vibes_tracker` into submodules (`core`, `utils`, `analysis`, `gui`).
3.  **CLI Unification**: Replace standalone scripts in `src/` (like `ingest.py`) with entry points in `vibes_tracker/cli.py` or `vibes_tracker/commands/`.
4.  **Import Standardization**: Remove `sys.path.insert` and use absolute imports (e.g., `from vibes_tracker.utils import ...`).
5.  **Artifact Consolidation**: Move documentation-like files from `results/` to `docs/` and organize outputs.

## Objectives

1.  **Create Package Structure**:
    *   Create `src/vibes_tracker/`.
    *   Create `src/vibes_tracker/__init__.py`.
    *   Create subdirectories: `core`, `utils`, `analysis`, `gui`, `commands`.

2.  **Relocate Modules**:
    *   Move `src/utils` -> `src/vibes_tracker/utils`.
    *   Move `src/visualizations` -> `src/vibes_tracker/visualizations`.
    *   Move core scripts (`ingest.py`, `analyze.py`, `visualize.py`) -> `src/vibes_tracker/core/`.
    *   Move analysis scripts (`temporal_analysis.py`, etc.) -> `src/vibes_tracker/analysis/`.
    *   Move `gui/app.py` -> `src/vibes_tracker/gui/app.py`.

3.  **Refactor Imports**:
    *   Scan all files and replace `from src.utils` with `from vibes_tracker.utils`.
    *   Remove `sys.path.insert` blocks.

4.  **Create Unified CLI**:
    *   Refactor `src/main.py` into `src/vibes_tracker/cli.py` using `argparse` or `click`.
    *   Create a root-level `run_pipeline.py` or entry point wrapper that calls the package CLI.

5.  **Clean Up Root**:
    *   Move `results/` content to `docs/reports/`.
    *   Move `figures/` to `output/figures/` (optional, but good for separation).

## Affected Files
*   All `.py` files in `src/`, `scripts/`, `gui/`.
*   `config/pipeline_config.yaml` (Paths might need updates, though usually relative to execution dir).

## Pre-Flight Checks
*   `git status` (Ensure clean state).
*   `pip freeze` (Check dependencies).

## Testing & Verification
*   **Test Command**: `python -m pytest tests/` (after updating tests to new imports).
*   **Verification**: Run `python -m vibes_tracker.cli --help` and verify all commands appear.

## Risk & Rollback
*   **Risk**: Import errors are the biggest risk. `sys.path` hacks might be hiding circular dependencies.
*   **Rollback**: `git reset --hard HEAD` (since we are doing file moves, git handles this well).