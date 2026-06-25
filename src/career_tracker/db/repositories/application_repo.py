"""Application repository — CRUD operations for the applications table."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import structlog

from career_tracker.db.database import DatabaseManager, get_database
from career_tracker.models.application import ApplicationStatus, JobApplication

logger = structlog.get_logger(__name__)


class ApplicationRepository:
    """Data access object for job applications."""

    def __init__(self, db: DatabaseManager | None = None) -> None:
        self._db = db or get_database()

    def create(self, app: JobApplication) -> JobApplication:
        """Insert a new application record."""
        sql = """
            INSERT INTO applications
                (id, company, role, status, url, location, salary_range,
                 job_description, recruiter_id, resume_used, cover_letter_used,
                 applied_at, source_email_id, notes, created_at, updated_at)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            app.id, app.company, app.role, app.status.value,
            app.url, app.location, app.salary_range,
            app.job_description, app.recruiter_id,
            app.resume_used, app.cover_letter_used,
            app.applied_at.isoformat() if app.applied_at else None,
            app.source_email_id, app.notes,
            app.created_at.isoformat(), app.updated_at.isoformat(),
        )
        self._db.execute_write(sql, params)
        logger.info("application.created", id=app.id, company=app.company, role=app.role)
        return app

    def get_by_id(self, application_id: str) -> Optional[JobApplication]:
        """Fetch a single application by ID."""
        rows = self._db.execute(
            "SELECT * FROM applications WHERE id = ?", (application_id,)
        )
        if not rows:
            return None
        return self._row_to_model(rows[0])

    def get_by_company(self, company: str) -> list[JobApplication]:
        """Fetch all applications for a given company."""
        rows = self._db.execute(
            "SELECT * FROM applications WHERE company LIKE ? ORDER BY created_at DESC",
            (f"%{company}%",),
        )
        return [self._row_to_model(r) for r in rows]

    def get_by_status(self, status: ApplicationStatus) -> list[JobApplication]:
        """Fetch all applications with a given status."""
        rows = self._db.execute(
            "SELECT * FROM applications WHERE status = ? ORDER BY updated_at DESC",
            (status.value,),
        )
        return [self._row_to_model(r) for r in rows]

    def get_all(self, limit: int = 100, offset: int = 0) -> list[JobApplication]:
        """Fetch all applications with pagination."""
        rows = self._db.execute(
            "SELECT * FROM applications ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [self._row_to_model(r) for r in rows]

    def update(self, app: JobApplication) -> JobApplication:
        """Update an existing application record."""
        app.updated_at = datetime.utcnow()
        sql = """
            UPDATE applications SET
                company = ?, role = ?, status = ?, url = ?, location = ?,
                salary_range = ?, job_description = ?, recruiter_id = ?,
                resume_used = ?, cover_letter_used = ?, applied_at = ?,
                source_email_id = ?, notes = ?, updated_at = ?
            WHERE id = ?
        """
        params = (
            app.company, app.role, app.status.value, app.url, app.location,
            app.salary_range, app.job_description, app.recruiter_id,
            app.resume_used, app.cover_letter_used,
            app.applied_at.isoformat() if app.applied_at else None,
            app.source_email_id, app.notes, app.updated_at.isoformat(),
            app.id,
        )
        self._db.execute_write(sql, params)
        logger.info("application.updated", id=app.id, status=app.status.value)
        return app

    def update_status(self, application_id: str, status: ApplicationStatus) -> None:
        """Update just the status of an application."""
        now = datetime.utcnow().isoformat()
        self._db.execute_write(
            "UPDATE applications SET status = ?, updated_at = ? WHERE id = ?",
            (status.value, now, application_id),
        )
        logger.info("application.status_updated", id=application_id, status=status.value)

    def delete(self, application_id: str) -> None:
        """Delete an application by ID."""
        self._db.execute_write("DELETE FROM applications WHERE id = ?", (application_id,))
        logger.info("application.deleted", id=application_id)

    def find_by_email_id(self, email_id: str) -> Optional[JobApplication]:
        """Find an application linked to a specific source email."""
        rows = self._db.execute(
            "SELECT * FROM applications WHERE source_email_id = ?", (email_id,)
        )
        if not rows:
            return None
        return self._row_to_model(rows[0])

    @staticmethod
    def _row_to_model(row: dict) -> JobApplication:
        """Convert a database row dict to a JobApplication model."""
        return JobApplication(
            id=row["id"],
            company=row["company"],
            role=row["role"],
            status=ApplicationStatus(row["status"]),
            url=row.get("url"),
            location=row.get("location"),
            salary_range=row.get("salary_range"),
            job_description=row.get("job_description"),
            recruiter_id=row.get("recruiter_id"),
            resume_used=row.get("resume_used"),
            cover_letter_used=row.get("cover_letter_used"),
            applied_at=datetime.fromisoformat(row["applied_at"]) if row.get("applied_at") else None,
            source_email_id=row.get("source_email_id"),
            notes=row.get("notes"),
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else datetime.utcnow(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else datetime.utcnow(),
        )
