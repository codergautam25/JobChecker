"""Approval queue data models.

Every AI-generated action must enter the approval queue before execution.
No email is ever sent without explicit human approval.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class ApprovalStatus(str, Enum):
    """Approval states for queued actions."""

    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ApprovalAction(BaseModel):
    """An action awaiting human review.

    Encapsulates any side-effecting operation (send email, update record, etc.)
    that must be approved before execution.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    action_type: str = Field(
        description="Type of action: 'send_email', 'update_application', 'create_application'"
    )
    payload: dict[str, Any] = Field(
        description="Full action data — the draft email, record updates, etc."
    )
    status: ApprovalStatus = ApprovalStatus.PENDING_APPROVAL
    created_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_at: Optional[datetime] = None
    reviewer_notes: Optional[str] = None
    related_email_id: Optional[str] = None
    related_application_id: Optional[str] = None

    def approve(self, notes: Optional[str] = None) -> None:
        """Mark this action as approved."""
        self.status = ApprovalStatus.APPROVED
        self.reviewed_at = datetime.utcnow()
        if notes:
            self.reviewer_notes = notes

    def reject(self, notes: Optional[str] = None) -> None:
        """Mark this action as rejected."""
        self.status = ApprovalStatus.REJECTED
        self.reviewed_at = datetime.utcnow()
        if notes:
            self.reviewer_notes = notes

    @property
    def is_pending(self) -> bool:
        return self.status == ApprovalStatus.PENDING_APPROVAL
