"""Core services and repository accessors."""

from career_tracker.config import get_settings
from career_tracker.db.database import get_database
from career_tracker.db.repositories.application_repo import ApplicationRepository
from career_tracker.db.repositories.email_repo import EmailRepository
from career_tracker.db.repositories.event_repo import EventRepository

from career_tracker.services.approval_service import (
    _generate_draft_on_demand,
    _get_draft_details_for_bot,
    _rewrite_draft_with_feedback,
    _send_approval_immediately,
    _create_draft_from_linkedin_job,
)
from career_tracker.services.chat_service import handle_general_chat
from career_tracker.services.profile_service import (
    handle_cv_upload,
    handle_profile_upload,
    load_cv_status,
    save_profile,
)
from career_tracker.services.settings_service import check_setup, load_settings, save_settings


def _get_db():
    return get_database()


def _get_app_repo():
    return ApplicationRepository()


def _get_email_repo():
    return EmailRepository()


def _get_event_repo():
    return EventRepository()


def _get_settings():
    return get_settings()


__all__ = [
    '_get_db',
    '_get_app_repo',
    '_get_email_repo',
    '_get_event_repo',
    '_get_settings',
    '_generate_draft_on_demand',
    '_get_draft_details_for_bot',
    '_rewrite_draft_with_feedback',
    '_send_approval_immediately',
    '_create_draft_from_linkedin_job',
    'handle_general_chat',
    'handle_cv_upload',
    'handle_profile_upload',
    'load_cv_status',
    'save_profile',
    'check_setup',
    'load_settings',
    'save_settings'
]
