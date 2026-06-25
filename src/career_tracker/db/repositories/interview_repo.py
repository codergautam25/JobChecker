"""Interview repository — CRUD operations for the interviews table."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import structlog

from career_tracker.db.database import DatabaseManager, get_database
from career_tracker.models.interview import Interview, InterviewStatus, InterviewType

logger = structlog.get_logger(__name__)


class InterviewRepository:
    """Data access object for interview records."""

    def __init__(self, db: DatabaseManager | None = None) -> None:
        self._db = db or get_database()

    def create(self, interview: Interview) -> Interview:
        """Insert a new interview record."""
        sql = """
            INSERT INTO interviews
                (id, application_id, interview_type, scheduled_at,
                 duration_minutes, location, interviewer_names, notes,
                 status, source_email_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            interview.id, interview.application_id, interview.interview_type.value,
            interview.scheduled_at.isoformat() if interview.scheduled_at else None,
            interview.duration_minutes, interview.location,
            json.dumps(interview.interviewer_names),
            interview.notes, interview.status.value, interview.source_email_id,
            interview.created_at.isoformat(), interview.updated_at.isoformat(),
        )
        self._db.execute_write(sql, params)
        logger.info(
            "interview.created",
            id=interview.id,
            application_id=interview.application_id,
            type=interview.interview_type.value,
        )
        return interview

    def get_by_id(self, interview_id: str) -> Optional[Interview]:
        """Fetch an interview by ID."""
        rows = self._db.execute("SELECT * FROM interviews WHERE id = ?", (interview_id,))
        return self._row_to_model(rows[0]) if rows else None

    def get_by_application(self, application_id: str) -> list[Interview]:
        """Fetch all interviews for a job application."""
        rows = self._db.execute(
            "SELECT * FROM interviews WHERE application_id = ? ORDER BY scheduled_at ASC",
            (application_id,),
        )
        return [self._row_to_model(r) for r in rows]

    def get_upcoming(self, limit: int = 10) -> list[Interview]:
        """Fetch upcoming scheduled interviews."""
        now = datetime.utcnow().isoformat()
        rows = self._db.execute(
            """SELECT * FROM interviews
               WHERE status = 'SCHEDULED' AND scheduled_at > ?
               ORDER BY scheduled_at ASC LIMIT ?""",
            (now, limit),
        )
        return [self._row_to_model(r) for r in rows]

    def update(self, interview: Interview) -> Interview:
        """Update an existing interview."""
        interview.updated_at = datetime.utcnow()
        sql = """
            UPDATE interviews SET
                interview_type = ?, scheduled_at = ?, duration_minutes = ?,
                location = ?, interviewer_names = ?, notes = ?,
                status = ?, updated_at = ?
            WHERE id = ?
        """
        params = (
            interview.interview_type.value,
            interview.scheduled_at.isoformat() if interview.scheduled_at else None,
            interview.duration_minutes, interview.location,
            json.dumps(interview.interviewer_names),
            interview.notes, interview.status.value,
            interview.updated_at.isoformat(), interview.id,
        )
        self._db.execute_write(sql, params)
        logger.info("interview.updated", id=interview.id, status=interview.status.value)
        return interview

    def update_status(self, interview_id: str, status: InterviewStatus) -> None:
        """Update just the status of an interview."""
        now = datetime.utcnow().isoformat()
        self._db.execute_write(
            "UPDATE interviews SET status = ?, updated_at = ? WHERE id = ?",
            (status.value, now, interview_id),
        )

    @staticmethod
    def _row_to_model(row: dict) -> Interview:
        """Convert a database row dict to an Interview model."""
        interviewer_names = []
        if row.get("interviewer_names"):
            try:
                interviewer_names = json.loads(row["interviewer_names"])
            except (json.JSONDecodeError, TypeError):
                pass

        return Interview(
            id=row["id"],
            application_id=row["application_id"],
            interview_type=InterviewType(row["interview_type"]),
            scheduled_at=(
                datetime.fromisoformat(row["scheduled_at"])
                if row.get("scheduled_at") else None
            ),
            duration_minutes=row.get("duration_minutes"),
            location=row.get("location"),
            interviewer_names=interviewer_names,
            notes=row.get("notes"),
            status=InterviewStatus(row.get("status", "SCHEDULED")),
            source_email_id=row.get("source_email_id"),
        )
