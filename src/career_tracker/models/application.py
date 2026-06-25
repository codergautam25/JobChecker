"""Job application data models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class ApplicationStatus(str, Enum):
    """Lifecycle states for a job application."""

    DISCOVERED = "DISCOVERED"
    APPLIED = "APPLIED"
    SCREENING = "SCREENING"
    INTERVIEWING = "INTERVIEWING"
    OFFER = "OFFER"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


class JobApplication(BaseModel):
    """Represents a tracked job application."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    company: str = Field(description="Company name")
    role: str = Field(description="Job title / role")
    status: ApplicationStatus = ApplicationStatus.DISCOVERED
    url: Optional[str] = Field(default=None, description="Job posting URL")
    location: Optional[str] = None
    salary_range: Optional[str] = None
    job_description: Optional[str] = None
    recruiter_id: Optional[str] = Field(
        default=None, description="FK to the recruiter who initiated contact"
    )
    resume_used: Optional[str] = None
    cover_letter_used: Optional[str] = None
    applied_at: Optional[datetime] = None
    source_email_id: Optional[str] = Field(
        default=None, description="Gmail message ID that initiated this application"
    )
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def mark_applied(self) -> None:
        """Transition the application to APPLIED status."""
        self.status = ApplicationStatus.APPLIED
        self.applied_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_rejected(self) -> None:
        """Transition the application to REJECTED status."""
        self.status = ApplicationStatus.REJECTED
        self.updated_at = datetime.utcnow()

    def advance_to(self, status: ApplicationStatus) -> None:
        """Advance the application to a new status."""
        self.status = status
        self.updated_at = datetime.utcnow()
