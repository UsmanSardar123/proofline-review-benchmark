"""Configuration and path management for the benchmark engine."""

import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_ROOT = Path(__file__).resolve().parent

DEFAULT_DB_PATH = PROJECT_ROOT / "benchmark.sqlite"
DEFAULT_MIGRATIONS_DIR = BENCHMARK_ROOT / "migrations"
DEFAULT_CASES_DIR = PROJECT_ROOT / "cases"
DEFAULT_EVIDENCE_DIR = PROJECT_ROOT / "evidence" / "raw"

BASELINE_COMMIT = "9b5ac64"


def get_db_path() -> Path:
    """Return the active SQLite database path, supporting environment override."""
    override = os.environ.get("BENCHMARK_DB_PATH")
    if override:
        return Path(override)
    return DEFAULT_DB_PATH


def get_migrations_dir() -> Path:
    """Return the directory containing benchmark schema migrations."""
    return DEFAULT_MIGRATIONS_DIR


def get_cases_dir() -> Path:
    """Return the directory containing the 8 benchmark cases."""
    return DEFAULT_CASES_DIR


def get_evidence_dir() -> Path:
    """Return the root directory for saving raw review response evidence."""
    override = os.environ.get("BENCHMARK_EVIDENCE_DIR")
    if override:
        return Path(override)
    return DEFAULT_EVIDENCE_DIR


def get_python_executable() -> str:
    """Return the current active Python executable without system alias assumptions."""
    return sys.executable
