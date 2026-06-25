"""Recruiter repository — CRUD operations for the recruiters table."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import structlog

from career_tracker.db.database import DatabaseManager, get_database
from career_tracker.models.recruiter import Recruiter

logger = structlog.get_logger(__name__)


class RecruiterRepository:
    """Data access object for recruiter contacts."""

    def __init__(self, db: DatabaseManager | None = None) -> None:
        self._db = db or get_database()

    def create(self, recruiter: Recruiter) -> Recruiter:
        """Insert a new recruiter record."""
        sql = """
            INSERT INTO recruiters
                (id, name, email, company, title, linkedin_url, phone, notes,
                 first_contact_date, last_contact_date, interaction_count,
                 sentiment, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            recruiter.id, recruiter.name, recruiter.email,
            recruiter.company, recruiter.title, recruiter.linkedin_url,
            recruiter.phone, recruiter.notes,
            recruiter.first_contact_date.isoformat() if recruiter.first_contact_date else None,
            recruiter.last_contact_date.isoformat() if recruiter.last_contact_date else None,
            recruiter.interaction_count, recruiter.sentiment,
            recruiter.created_at.isoformat(), recruiter.updated_at.isoformat(),
        )
        self._db.execute_write(sql, params)
        logger.info("recruiter.created", id=recruiter.id, email=recruiter.email)
        return recruiter

    def get_by_id(self, recruiter_id: str) -> Optional[Recruiter]:
        """Fetch a recruiter by ID."""
        rows = self._db.execute("SELECT * FROM recruiters WHERE id = ?", (recruiter_id,))
        return self._row_to_model(rows[0]) if rows else None

    def get_by_email(self, email: str) -> Optional[Recruiter]:
        """Fetch a recruiter by email address."""
        rows = self._db.execute("SELECT * FROM recruiters WHERE email = ?", (email,))
        return self._row_to_model(rows[0]) if rows else None

    def get_all(self, limit: int = 100, offset: int = 0) -> list[Recruiter]:
        """Fetch all recruiters with pagination."""
        rows = self._db.execute(
            "SELECT * FROM recruiters ORDER BY last_contact_date DESC NULLS LAST LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [self._row_to_model(r) for r in rows]

    def update(self, recruiter: Recruiter) -> Recruiter:
        """Update an existing recruiter record."""
        recruiter.updated_at = datetime.utcnow()
        sql = """
            UPDATE recruiters SET
                name = ?, email = ?, company = ?, title = ?, linkedin_url = ?,
                phone = ?, notes = ?, first_contact_date = ?, last_contact_date = ?,
                interaction_count = ?, sentiment = ?, updated_at = ?
            WHERE id = ?
        """
        params = (
            recruiter.name, recruiter.email, recruiter.company, recruiter.title,
            recruiter.linkedin_url, recruiter.phone, recruiter.notes,
            recruiter.first_contact_date.isoformat() if recruiter.first_contact_date else None,
            recruiter.last_contact_date.isoformat() if recruiter.last_contact_date else None,
            recruiter.interaction_count, recruiter.sentiment,
            recruiter.updated_at.isoformat(), recruiter.id,
        )
        self._db.execute_write(sql, params)
        logger.info("recruiter.updated", id=recruiter.id)
        return recruiter

    def upsert_by_email(self, recruiter: Recruiter) -> Recruiter:
        """Insert or update a recruiter based on email address.

        If a recruiter with the same email exists, update their record
        and increment the interaction count.
        """
        existing = self.get_by_email(recruiter.email)
        if existing:
            existing.name = recruiter.name or existing.name
            existing.company = recruiter.company or existing.company
            existing.title = recruiter.title or existing.title
            existing.linkedin_url = recruiter.linkedin_url or existing.linkedin_url
            existing.phone = recruiter.phone or existing.phone
            existing.record_interaction()
            return self.update(existing)
        else:
            recruiter.first_contact_date = datetime.utcnow()
            recruiter.last_contact_date = datetime.utcnow()
            recruiter.interaction_count = 1
            return self.create(recruiter)

    def delete(self, recruiter_id: str) -> None:
        """Delete a recruiter by ID."""
        self._db.execute_write("DELETE FROM recruiters WHERE id = ?", (recruiter_id,))
        logger.info("recruiter.deleted", id=recruiter_id)

    @staticmethod
    def _row_to_model(row: dict) -> Recruiter:
        """Convert a database row dict to a Recruiter model."""
        return Recruiter(
            id=row["id"],
            name=row["name"],
            email=row["email"],
            company=row.get("company"),
            title=row.get("title"),
            linkedin_url=row.get("linkedin_url"),
            phone=row.get("phone"),
            notes=row.get("notes"),
            first_contact_date=(
                datetime.fromisoformat(row["first_contact_date"])
                if row.get("first_contact_date") else None
            ),
            last_contact_date=(
                datetime.fromisoformat(row["last_contact_date"])
                if row.get("last_contact_date") else None
            ),
            interaction_count=row.get("interaction_count", 0),
            sentiment=row.get("sentiment"),
        )
