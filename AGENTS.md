# Repository Guidelines

## Project Structure & Module Organization
- `src/gtkmud/` contains the application code, organized by domain: `ui/`, `net/`, `parsers/`, `sound/`, `scripting/`, `config/`, `accessibility/`, and `utils/`.
- `tests/` holds pytest-based unit tests (e.g., `tests/test_sphook_parser.py`).
- `docs/` contains feature documentation (scripting and sound protocols).
- `scripts/` contains example MUD scripting files (`.mud`).
- `resources/` and `data/` contain runtime assets and packaged data files.

## Build, Test, and Development Commands
- `pip install -e .` installs the package in editable mode.
- `pip install -e ".[dev]"` installs dev extras (pytest, coverage).
- `PYTHONPATH=src python -m gtkmud` runs the app from source.
- `PYTHONPATH=src pytest` runs the test suite.
- `PYTHONPATH=src pytest tests/test_ansi_parser.py` runs a single test file.
- `PYTHONPATH=src pytest --cov=gtkmud` runs tests with coverage.

## Coding Style & Naming Conventions
- Python 3.11+ codebase. Keep modules and filenames lowercase with underscores (e.g., `test_sphook_parser.py`).
- Follow existing patterns in `src/gtkmud/` for class and function naming (PEP 8 style).
- No formatter or linter is configured in this repo; keep changes consistent with surrounding files.

## Testing Guidelines
- Tests use `pytest` with `pytest-asyncio` enabled.
- Prefer running pytest from the project venv (e.g., `venv/bin/pytest`) to avoid system pytest config warnings (like `asyncio_mode`).
- Place new tests under `tests/` and use the `test_*.py` naming convention.
- Prefer focused unit tests for parser and scripting behavior.

## Commit & Pull Request Guidelines
- No explicit commit message convention is documented or observable here (no `.git` history available). Use concise, imperative summaries (e.g., “Fix MSP parser edge case”).
- PRs should include: a brief summary, test commands run, and any accessibility/UI notes if UI changes are involved. Include screenshots or recordings for visible UI changes when possible.

## Configuration & Runtime Notes
- The app follows XDG paths for runtime config and caches (see `README.md` for locations).
- System dependencies include GTK4/libadwaita and GStreamer; ensure these are installed before running locally.
