"""SendReplyNode — sends an approved email via Gmail.

Only called after human approval. Saves successful responses to
semantic memory for future context.
"""

from __future__ import annotations

import structlog

from career_tracker.db.repositories.event_repo import EventRepository
from career_tracker.memory.store import APPROVED_RESPONSES, get_memory_store
from career_tracker.mcp_servers.gmail_server import send_email
from career_tracker.models.state import WorkflowState

logger = structlog.get_logger(__name__)


def send_reply_node(state: WorkflowState) -> dict:
    """Send the approved reply via Gmail and save to semantic memory.

    This node should only execute after the human_approval node
    has been passed with an APPROVED status.
    """
    draft_reply = state.get("draft_reply")
    if not draft_reply:
        logger.warning("node.send_reply.no_draft")
        return {"current_node": "send_reply"}

    logger.info(
        "node.send_reply.start",
        to=draft_reply.get("to"),
        subject=draft_reply.get("subject", "")[:50],
    )

    try:
        # Send via Gmail MCP tool
        result = send_email(
            to=draft_reply["to"],
            subject=draft_reply["subject"],
            body=draft_reply["body"],
            reply_to_message_id=draft_reply.get("reply_to_message_id"),
        )

        logger.info(
            "node.send_reply.sent",
            message_id=result.get("message_id"),
            thread_id=result.get("thread_id"),
        )

        # Save to semantic memory for future context
        try:
            job_info = state.get("job_info", {}) or {}
            store = get_memory_store()
            store.save(
                collection=APPROVED_RESPONSES,
                doc_id=result.get("message_id", draft_reply.get("reply_to_message_id", "")),
                content=draft_reply["body"],
                metadata={
                    "company": job_info.get("company", ""),
                    "role": job_info.get("role", ""),
                    "to": draft_reply["to"],
                    "subject": draft_reply["subject"],
                    "outcome": "sent",
                },
            )
            logger.info("node.send_reply.saved_to_memory")
        except Exception as e:
            logger.warning("node.send_reply.memory_save_failed", error=str(e))

        # Log audit event
        EventRepository().log(
            event_type="email_sent",
            entity_type="email",
            entity_id=result.get("message_id", ""),
            data={
                "to": draft_reply["to"],
                "subject": draft_reply["subject"],
                "reply_to": draft_reply.get("reply_to_message_id"),
            },
        )

        return {
            "processed_email_ids": [draft_reply.get("reply_to_message_id", "")],
            "current_node": "send_reply",
        }

    except Exception as e:
        logger.error("node.send_reply.error", error=str(e))
        return {
            "errors": [{
                "node": "send_reply",
                "error_type": type(e).__name__,
                "message": str(e),
                "retryable": True,
            }],
            "current_node": "send_reply",
        }
