"""Conditional edge routing functions for the LangGraph workflow.

These functions inspect the current workflow state and determine
which node to execute next.
"""

from __future__ import annotations

from typing import Literal

import structlog

from career_tracker.models.state import WorkflowState

logger = structlog.get_logger(__name__)


def route_by_category(
    state: WorkflowState,
) -> Literal[
    "extract_job_info",
    "extract_recruiter_info",
    "interview",
    "rejection",
    "ignore",
    "human_approval",
    "error_recovery",
]:
    """Route to the appropriate node based on email classification category.

    Called after ClassifyEmailNode to branch the workflow.
    """
    classification = state.get("classification")

    # If no classification or should_continue is False, go to error recovery
    if not classification:
        logger.warning("edges.route_by_category.no_classification")
        return "error_recovery"

    if not state.get("should_continue", True):
        return "error_recovery"

    category = classification.get("category", "HUMAN_REVIEW")

    logger.info("edges.route_by_category", category=category)

    routing = {
        "APPLY_JOB": "human_approval",
        "REPLY_RECRUITER": "human_approval",
        "INTERVIEW": "interview",
        "REJECTION": "rejection",
        "IGNORE": "ignore",
        "HUMAN_REVIEW": "human_approval",
    }

    return routing.get(category, "human_approval")


def route_after_fetch(
    state: WorkflowState,
) -> Literal["classify_email", "__end__"]:
    """Route after FetchEmailsNode — continue only if there are new emails."""
    emails = state.get("emails", [])
    should_continue = state.get("should_continue", True)

    if not emails or not should_continue:
        logger.info("edges.route_after_fetch.no_emails")
        return "__end__"

    return "classify_email"


def route_approval_decision(
    state: WorkflowState,
) -> Literal["send_reply", "__end__"]:
    """Route after HumanApprovalNode based on the approval decision.

    Since the workflow uses ``interrupt_before=["human_approval"]``,
    when execution resumes the pending_approvals will have been updated
    by the human review process.
    """
    pending = state.get("pending_approvals", [])

    if not pending:
        return "__end__"

    latest = pending[-1] if pending else {}

    status = latest.get("status", "PENDING_APPROVAL")

    if status == "APPROVED":
        # Route to send_reply for both new "sent_mail" and legacy "send_email" types.
        # "agent_apply" approvals are portal applications — no email to send.
        action_type = latest.get("action_type", "")
        if action_type in ("sent_mail", "send_email"):
            logger.info("edges.route_approval.approved_send")
            return "send_reply"

    logger.info("edges.route_approval.end", status=status)
    return "__end__"
