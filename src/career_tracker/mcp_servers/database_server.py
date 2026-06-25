"""Database MCP Tool Server.

Exposes SQLite CRUD operations as MCP tools for the LangGraph workflow.
Wraps the repository layer to provide structured, validated data access.

Usage::

    python -m career_tracker.mcp_servers.database_server
"""

from __future__ import annotations

import json
from typing import Any, Optional

import structlog
from mcp.server.fastmcp import FastMCP

from career_tracker.db.database import get_database
from career_tracker.db.repositories import (
    ApplicationRepository,
    EmailRepository,
    EventRepository,
    InterviewRepository,
    RecruiterRepository,
    UserProfileRepository,
)
from career_tracker.models.application import ApplicationStatus, JobApplication
from career_tracker.models.recruiter import Recruiter
from career_tracker.models.interview import Interview, InterviewType

logger = structlog.get_logger(__name__)

mcp = FastMCP("DatabaseToolServer")


# ── Application Tools ────────────────────────────────────────────────────────

@mcp.tool()
def create_application(
    company: str,
    role: str,
    url: Optional[str] = None,
    location: Optional[str] = None,
    salary_range: Optional[str] = None,
    job_description: Optional[str] = None,
    recruiter_id: Optional[str] = None,
    source_email_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    """Create a new job application record.

    Args:
        company: Company name.
        role: Job title / role.
        url: Job posting URL.
        location: Work location.
        salary_range: Compensation range.
        job_description: Brief role description.
        recruiter_id: ID of the associated recruiter.
        source_email_id: Gmail message ID that initiated this application.
        notes: Additional notes.

    Returns:
        The created application as a dict.
    """
    repo = ApplicationRepository()
    app = JobApplication(
        company=company,
        role=role,
        url=url,
        location=location,
        salary_range=salary_range,
        job_description=job_description,
        recruiter_id=recruiter_id,
        source_email_id=source_email_id,
        notes=notes,
    )
    created = repo.create(app)

    # Log audit event
    EventRepository().log(
        event_type="application_created",
        entity_type="application",
        entity_id=created.id,
        data={"company": company, "role": role},
    )

    return created.model_dump(mode="json")


@mcp.tool()
def update_application(application_id: str, **updates: Any) -> dict:
    """Update an existing job application.

    Args:
        application_id: ID of the application to update.
        **updates: Fields to update (status, notes, url, etc.)

    Returns:
        The updated application as a dict.
    """
    repo = ApplicationRepository()
    app = repo.get_by_id(application_id)
    if not app:
        raise ValueError(f"Application not found: {application_id}")

    # Apply updates
    for field, value in updates.items():
        if field == "status":
            value = ApplicationStatus(value)
        if hasattr(app, field):
            setattr(app, field, value)

    updated = repo.update(app)

    EventRepository().log(
        event_type="application_updated",
        entity_type="application",
        entity_id=application_id,
        data={"updates": {k: str(v) for k, v in updates.items()}},
    )

    return updated.model_dump(mode="json")


@mcp.tool()
def get_application(
    application_id: Optional[str] = None,
    company: Optional[str] = None,
    status: Optional[str] = None,
) -> list[dict]:
    """Get application(s) by ID, company, or status.

    Args:
        application_id: Specific application ID.
        company: Filter by company name (partial match).
        status: Filter by status (e.g., 'APPLIED', 'INTERVIEWING').

    Returns:
        List of matching applications as dicts.
    """
    repo = ApplicationRepository()

    if application_id:
        app = repo.get_by_id(application_id)
        return [app.model_dump(mode="json")] if app else []
    elif company:
        apps = repo.get_by_company(company)
        return [a.model_dump(mode="json") for a in apps]
    elif status:
        apps = repo.get_by_status(ApplicationStatus(status))
        return [a.model_dump(mode="json") for a in apps]
    else:
        apps = repo.get_all()
        return [a.model_dump(mode="json") for a in apps]


# ── Recruiter Tools ──────────────────────────────────────────────────────────

@mcp.tool()
def upsert_recruiter(
    name: str,
    email: str,
    company: Optional[str] = None,
    title: Optional[str] = None,
    linkedin_url: Optional[str] = None,
    phone: Optional[str] = None,
) -> dict:
    """Create or update a recruiter contact.

    If a recruiter with the same email exists, their info is updated
    and interaction count incremented. Otherwise a new record is created.

    Returns:
        The recruiter record as a dict.
    """
    repo = RecruiterRepository()
    recruiter = Recruiter(
        name=name,
        email=email,
        company=company,
        title=title,
        linkedin_url=linkedin_url,
        phone=phone,
    )
    result = repo.upsert_by_email(recruiter)

    EventRepository().log(
        event_type="recruiter_upserted",
        entity_type="recruiter",
        entity_id=result.id,
        data={"email": email, "company": company},
    )

    return result.model_dump(mode="json")


@mcp.tool()
def get_recruiter(
    recruiter_id: Optional[str] = None,
    email: Optional[str] = None,
) -> Optional[dict]:
    """Get a recruiter by ID or email.

    Returns:
        The recruiter record, or None if not found.
    """
    repo = RecruiterRepository()
    if recruiter_id:
        r = repo.get_by_id(recruiter_id)
    elif email:
        r = repo.get_by_email(email)
    else:
        return None
    return r.model_dump(mode="json") if r else None


# ── Event / Audit Tools ──────────────────────────────────────────────────────

@mcp.tool()
def create_event(
    event_type: str,
    entity_type: str,
    entity_id: str,
    data: Optional[dict] = None,
) -> dict:
    """Log an audit event.

    Args:
        event_type: Event name (e.g., 'email_classified', 'reply_approved').
        entity_type: Related entity type ('application', 'email', 'recruiter').
        entity_id: Related entity ID.
        data: Arbitrary JSON context.

    Returns:
        Dict with the new event ID.
    """
    event_id = EventRepository().log(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        data=data,
    )
    return {"event_id": event_id, "event_type": event_type}


@mcp.tool()
def get_entity_timeline(entity_type: str, entity_id: str) -> list[dict]:
    """Get the full audit timeline for an entity.

    Returns:
        Chronological list of events for the entity.
    """
    return EventRepository().get_timeline(entity_type, entity_id)


# ── Approval Queue Tools ─────────────────────────────────────────────────────

@mcp.tool()
def enqueue_approval(
    action_type: str,
    payload: dict,
    related_email_id: Optional[str] = None,
    related_application_id: Optional[str] = None,
) -> dict:
    """Add an action to the human approval queue.

    Args:
        action_type: Type of action ('send_email', 'update_application').
        payload: The full action data (e.g., draft email content).
        related_email_id: Associated email ID.
        related_application_id: Associated application ID.

    Returns:
        The queued approval action as a dict.
    """
    from career_tracker.models.approval import ApprovalAction

    action = ApprovalAction(
        action_type=action_type,
        payload=payload,
        related_email_id=related_email_id,
        related_application_id=related_application_id,
    )

    db = get_database()
    db.execute_write(
        """INSERT INTO approval_queue
            (id, action_type, payload, status, related_email_id,
             related_application_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            action.id, action.action_type, json.dumps(action.payload),
            action.status.value, action.related_email_id,
            action.related_application_id, action.created_at.isoformat(),
        ),
    )

    EventRepository().log(
        event_type="approval_queued",
        entity_type="approval",
        entity_id=action.id,
        data={"action_type": action_type},
    )

    logger.info("approval.queued", id=action.id, action_type=action_type)
    return action.model_dump(mode="json")


@mcp.tool()
def get_pending_approvals() -> list[dict]:
    """Get all actions pending human approval.

    Returns:
        List of pending approval actions.
    """
    db = get_database()
    rows = db.execute(
        "SELECT * FROM approval_queue WHERE status = 'PENDING_APPROVAL' ORDER BY created_at ASC"
    )
    for row in rows:
        if row.get("payload"):
            try:
                row["payload"] = json.loads(row["payload"])
            except (json.JSONDecodeError, TypeError):
                pass
    return rows


@mcp.tool()
def review_approval(
    approval_id: str,
    decision: str,
    notes: Optional[str] = None,
) -> dict:
    """Review a pending approval action.

    Args:
        approval_id: ID of the approval to review.
        decision: 'APPROVED' or 'REJECTED'.
        notes: Optional reviewer notes.

    Returns:
        The updated approval action.
    """
    from datetime import datetime

    if decision not in ("APPROVED", "REJECTED"):
        raise ValueError("Decision must be 'APPROVED' or 'REJECTED'.")

    db = get_database()
    now = datetime.utcnow().isoformat()

    db.execute_write(
        """UPDATE approval_queue SET
            status = ?, reviewer_notes = ?, reviewed_at = ?
           WHERE id = ?""",
        (decision, notes, now, approval_id),
    )

    EventRepository().log(
        event_type=f"approval_{decision.lower()}",
        entity_type="approval",
        entity_id=approval_id,
        data={"decision": decision, "notes": notes},
    )

    logger.info("approval.reviewed", id=approval_id, decision=decision)

    rows = db.execute("SELECT * FROM approval_queue WHERE id = ?", (approval_id,))
    if rows and rows[0].get("payload"):
        try:
            rows[0]["payload"] = json.loads(rows[0]["payload"])
        except (json.JSONDecodeError, TypeError):
            pass
    return rows[0] if rows else {"id": approval_id, "status": decision}


if __name__ == "__main__":
    mcp.run(transport="stdio")
