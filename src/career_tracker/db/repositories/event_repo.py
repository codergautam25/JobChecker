"""Event repository — audit log operations for the events table."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

import structlog

from career_tracker.db.database import DatabaseManager, get_database

logger = structlog.get_logger(__name__)


class EventRepository:
    """Data access object for audit events.

    Every significant action in the system is logged as an event,
    providing a full audit trail for debugging and compliance.
    """

    def __init__(self, db: DatabaseManager | None = None) -> None:
        self._db = db or get_database()

    def log(
        self,
        event_type: str,
        entity_type: str | None = None,
        entity_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> int:
        """Log a new audit event.

        Args:
            event_type: Event name (e.g. 'email_classified', 'reply_approved').
            entity_type: Related entity type (e.g. 'application', 'email').
            entity_id: Related entity ID.
            data: Arbitrary JSON-serializable context.

        Returns:
            The auto-incremented event ID.
        """
        sql = """
            INSERT INTO events (event_type, entity_type, entity_id, data, created_at)
            VALUES (?, ?, ?, ?, ?)
        """
        params = (
            event_type,
            entity_type,
            entity_id,
            json.dumps(data) if data else None,
            datetime.utcnow().isoformat(),
        )
        event_id = self._db.execute_insert(sql, params)
        logger.info(
            "event.logged",
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        return event_id  # type: ignore[return-value]

    def get_by_entity(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 50,
    ) -> list[dict]:
        """Fetch events related to a specific entity."""
        return self._db.execute(
            """SELECT * FROM events
               WHERE entity_type = ? AND entity_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (entity_type, entity_id, limit),
        )

    def get_by_type(self, event_type: str, limit: int = 50) -> list[dict]:
        """Fetch events of a specific type."""
        return self._db.execute(
            "SELECT * FROM events WHERE event_type = ? ORDER BY created_at DESC LIMIT ?",
            (event_type, limit),
        )

    def get_recent(self, limit: int = 100) -> list[dict]:
        """Fetch the most recent events."""
        return self._db.execute(
            "SELECT * FROM events ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )

    def get_timeline(
        self,
        entity_type: str,
        entity_id: str,
    ) -> list[dict]:
        """Get a chronological timeline for an entity.

        Returns events in ascending order — useful for building
        a full history view.
        """
        rows = self._db.execute(
            """SELECT * FROM events
               WHERE entity_type = ? AND entity_id = ?
               ORDER BY created_at ASC""",
            (entity_type, entity_id),
        )
        # Parse JSON data field
        for row in rows:
            if row.get("data"):
                try:
                    row["data"] = json.loads(row["data"])
                except (json.JSONDecodeError, TypeError):
                    pass
        return rows
