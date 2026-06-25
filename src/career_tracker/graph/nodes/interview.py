"""InterviewNode — extracts interview details and creates interview records."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import structlog
from pydantic import BaseModel, Field

from career_tracker.db.repositories import (
    ApplicationRepository,
    EventRepository,
    InterviewRepository,
)
from career_tracker.llm.client import get_structured_llm
from career_tracker.llm.prompts import EXTRACT_INTERVIEW_SYSTEM, EXTRACT_INTERVIEW_USER
from career_tracker.memory.store import INTERVIEW_INVITATIONS, get_memory_store
from career_tracker.models.application import ApplicationStatus
from career_tracker.models.interview import Interview, InterviewType
from career_tracker.models.state import WorkflowState

logger = structlog.get_logger(__name__)


class ExtractedInterview(BaseModel):
    """Schema for LLM-extracted interview details."""

    interview_type: str = Field(default="OTHER")
    scheduled_at: Optional[str] = Field(default=None, description="ISO 8601 datetime")
    duration_minutes: Optional[int] = None
    location: Optional[str] = None
    interviewer_names: list[str] = Field(default_factory=list)
    notes: Optional[str] = None


def interview_node(state: WorkflowState) -> dict:
    """Extract interview details from an email and store them.

    Steps:
    1. Extract interview scheduling info via LLM.
    2. Find or create the associated application.
    3. Create an Interview record.
    4. Update application status to INTERVIEWING.
    5. Save to semantic memory.
    """
    current_email = state.get("current_email")
    if not current_email:
        return {"current_node": "interview"}

    logger.info(
        "node.interview.start",
        message_id=current_email.get("message_id"),
    )

    # 1. Extract interview details
    try:
        llm = get_structured_llm(ExtractedInterview)

        user_prompt = EXTRACT_INTERVIEW_USER.format(
            sender=current_email.get("sender", ""),
            subject=current_email.get("subject", ""),
            body=current_email.get("body_text", "")[:3000],
        )

        result: ExtractedInterview = llm.invoke([
            {"role": "system", "content": EXTRACT_INTERVIEW_SYSTEM},
            {"role": "user", "content": user_prompt},
        ])
    except Exception as e:
        logger.error("node.interview.extraction_error", error=str(e))
        result = ExtractedInterview()

    # 2. Find the associated application
    app_repo = ApplicationRepository()
    interview_repo = InterviewRepository()

    application_id = None
    job_info = state.get("job_info")

    if job_info and job_info.get("company"):
        apps = app_repo.get_by_company(job_info["company"])
        if apps:
            application_id = apps[0].id
    
    # If no application found, try to find via email thread
    if not application_id and current_email.get("message_id"):
        existing = app_repo.find_by_email_id(current_email["message_id"])
        if existing:
            application_id = existing.id

    # Create a placeholder application if none found
    if not application_id:
        from career_tracker.models.application import JobApplication
        placeholder = JobApplication(
            company=current_email.get("sender", "Unknown"),
            role="Unknown Role",
            source_email_id=current_email.get("message_id"),
            status=ApplicationStatus.INTERVIEWING,
        )
        saved = app_repo.create(placeholder)
        application_id = saved.id

    # 3. Create interview record
    try:
        interview_type = InterviewType.OTHER
        try:
            interview_type = InterviewType(result.interview_type)
        except (ValueError, KeyError):
            pass

        scheduled = None
        if result.scheduled_at:
            try:
                scheduled = datetime.fromisoformat(result.scheduled_at)
            except (ValueError, TypeError):
                pass

        interview = Interview(
            application_id=application_id,
            interview_type=interview_type,
            scheduled_at=scheduled,
            duration_minutes=result.duration_minutes,
            location=result.location,
            interviewer_names=result.interviewer_names,
            notes=result.notes,
            source_email_id=current_email.get("message_id"),
        )
        interview_repo.create(interview)

        # 4. Update application status
        app_repo.update_status(application_id, ApplicationStatus.INTERVIEWING)

        # 5. Save to semantic memory
        try:
            store = get_memory_store()
            store.save(
                collection=INTERVIEW_INVITATIONS,
                doc_id=interview.id,
                content=f"Interview at {current_email.get('sender', '')}. {result.notes or ''}",
                metadata={
                    "application_id": application_id,
                    "interview_type": interview_type.value,
                    "scheduled_at": result.scheduled_at or "",
                },
            )
        except Exception as e:
            logger.warning("node.interview.memory_error", error=str(e))

        # Log event
        EventRepository().log(
            event_type="interview_scheduled",
            entity_type="interview",
            entity_id=interview.id,
            data={
                "application_id": application_id,
                "type": interview_type.value,
                "scheduled_at": result.scheduled_at,
            },
        )

        interview_info = {
            "id": interview.id,
            "application_id": application_id,
            "interview_type": interview_type.value,
            "scheduled_at": result.scheduled_at,
            "location": result.location,
        }

        # 6. Update email status to PROCESSED
        try:
            from career_tracker.db.database import get_database
            _db = get_database()
            _db.execute_write(
                "UPDATE emails SET status='PROCESSED' WHERE id=?",
                (current_email.get("message_id"),)
            )
        except Exception as _e:
            logger.error("node.interview.email_status_error", error=str(_e))

        logger.info(
            "node.interview.complete",
            interview_id=interview.id,
            type=interview_type.value,
        )

        return {
            "interview_info": interview_info,
            "current_node": "interview",
        }

    except Exception as e:
        logger.error("node.interview.error", error=str(e))
        return {
            "errors": [{
                "node": "interview",
                "error_type": type(e).__name__,
                "message": str(e),
                "retryable": True,
            }],
            "current_node": "interview",
        }
