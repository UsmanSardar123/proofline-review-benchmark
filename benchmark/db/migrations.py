"""Migration runner for the benchmark database."""

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from benchmark.config import get_migrations_dir


class MigrationError(RuntimeError):
    """Raised when a schema migration fails to apply."""
    pass


def get_current_version(db: sqlite3.Connection) -> int:
    """Retrieve the current schema version from SQLite."""
    row = db.execute("PRAGMA user_version").fetchone()
    return int(row[0]) if row else 0


def migrate_benchmark_db(
    db: sqlite3.Connection,
    migrations_dir: Path | None = None,
) -> list[int]:
    """Run pending numbered SQL migrations on the benchmark database.

    Migrations are applied in sequential order. Each migration is executed inside
    an atomic transaction. Both PRAGMA user_version and the schema_migrations table
    are updated to guarantee idempotency and auditability.

    Returns the list of migration versions applied during this invocation.
    """
    if migrations_dir is None:
        migrations_dir = get_migrations_dir()

    if not migrations_dir.is_dir():
        raise MigrationError(f"Migrations directory does not exist: {migrations_dir}")

    # Ensure schema_migrations table exists for version history
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );
        """
    )
    db.commit()

    current_version = get_current_version(db)
    applied_versions: list[int] = []

    sql_files = sorted(migrations_dir.glob("*.sql"))
    for path in sql_files:
        try:
            version_str = path.name.split("_", 1)[0]
            version = int(version_str)
        except (ValueError, IndexError):
            continue

        if version > current_version:
            script = path.read_text(encoding="utf-8")
            now_iso = datetime.now(timezone.utc).isoformat()
            try:
                with db:
                    db.executescript(script)
                    db.execute(
                        "INSERT OR REPLACE INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                        (version, now_iso),
                    )
                    db.execute(f"PRAGMA user_version = {version};")
                applied_versions.append(version)
                current_version = version
            except Exception as exc:
                raise MigrationError(
                    f"Failed applying migration {path.name} (version {version}): {exc}"
                ) from exc

    return applied_versions
