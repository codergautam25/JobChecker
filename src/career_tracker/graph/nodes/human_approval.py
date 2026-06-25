"""HumanApprovalNode — queues actions for human review.

This node creates approval queue entries and triggers a workflow
interrupt so the graph pauses until the human reviews the action.
No email is ever sent without explicit approval.

Action types produced by this node:
  - ``sent_mail``          — A draft reply was generated; send via Gmail.
  - ``agent_apply``        — A portal-link job application; no email to send.
  - ``review_classification`` — Low-confidence classification; human decides.
  - ``review_action``      — Catch-all for anything else.
"""

from __future__ import annotations

import json
import re as _re

import structlog

from career_tracker.db.database import get_database
from career_tracker.db.repositories.event_repo import EventRepository
from career_tracker.models.approval import ApprovalAction, ApprovalStatus
from career_tracker.models.state import WorkflowState

logger = structlog.get_logger(__name__)

# ── URL extraction helpers ────────────────────────────────────────────────────

_PORTAL_KEYWORDS = _re.compile(
    r"(apply|application|naukri|linkedin|indeed|glassdoor|unstop|internshala"
    r"|hirist|iimjobs|monster|shine|apna|portal|careers|job)",
    _re.IGNORECASE,
)

_URL_PATTERN = _re.compile(
    r"https?://[^\s<>\"'\]\)]+",
    _re.IGNORECASE,
)

_ANTI_KEYWORDS = _re.compile(
    r"(unsubscribe|preferences|opt-out|linkedin\.com/in/|linkedin\.com/company/|twitter\.com|facebook\.com|instagram\.com)",
    _re.IGNORECASE,
)


def _extract_apply_url(text: str, html: str = "") -> str:
    """Extract the most likely job-application URL from an email body and HTML.

    Strategy:
    1. Find all https?:// URLs in text.
    2. Extract all href=... URLs from HTML.
    3. Filter out unsubscribe/profile links.
    4. Prefer URLs that contain a known portal keyword.
    5. Fall back to the first URL found.
    6. Return empty string if no URL exists.
    """
    urls = []
    if text:
        urls.extend(_URL_PATTERN.findall(text))
    if html:
        hrefs = _re.findall(r'href=[\'"]?(https?://[^\'" >]+)', html, _re.IGNORECASE)
        urls.extend(hrefs)
        
    if not urls:
        return ""
        
    # Filter out obvious anti-patterns like profile links and unsubscribe links
    valid_urls = [u for u in urls if not _ANTI_KEYWORDS.search(u)]
    if not valid_urls:
        valid_urls = urls  # Fallback to all if everything was filtered out
        
    # Prefer portal-keyword URLs
    for url in valid_urls:
        if _PORTAL_KEYWORDS.search(url):
            return url.rstrip(".,;)")
    # Fallback: first valid URL
    return valid_urls[0].rstrip(".,;)")


# ── Main node ─────────────────────────────────────────────────────────────────


def human_approval_node(state: WorkflowState) -> dict:
    """Create an approval queue entry for the current draft.

    This node:
    1. Determines the correct action category (sent_mail vs agent_apply).
    2. Packages the relevant data into an ApprovalAction.
    3. Persists it to the approval_queue table.
    4. Returns the approval as a pending item.

    The workflow uses ``interrupt_before=["human_approval"]`` (if enabled)
    so LangGraph will pause execution here, allowing the human to review
    and approve/reject before the graph continues.
    """
    current_email = state.get("current_email")
    draft_reply = state.get("draft_reply")
    classification = state.get("classification")

    logger.info("node.human_approval.start")

    category = classification.get("category") if classification else None
    
    print("DEBUG_VARS category:", repr(category), "type_category:", type(category), "draft_reply:", draft_reply, "type_class:", type(classification))

    # ── Determine action type and payload ────────────────────────────────────
    receiver_email = current_email.get("receiver_email", current_email.get("recipient", "")) if current_email else ""

    if draft_reply:
        # An LLM-generated draft exists → this is a send-mail action
        action_type = "sent_mail"
        payload = {
            "draft": draft_reply,
            "classification": classification,
            "suggested_resume": state.get("suggested_resume"),
            "suggested_cover_letter": state.get("suggested_cover_letter"),
            "receiver_email": receiver_email,
        }

    elif category == "APPLY_JOB" and not draft_reply:
        # No draft generated → this is a portal / manual-link application.
        # Extract the apply URL from the email body so the user can click it.
        email_body = current_email.get("body_text", "") if current_email else ""
        email_html = current_email.get("body_html", "") if current_email else ""
        apply_url = _extract_apply_url(email_body, email_html)
        action_type = "agent_apply"
        payload = {
            "draft": None,
            "classification": classification,
            "suggested_resume": None,
            "suggested_cover_letter": None,
            "email_subject": current_email.get("subject", "") if current_email else "",
            "email_sender": current_email.get("sender", "") if current_email else "",
            "email_body": email_body,
            "apply_url": apply_url,
            "receiver_email": receiver_email,
        }

    elif category == "REPLY_RECRUITER" and not draft_reply:
        # Recruiter reply needed but draft is missing — still a mail action
        action_type = "sent_mail"
        payload = {
            "draft": None,
            "classification": classification,
            "suggested_resume": None,
            "suggested_cover_letter": None,
            "email_subject": current_email.get("subject", "") if current_email else "",
            "email_sender": current_email.get("sender", "") if current_email else "",
            "email_body": current_email.get("body_text", "") if current_email else "",
            "receiver_email": receiver_email,
        }

    elif classification and category == "HUMAN_REVIEW":
        action_type = "review_classification"
        payload = {
            "email_subject": current_email.get("subject", "") if current_email else "",
            "email_sender": current_email.get("sender", "") if current_email else "",
            "email_body_preview": (current_email.get("body_text", "")[:500] if current_email else ""),
            "classification": classification,
            "receiver_email": receiver_email,
        }

    elif classification and category == "INTERVIEW":
        action_type = "interview"
        payload = {
            "email_subject": current_email.get("subject", "") if current_email else "",
            "email_sender": current_email.get("sender", "") if current_email else "",
            "email_body_preview": (current_email.get("body_text", "")[:500] if current_email else ""),
            "classification": classification,
            "interview_info": state.get("interview_info"),
            "receiver_email": receiver_email,
        }

    else:
        action_type = "review_action"
        payload = {
            "classification": classification,
            "job_info": state.get("job_info"),
            "recruiter_info": state.get("recruiter_info"),
            "receiver_email": receiver_email,
        }

    # ── Create and persist the approval action ────────────────────────────────
    action = ApprovalAction(
        action_type=action_type,
        payload=payload,
        related_email_id=current_email.get("message_id") if current_email else None,
    )

    try:
        db = get_database()
        db.execute_write(
            """INSERT INTO approval_queue
                (id, action_type, payload, status, related_email_id,
                 related_application_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                action.id,
                action.action_type,
                json.dumps(action.payload, default=str),
                action.status.value,
                action.related_email_id,
                action.related_application_id,
                action.created_at.isoformat(),
            ),
        )

        EventRepository().log(
            event_type="approval_queued",
            entity_type="approval",
            entity_id=action.id,
            data={"action_type": action_type, "email_id": action.related_email_id},
        )

        logger.info(
            "node.human_approval.queued",
            approval_id=action.id,
            action_type=action_type,
        )

    except Exception as e:
        logger.error("node.human_approval.db_error", error=str(e))

    # Mark the email as APPROVED in the emails table — it has been fully
    # processed by the workflow; the approval queue entry tracks the
    # send/apply action separately.
    if action.related_email_id:
        try:
            _db = get_database()
            _db.execute_write(
                "UPDATE emails SET status='APPROVED' WHERE id=?",
                (action.related_email_id,)
            )
            logger.info("node.human_approval.email_marked_approved", email_id=action.related_email_id)
        except Exception as _e:
            logger.error("node.human_approval.email_status_error", error=str(_e))

    return {
        "pending_approvals": [action.model_dump(mode="json")],
        "current_node": "human_approval",
    }
