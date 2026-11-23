"""Configuration and path management for the benchmark engine."""

import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_ROOT = Path(__file__).resolve().parent


def load_project_env() -> None:
    """Load key-value pairs from root .env if present without overwriting existing environment."""
    env_file = PROJECT_ROOT / ".env"
    if not env_file.is_file():
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file, override=False)
    except ImportError:
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass


load_project_env()

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
