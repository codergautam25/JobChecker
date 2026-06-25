"""RejectionNode — processes rejection emails and updates application status."""

from __future__ import annotations

import structlog

from career_tracker.db.repositories import ApplicationRepository, EventRepository
from career_tracker.models.application import ApplicationStatus
from career_tracker.models.state import WorkflowState

logger = structlog.get_logger(__name__)


def rejection_node(state: WorkflowState) -> dict:
    """Process a rejection email.

    Updates the associated application status to REJECTED and logs
    the event for analytics.
    """
    current_email = state.get("current_email")
    if not current_email:
        return {"current_node": "rejection"}

    logger.info(
        "node.rejection.start",
        message_id=current_email.get("message_id"),
        subject=current_email.get("subject", "")[:50],
    )

    app_repo = ApplicationRepository()
    event_repo = EventRepository()
    application_id = None

    # Try to find the associated application
    # 1. By source email
    if current_email.get("message_id"):
        existing = app_repo.find_by_email_id(current_email["message_id"])
        if existing:
            application_id = existing.id

    # 2. By company name from job info
    if not application_id:
        job_info = state.get("job_info")
        if job_info and job_info.get("company"):
            apps = app_repo.get_by_company(job_info["company"])
            # Find the most recent non-rejected application
            for app in apps:
                if app.status != ApplicationStatus.REJECTED:
                    application_id = app.id
                    break

    # Update application status
    if application_id:
        try:
            app_repo.update_status(application_id, ApplicationStatus.REJECTED)
            logger.info("node.rejection.application_updated", application_id=application_id)
        except Exception as e:
            logger.error("node.rejection.update_error", error=str(e))

    # Log audit event
    event_repo.log(
        event_type="rejection_received",
        entity_type="application" if application_id else "email",
        entity_id=application_id or current_email.get("message_id", ""),
        data={
            "subject": current_email.get("subject", ""),
            "sender": current_email.get("sender", ""),
            "application_id": application_id,
        },
    )

    # Update emails table status to REJECTED in database
    message_id = current_email.get("message_id", "")
    if message_id:
        try:
            from career_tracker.db.database import get_database
            db = get_database()
            db.execute_write("UPDATE emails SET status='REJECTED' WHERE id=?", (message_id,))
        except Exception as e:
            logger.error("node.rejection.update_email_status_error", error=str(e))

    logger.info(
        "node.rejection.complete",
        application_id=application_id,
    )

    return {
        "processed_email_ids": [message_id],
        "current_node": "rejection",
    }
