"""ExtractRecruiterInfoNode — extracts recruiter contact details from emails."""

from __future__ import annotations

from typing import Optional

import structlog
from pydantic import BaseModel, Field

from career_tracker.llm.client import get_structured_llm
from career_tracker.llm.prompts import EXTRACT_RECRUITER_INFO_SYSTEM, EXTRACT_RECRUITER_INFO_USER
from career_tracker.models.state import WorkflowState

logger = structlog.get_logger(__name__)


class ExtractedRecruiterInfo(BaseModel):
    """Schema for LLM-extracted recruiter information."""

    name: str = Field(default="Unknown", description="Recruiter's full name")
    email: str = Field(default="", description="Recruiter's email address")
    company: Optional[str] = None
    title: Optional[str] = None
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None


def extract_recruiter_info_node(state: WorkflowState) -> dict:
    """Extract recruiter contact information from the current email using LLM."""
    current_email = state.get("current_email")
    if not current_email:
        return {"current_node": "extract_recruiter_info"}

    logger.info(
        "node.extract_recruiter_info.start",
        message_id=current_email.get("message_id"),
    )

    try:
        llm = get_structured_llm(ExtractedRecruiterInfo)

        user_prompt = EXTRACT_RECRUITER_INFO_USER.format(
            sender=current_email.get("sender", ""),
            subject=current_email.get("subject", ""),
            body=current_email.get("body_text", "")[:1500],
        )

        result: ExtractedRecruiterInfo = llm.invoke([
            {"role": "system", "content": EXTRACT_RECRUITER_INFO_SYSTEM},
            {"role": "user", "content": user_prompt},
        ])

        # Fall back to the From header if LLM didn't extract email
        if not result.email and current_email.get("sender"):
            sender = current_email["sender"]
            if "<" in sender and ">" in sender:
                result.email = sender.split("<")[1].rstrip(">").strip()
            else:
                result.email = sender.strip()

        recruiter_info = result.model_dump(mode="json")

        logger.info(
            "node.extract_recruiter_info.complete",
            name=result.name,
            company=result.company,
        )

        return {
            "recruiter_info": recruiter_info,
            "current_node": "extract_recruiter_info",
        }

    except Exception as e:
        logger.error("node.extract_recruiter_info.error", error=str(e))

        # Fallback: use sender email as minimal info
        sender = current_email.get("sender", "")
        fallback_email = sender
        if "<" in sender:
            fallback_email = sender.split("<")[1].rstrip(">").strip()

        return {
            "recruiter_info": {
                "name": sender.split("<")[0].strip().strip('"') if "<" in sender else sender,
                "email": fallback_email,
            },
            "errors": [{
                "node": "extract_recruiter_info",
                "error_type": type(e).__name__,
                "message": str(e),
                "retryable": True,
            }],
            "current_node": "extract_recruiter_info",
        }
