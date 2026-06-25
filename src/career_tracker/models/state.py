"""LangGraph workflow state definition.

The WorkflowState TypedDict is the single source of truth passed between
every node in the LangGraph execution graph. Fields annotated with
``operator.add`` are *accumulators* — new values are appended rather
than overwriting.
"""

from __future__ import annotations

import operator
from datetime import datetime
from typing import Annotated, Optional

from typing_extensions import TypedDict

from pydantic import BaseModel, Field

from career_tracker.models.email import DraftReply, EmailClassification, EmailMessage
from career_tracker.models.application import JobApplication
from career_tracker.models.recruiter import Recruiter
from career_tracker.models.interview import Interview
from career_tracker.models.approval import ApprovalAction


class WorkflowError(BaseModel):
    """Structured error captured during workflow execution."""

    node: str = Field(description="Name of the node that raised the error")
    error_type: str = Field(description="Exception class name")
    message: str = Field(description="Human-readable error message")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    retryable: bool = True
    retry_count: int = 0


class WorkflowState(TypedDict, total=False):
    """Strongly-typed state flowing through the LangGraph workflow.

    Accumulator fields (``Annotated[list, operator.add]``) are safe for
    parallel node execution — values are merged rather than overwritten.

    Non-accumulator fields hold the *current* processing context and are
    overwritten by each node that updates them.
    """

    # ── Email batch ──────────────────────────────────────────────────────
    # All unread emails fetched in the current cycle
    emails: Annotated[list[dict], operator.add]

    # ── Current processing context ───────────────────────────────────────
    current_email: Optional[dict]
    classification: Optional[dict]

    # ── Extracted entities ───────────────────────────────────────────────
    job_info: Optional[dict]
    recruiter_info: Optional[dict]
    interview_info: Optional[dict]

    # ── Generated output ─────────────────────────────────────────────────
    draft_reply: Optional[dict]
    suggested_resume: Optional[str]
    suggested_cover_letter: Optional[str]

    # ── Approval queue ───────────────────────────────────────────────────
    pending_approvals: Annotated[list[dict], operator.add]

    # ── Processing metadata ──────────────────────────────────────────────
    processed_email_ids: Annotated[list[str], operator.add]
    errors: Annotated[list[dict], operator.add]

    # ── Workflow control ─────────────────────────────────────────────────
    current_node: str
    retry_count: int
    should_continue: bool

    # ── Fetch stats (funnel counts for UI display) ───────────────────────
    fetch_stats: Optional[dict]
