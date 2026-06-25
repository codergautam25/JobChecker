"""SQLite database connection manager.

Provides both synchronous and asynchronous access to the SQLite database.
Handles schema initialization on first run.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import structlog

from career_tracker.config import get_settings, PROJECT_ROOT

logger = structlog.get_logger(__name__)

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class DatabaseManager:
    """Manages SQLite connections and schema lifecycle.

    Usage::

        db = DatabaseManager()
        db.initialize()

        with db.connection() as conn:
            cursor = conn.execute("SELECT * FROM applications")
            rows = cursor.fetchall()
    """

    def __init__(self, db_path: Path | None = None) -> None:
        settings = get_settings()
        self._db_path = db_path or settings.resolve_path(settings.db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    @property
    def db_path(self) -> Path:
        return self._db_path

    def initialize(self) -> None:
        """Create all tables and indexes from schema.sql if they don't exist."""
        if self._initialized:
            return

        schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")

        with self.connection() as conn:
            conn.executescript(schema_sql)
            logger.info("database.initialized", path=str(self._db_path))

        self._initialized = True
        
        # Automatic Migration for Phase 1 new profile columns
        with self.connection() as conn:
            cursor = conn.execute("PRAGMA table_info(user_profiles)")
            columns = [row["name"] for row in cursor.fetchall()]
            new_columns = [
                "experience", "education", "certifications", 
                "projects", "publications", "awards", 
                "languages", "social_links", "parsed_files"
            ]
            for col in new_columns:
                if col not in columns:
                    try:
                        conn.execute(f"ALTER TABLE user_profiles ADD COLUMN {col} TEXT")
                        logger.info("database.migrated_column", column=col)
                    except Exception as e:
                        logger.warning("database.migration_failed", column=col, error=str(e))
                        
            cursor = conn.execute("PRAGMA table_info(emails)")
            columns = [row["name"] for row in cursor.fetchall()]
            for col, col_type in [("attachments_metadata", "TEXT"), ("attachment_extracted_text", "TEXT"), ("matched_skills", "TEXT"), ("status", "TEXT DEFAULT 'PENDING'")]:
                if col not in columns:
                    try:
                        conn.execute(f"ALTER TABLE emails ADD COLUMN {col} {col_type}")
                        logger.info("database.migrated_column", column=col)
                    except Exception as e:
                        logger.warning("database.migration_failed", column=col, error=str(e))

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Yield a SQLite connection with row_factory set to sqlite3.Row.

        Commits on success, rolls back on exception.
        """
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute(
        self,
        sql: str,
        params: tuple | dict | None = None,
    ) -> list[dict]:
        """Execute a query and return results as a list of dicts."""
        with self.connection() as conn:
            cursor = conn.execute(sql, params or ())
            if cursor.description:
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
            return []

    def execute_write(
        self,
        sql: str,
        params: tuple | dict | None = None,
    ) -> int:
        """Execute a write query and return the number of affected rows."""
        with self.connection() as conn:
            cursor = conn.execute(sql, params or ())
            return cursor.rowcount

    def execute_insert(
        self,
        sql: str,
        params: tuple | dict | None = None,
    ) -> str | int:
        """Execute an INSERT and return the last row ID."""
        with self.connection() as conn:
            cursor = conn.execute(sql, params or ())
            return cursor.lastrowid


# ── Module-level singleton ───────────────────────────────────────────────────

_db_manager: DatabaseManager | None = None


def get_database() -> DatabaseManager:
    """Return a cached singleton DatabaseManager, initializing on first call."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
        _db_manager.initialize()
    return _db_manager
