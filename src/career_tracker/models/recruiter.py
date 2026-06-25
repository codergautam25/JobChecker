"""Recruiter contact data model."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class Recruiter(BaseModel):
    """Represents a recruiter or hiring contact."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(description="Recruiter's full name")
    email: str = Field(description="Recruiter's email address")
    company: Optional[str] = Field(default=None, description="Recruiting firm or hiring company")
    title: Optional[str] = Field(default=None, description="Job title (e.g. 'Technical Recruiter')")
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    first_contact_date: Optional[datetime] = None
    last_contact_date: Optional[datetime] = None
    interaction_count: int = 0
    sentiment: Optional[str] = Field(
        default=None,
        description="Overall sentiment: positive, neutral, or negative",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def record_interaction(self) -> None:
        """Increment the interaction count and update last contact date."""
        self.interaction_count += 1
        self.last_contact_date = datetime.utcnow()
        self.updated_at = datetime.utcnow()
