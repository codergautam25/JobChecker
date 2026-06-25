"""FetchEmailsNode — fetches recent emails from Gmail via MCP.

This is the entry point of the workflow. It calls the Gmail MCP server
to fetch emails from the last N hours, deduplicates against the DB,
and reports a full funnel: total in window → new → recruitment-related.
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog

from career_tracker.config import get_settings
from career_tracker.models.state import WorkflowState
from career_tracker.mcp_servers.gmail_server import fetch_recent_emails
from career_tracker.db.repositories.email_repo import EmailRepository

logger = structlog.get_logger(__name__)


# Keywords that suggest a recruitment / job email
_RECRUITMENT_KEYWORDS = [
    "job", "role", "position", "opportunity", "recruiter", "hiring",
    "interview", "application", "applied", "candidate", "career",
    "opening", "vacancy", "offer", "resume", "cv", "talent",
    "engineer", "developer", "analyst", "manager", "intern",
]


def _looks_like_recruitment(email: dict) -> bool:
    """Quick keyword heuristic — true if email looks job-related."""
    text = (
        (email.get("subject") or "") + " " + (email.get("body_text") or "")
    ).lower()
    return any(kw in text for kw in _RECRUITMENT_KEYWORDS)


def fetch_emails_node(state: WorkflowState) -> dict:
    """Fetch unprocessed emails from the local database.

    Returns stats for processing:
      total unprocessed -> emails
    """
    logger.info("node.fetch_emails.start")

    settings = get_settings()
    
    try:
        email_repo = EmailRepository()
        unprocessed_rows = email_repo.get_unprocessed(limit=50)
    except Exception as e:
        logger.error("node.fetch_emails.error", error=str(e), error_type=type(e).__name__)
        return {
            "errors": [{
                "node": "fetch_emails",
                "error_type": type(e).__name__,
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "retryable": True,
            }],
            "fetch_stats": {
                "total_in_window": 0, "already_seen": 0,
                "new_emails": 0, "recruitment_emails": 0,
                "hours": 0,
            },
            "current_node": "fetch_emails",
            "should_continue": False,
        }

    import json
    new_emails = []
    for r in unprocessed_rows:
        try:
            labels = json.loads(r["labels"]) if r.get("labels") else []
        except:
            labels = []
            
        email_dict = {
            "message_id": r["id"],
            "thread_id": r.get("thread_id", ""),
            "subject": r.get("subject", ""),
            "sender": r.get("sender", ""),
            "recipient": r.get("recipient", ""),
            "date": r.get("date", ""),
            "body_text": r.get("body_text", ""),
            "body_html": r.get("body_html"),
            "labels": labels,
            "is_read": bool(r.get("is_read")),
            "attachments": json.loads(r["attachments_metadata"]) if r.get("attachments_metadata") else [],
        }
        new_emails.append(email_dict)

    fetch_stats = {
        "total_in_window":   len(new_emails),
        "unread_count":      sum(1 for e in new_emails if not e["is_read"]),
        "already_seen":      0,
        "new_emails":        len(new_emails),
        "recruitment_emails": 0,  # calculated later if needed
        "hours":             0,
    }

    logger.info("node.fetch_emails.complete", **fetch_stats)

    if not new_emails:
        return {
            "emails": [],
            "fetch_stats": fetch_stats,
            "current_node": "fetch_emails",
            "should_continue": False,
        }

    # Set the first email as current for processing
    current = new_emails[0]

    return {
        "emails": new_emails,
        "current_email": current,
        "fetch_stats": fetch_stats,
        "current_node": "fetch_emails",
        "should_continue": True,
    }
