"""StoreApplicationNode — persists extracted data to SQLite."""

from __future__ import annotations

import structlog

from career_tracker.db.repositories import (
    ApplicationRepository,
    EmailRepository,
    EventRepository,
    RecruiterRepository,
)
from career_tracker.models.application import JobApplication
from career_tracker.models.recruiter import Recruiter
from career_tracker.models.state import WorkflowState

logger = structlog.get_logger(__name__)


def store_application_node(state: WorkflowState) -> dict:
    """Persist extracted job, recruiter, and email data to SQLite.

    Creates or updates:
    - Application record (from job_info)
    - Recruiter record (from recruiter_info, with deduplication)
    - Links email to application and recruiter
    """
    current_email = state.get("current_email")
    job_info = state.get("job_info")
    recruiter_info = state.get("recruiter_info")

    logger.info("node.store_application.start")

    app_repo = ApplicationRepository()
    recruiter_repo = RecruiterRepository()
    email_repo = EmailRepository()
    event_repo = EventRepository()

    recruiter_id = None
    application_id = None

    # 1. Upsert recruiter if info was extracted
    if recruiter_info and recruiter_info.get("email"):
        try:
            recruiter = Recruiter(
                name=recruiter_info.get("name", "Unknown"),
                email=recruiter_info["email"],
                company=recruiter_info.get("company"),
                title=recruiter_info.get("title"),
                linkedin_url=recruiter_info.get("linkedin_url"),
                phone=recruiter_info.get("phone"),
            )
            saved_recruiter = recruiter_repo.upsert_by_email(recruiter)
            recruiter_id = saved_recruiter.id
            logger.info("node.store_application.recruiter_saved", id=recruiter_id)
        except Exception as e:
            logger.error("node.store_application.recruiter_error", error=str(e))

    # 2. Create application if job info was extracted
    if job_info and job_info.get("company", "Unknown") != "Unknown":
        try:
            # Check if an application already exists for this email
            source_email_id = current_email.get("message_id") if current_email else None
            existing = None
            if source_email_id:
                existing = app_repo.find_by_email_id(source_email_id)

            if not existing:
                application = JobApplication(
                    company=job_info.get("company", "Unknown"),
                    role=job_info.get("role", "Unknown"),
                    url=job_info.get("url"),
                    location=job_info.get("location"),
                    salary_range=job_info.get("salary_range"),
                    job_description=job_info.get("job_description"),
                    recruiter_id=recruiter_id,
                    source_email_id=source_email_id,
                )
                saved_app = app_repo.create(application)
                application_id = saved_app.id
                logger.info(
                    "node.store_application.application_created",
                    id=application_id,
                    company=saved_app.company,
                )
            else:
                application_id = existing.id
                logger.info(
                    "node.store_application.application_exists",
                    id=application_id,
                )
        except Exception as e:
            logger.error("node.store_application.application_error", error=str(e))

    # 3. Link email to application and recruiter
    if current_email:
        message_id = current_email.get("message_id")
        if message_id:
            try:
                if application_id:
                    email_repo.link_to_application(message_id, application_id)
                if recruiter_id:
                    email_repo.link_to_recruiter(message_id, recruiter_id)
            except Exception as e:
                logger.error("node.store_application.link_error", error=str(e))

    # 4. Log audit event
    event_repo.log(
        event_type="data_stored",
        entity_type="application" if application_id else "email",
        entity_id=application_id or (current_email.get("message_id") if current_email else "unknown"),
        data={
            "recruiter_id": recruiter_id,
            "application_id": application_id,
            "has_job_info": bool(job_info),
            "has_recruiter_info": bool(recruiter_info),
        },
    )

    logger.info(
        "node.store_application.complete",
        application_id=application_id,
        recruiter_id=recruiter_id,
    )

    return {"current_node": "store_application"}
