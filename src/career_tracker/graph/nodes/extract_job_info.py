"""ExtractJobInfoNode — extracts structured job data from emails."""

from __future__ import annotations

from typing import Optional

import structlog
from pydantic import BaseModel, Field

from career_tracker.llm.client import get_structured_llm
from career_tracker.llm.prompts import EXTRACT_JOB_INFO_SYSTEM, EXTRACT_JOB_INFO_USER
from career_tracker.models.state import WorkflowState

logger = structlog.get_logger(__name__)


class ExtractedJobInfo(BaseModel):
    """Schema for LLM-extracted job information."""

    company: str = Field(default="Unknown", description="Hiring company name")
    role: str = Field(default="Unknown", description="Job title / role")
    url: Optional[str] = None
    location: Optional[str] = None
    salary_range: Optional[str] = None
    job_description: Optional[str] = None


def extract_job_info_node(state: WorkflowState) -> dict:
    """Extract structured job information from the current email using LLM."""
    current_email = state.get("current_email")
    if not current_email:
        return {"current_node": "extract_job_info"}

    logger.info(
        "node.extract_job_info.start",
        message_id=current_email.get("message_id"),
    )

    try:
        llm = get_structured_llm(ExtractedJobInfo)

        user_prompt = EXTRACT_JOB_INFO_USER.format(
            sender=current_email.get("sender", ""),
            subject=current_email.get("subject", ""),
            body=current_email.get("body_text", "")[:1500],
        )

        result: ExtractedJobInfo = llm.invoke([
            {"role": "system", "content": EXTRACT_JOB_INFO_SYSTEM},
            {"role": "user", "content": user_prompt},
        ])

        job_info = result.model_dump(mode="json")
        job_info["source_email_id"] = current_email.get("message_id")

        logger.info(
            "node.extract_job_info.complete",
            company=result.company,
            role=result.role,
        )

        return {
            "job_info": job_info,
            "current_node": "extract_job_info",
        }

    except Exception as e:
        logger.error("node.extract_job_info.error", error=str(e))
        return {
            "job_info": {
                "company": "Unknown",
                "role": "Unknown",
                "source_email_id": current_email.get("message_id"),
            },
            "errors": [{
                "node": "extract_job_info",
                "error_type": type(e).__name__,
                "message": str(e),
                "retryable": True,
            }],
            "current_node": "extract_job_info",
        }
