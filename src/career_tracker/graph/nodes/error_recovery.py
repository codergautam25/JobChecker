"""ErrorRecoveryNode — handles errors during workflow execution.

Logs errors, determines retryability, and decides whether to
continue processing or halt.
"""

from __future__ import annotations

import structlog

from career_tracker.db.repositories.event_repo import EventRepository
from career_tracker.models.state import WorkflowState

logger = structlog.get_logger(__name__)

# Errors that should never be retried
_NON_RETRYABLE_ERRORS = {
    "FileNotFoundError",
    "PermissionError",
    "ValueError",
    "KeyError",
}


def error_recovery_node(state: WorkflowState) -> dict:
    """Process and log workflow errors.

    Determines whether errors are retryable and logs full context
    to the events table for debugging.
    """
    errors = state.get("errors", [])
    retry_count = state.get("retry_count", 0)

    logger.info(
        "node.error_recovery.start",
        error_count=len(errors),
        retry_count=retry_count,
    )

    event_repo = EventRepository()

    for error in errors:
        error_type = error.get("error_type", "Unknown")
        is_retryable = (
            error.get("retryable", True)
            and error_type not in _NON_RETRYABLE_ERRORS
        )

        # Log each error as an audit event
        event_repo.log(
            event_type="workflow_error",
            entity_type="workflow",
            entity_id=error.get("node", "unknown"),
            data={
                "error_type": error_type,
                "message": error.get("message", ""),
                "node": error.get("node", ""),
                "retryable": is_retryable,
                "retry_count": retry_count,
            },
        )

        logger.error(
            "node.error_recovery.error_logged",
            node=error.get("node"),
            error_type=error_type,
            retryable=is_retryable,
            message=error.get("message", "")[:200],
        )

    # Mark current email as processed even on error to avoid infinite loops
    current_email = state.get("current_email")
    processed_ids = []
    if current_email and current_email.get("message_id"):
        processed_ids = [current_email["message_id"]]

    logger.info(
        "node.error_recovery.complete",
        processed_ids=processed_ids,
    )

    return {
        "processed_email_ids": processed_ids,
        "current_node": "error_recovery",
        "retry_count": retry_count + 1,
        "should_continue": False,
    }
