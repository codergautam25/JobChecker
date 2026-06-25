"""Interview data models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class InterviewType(str, Enum):
    """Types of interviews in the hiring pipeline."""

    PHONE_SCREEN = "PHONE_SCREEN"
    TECHNICAL = "TECHNICAL"
    BEHAVIORAL = "BEHAVIORAL"
    ONSITE = "ONSITE"
    PANEL = "PANEL"
    TAKE_HOME = "TAKE_HOME"
    FINAL = "FINAL"
    OTHER = "OTHER"


class InterviewStatus(str, Enum):
    """Status of a scheduled interview."""

    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    RESCHEDULED = "RESCHEDULED"
    NO_SHOW = "NO_SHOW"


class Interview(BaseModel):
    """Represents a single interview event."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    application_id: str = Field(description="FK to the parent job application")
    interview_type: InterviewType = InterviewType.OTHER
    scheduled_at: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(default=None, ge=1)
    location: Optional[str] = Field(
        default=None,
        description="URL for virtual interviews, address for in-person",
    )
    interviewer_names: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    status: InterviewStatus = InterviewStatus.SCHEDULED
    source_email_id: Optional[str] = Field(
        default=None, description="Gmail message ID that contained this invite"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def mark_completed(self, notes: Optional[str] = None) -> None:
        """Mark the interview as completed."""
        self.status = InterviewStatus.COMPLETED
        if notes:
            self.notes = notes
        self.updated_at = datetime.utcnow()

    def cancel(self) -> None:
        """Cancel the interview."""
        self.status = InterviewStatus.CANCELLED
        self.updated_at = datetime.utcnow()
