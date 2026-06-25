"""Email-related data models.

Covers raw email messages, classification results, attachment metadata,
and draft reply structures.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EmailCategory(str, Enum):
    """Classification categories for incoming emails."""

    APPLY_JOB = "APPLY_JOB"
    REPLY_RECRUITER = "REPLY_RECRUITER"
    INTERVIEW = "INTERVIEW"
    REJECTION = "REJECTION"
    IGNORE = "IGNORE"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class AttachmentInfo(BaseModel):
    """Metadata for an email attachment."""

    attachment_id: str
    filename: str
    mime_type: str
    size_bytes: int = 0
    local_path: Optional[str] = None  # Set after download


class EmailMessage(BaseModel):
    """Represents a single email message fetched from Gmail."""

    message_id: str = Field(description="Gmail API message ID")
    thread_id: str = Field(description="Gmail conversation thread ID")
    subject: str = ""
    sender: str = Field(description="From address (e.g. 'Name <email@example.com>')")
    recipient: str = ""
    date: datetime = Field(default_factory=datetime.utcnow)
    body_text: str = ""
    body_html: Optional[str] = None
    labels: list[str] = Field(default_factory=list)
    attachments: list[AttachmentInfo] = Field(default_factory=list)
    is_read: bool = False

    def sender_email(self) -> str:
        """Extract bare email address from sender field."""
        if "<" in self.sender and ">" in self.sender:
            return self.sender.split("<")[1].rstrip(">").strip()
        return self.sender.strip()

    def sender_name(self) -> str:
        """Extract display name from sender field."""
        if "<" in self.sender:
            return self.sender.split("<")[0].strip().strip('"')
        return self.sender.strip()


class EmailClassification(BaseModel):
    """LLM classification result for an email."""

    category: EmailCategory
    confidence: float = Field(ge=0.0, le=1.0, description="Classification confidence 0-1")
    reasoning: str = Field(description="Why the email was classified this way")
    is_suspicious: bool = Field(default=False, description="Whether the email seems suspicious/spammy")


class DraftReply(BaseModel):
    """A generated reply draft awaiting human approval."""

    to: str = Field(description="Recipient email address")
    subject: str = Field(description="Reply subject line")
    body: str = Field(description="Reply body text")
    reply_to_message_id: Optional[str] = Field(
        default=None, description="Gmail message ID to reply to (for threading)"
    )
    suggested_resume: Optional[str] = Field(
        default=None, description="Filename of the suggested resume to attach"
    )
    suggested_cover_letter: Optional[str] = Field(
        default=None, description="Filename of the suggested cover letter"
    )
    generation_reasoning: str = Field(
        default="", description="LLM reasoning for this draft"
    )
