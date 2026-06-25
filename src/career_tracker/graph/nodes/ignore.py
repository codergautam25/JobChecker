"""IgnoreNode — marks irrelevant emails as processed with no further action."""

from __future__ import annotations

import structlog

from career_tracker.db.repositories.event_repo import EventRepository
from career_tracker.models.state import WorkflowState

logger = structlog.get_logger(__name__)


def ignore_node(state: WorkflowState) -> dict:
    """Mark an email as processed and ignored — no action taken.

    Used for newsletters, marketing, spam, and non-recruitment emails.
    """
    current_email = state.get("current_email")
    message_id = current_email.get("message_id", "") if current_email else ""

    logger.info(
        "node.ignore.processed",
        message_id=message_id,
        subject=current_email.get("subject", "")[:50] if current_email else "",
    )

    # Log for analytics (track ignore rate)
    EventRepository().log(
        event_type="email_ignored",
        entity_type="email",
        entity_id=message_id,
        data={
            "subject": current_email.get("subject", "") if current_email else "",
            "sender": current_email.get("sender", "") if current_email else "",
        },
    )

    # Update emails table status to REJECTED in database
    if message_id:
        try:
            from career_tracker.db.database import get_database
            db = get_database()
            db.execute_write("UPDATE emails SET status='REJECTED' WHERE id=?", (message_id,))
        except Exception as e:
            logger.error("node.ignore.update_email_status_error", error=str(e))

    return {
        "processed_email_ids": [message_id] if message_id else [],
        "current_node": "ignore",
    }
