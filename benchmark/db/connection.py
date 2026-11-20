"""SQLite database connection management and pragmas for benchmark.sqlite."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator

from benchmark.config import get_db_path


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open and configure a SQLite connection for the benchmark database.

    Enforces foreign key checks, WAL journaling, and busy timeout.
    """
    if db_path is None:
        target = get_db_path()
    elif isinstance(db_path, str) and db_path != ":memory:":
        target = Path(db_path)
    else:
        target = db_path

    if isinstance(target, Path):
        target.parent.mkdir(parents=True, exist_ok=True)
        path_str = str(target)
    else:
        path_str = target

    conn = sqlite3.connect(path_str, timeout=10.0)
    conn.row_factory = sqlite3.Row

    # Enforce SQLite configuration invariants
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    if path_str != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL;")

    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Provide a transactional scope around a series of operations."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
