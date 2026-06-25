"""Email repository — CRUD operations for the emails table."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import structlog

from career_tracker.db.database import DatabaseManager, get_database
from career_tracker.models.email import EmailCategory, EmailClassification, EmailMessage

logger = structlog.get_logger(__name__)


class EmailRepository:
    """Data access object for stored email records."""

    def __init__(self, db: DatabaseManager | None = None) -> None:
        self._db = db or get_database()

    def create(self, email: EmailMessage, classification: EmailClassification | None = None) -> None:
        """Insert a new email record, optionally with classification data."""
        sql = """
            INSERT OR IGNORE INTO emails
                (id, thread_id, subject, sender, recipient, date, body_text,
                 body_html, labels, is_read, category, classification_confidence,
                 classification_reasoning, processed_at, created_at, status, attachments_metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        attachments_json = json.dumps([a.dict() for a in email.attachments]) if email.attachments else None
        params = (
            email.message_id, email.thread_id, email.subject,
            email.sender, email.recipient, email.date.isoformat(),
            email.body_text, email.body_html,
            json.dumps(email.labels), int(email.is_read),
            classification.category.value if classification else None,
            classification.confidence if classification else None,
            classification.reasoning if classification else None,
            datetime.utcnow().isoformat() if classification else None,
            datetime.utcnow().isoformat(),
            "PENDING",
            attachments_json
        )
        self._db.execute_write(sql, params)
        logger.info("email.stored", message_id=email.message_id, subject=email.subject[:50])

    def get_by_id(self, message_id: str) -> Optional[dict]:
        """Fetch an email by Gmail message ID."""
        rows = self._db.execute("SELECT * FROM emails WHERE id = ?", (message_id,))
        return rows[0] if rows else None

    def get_by_thread(self, thread_id: str) -> list[dict]:
        """Fetch all emails in a conversation thread."""
        return self._db.execute(
            "SELECT * FROM emails WHERE thread_id = ? ORDER BY date ASC",
            (thread_id,),
        )

    def get_by_category(self, category: EmailCategory, limit: int = 50) -> list[dict]:
        """Fetch emails by classification category."""
        return self._db.execute(
            "SELECT * FROM emails WHERE category = ? ORDER BY date DESC LIMIT ?",
            (category.value, limit),
        )

    def get_unprocessed(self, limit: int = 50) -> list[dict]:
        """Fetch emails that are in PENDING status."""
        return self._db.execute(
            "SELECT * FROM emails WHERE status = 'PENDING' ORDER BY date ASC LIMIT ?",
            (limit,),
        )

    def update_classification(
        self, message_id: str, classification: EmailClassification
    ) -> None:
        """Update the classification for an existing email."""
        status = "PENDING"
        if classification.category.value in ("IGNORE", "REJECTION"):
            status = "REJECTED"

        if getattr(classification, "is_suspicious", False):
            row = self.get_by_id(message_id)
            if row and row["labels"]:
                try:
                    labels = json.loads(row["labels"])
                    if "suspicious" not in labels:
                        labels.append("suspicious")
                    if "spam" not in labels:
                        labels.append("spam")
                    self._db.execute_write(
                        "UPDATE emails SET labels = ? WHERE id = ?",
                        (json.dumps(labels), message_id)
                    )
                except Exception as e:
                    logger.error("email.update_labels_error", error=str(e))

        self._db.execute_write(
            """UPDATE emails SET
                category = ?, classification_confidence = ?,
                classification_reasoning = ?, processed_at = ?,
                status = ?
            WHERE id = ?""",
            (
                classification.category.value,
                classification.confidence,
                classification.reasoning,
                datetime.utcnow().isoformat(),
                status,
                message_id,
            ),
        )
        logger.info(
            "email.classified",
            message_id=message_id,
            category=classification.category.value,
            confidence=classification.confidence,
        )

    def link_to_application(self, message_id: str, application_id: str) -> None:
        """Link an email to a job application."""
        self._db.execute_write(
            "UPDATE emails SET application_id = ? WHERE id = ?",
            (application_id, message_id),
        )

    def link_to_recruiter(self, message_id: str, recruiter_id: str) -> None:
        """Link an email to a recruiter."""
        self._db.execute_write(
            "UPDATE emails SET recruiter_id = ? WHERE id = ?",
            (recruiter_id, message_id),
        )

    def is_processed(self, message_id: str) -> bool:
        """Check if an email has already been processed."""
        rows = self._db.execute(
            "SELECT 1 FROM emails WHERE id = ? AND processed_at IS NOT NULL",
            (message_id,),
        )
        return len(rows) > 0

    def exists(self, message_id: str) -> bool:
        """Check if an email exists in the database."""
        rows = self._db.execute("SELECT 1 FROM emails WHERE id = ?", (message_id,))
        return len(rows) > 0
