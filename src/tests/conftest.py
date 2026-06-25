"""Shared test fixtures for Career Tracker tests."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path: Path):
    """Redirect all data directories to a temp path for test isolation.

    This ensures tests never touch real user data or credentials.
    """
    env_overrides = {
        "DB_PATH": str(tmp_path / "test.db"),
        "CHROMA_PATH": str(tmp_path / "chroma"),
        "RESUMES_DIR": str(tmp_path / "resumes"),
        "COVER_LETTERS_DIR": str(tmp_path / "cover_letters"),
        "ATTACHMENTS_DIR": str(tmp_path / "attachments"),
        "LOGS_DIR": str(tmp_path / "logs"),
        "GMAIL_CREDENTIALS_PATH": str(tmp_path / "credentials.json"),
        "GMAIL_TOKEN_PATH": str(tmp_path / "token.json"),
        "OPENAI_API_KEY": "test-key-not-real",
        "OPENAI_API_BASE": "http://localhost:11434/v1",
        "LLM_MODEL": "test-model",
    }

    with patch.dict(os.environ, env_overrides, clear=False):
        # Clear cached settings singleton
        from career_tracker.config import get_settings
        get_settings.cache_clear()

        # Clear cached database singleton
        import career_tracker.db.database as db_mod
        db_mod._db_manager = None

        # Clear cached memory store singleton
        import career_tracker.memory.store as mem_mod
        mem_mod._memory_store = None

        yield tmp_path

        # Clean up singletons after test
        get_settings.cache_clear()
        db_mod._db_manager = None
        mem_mod._memory_store = None


@pytest.fixture
def sample_email() -> dict:
    """Return a sample email dict matching Gmail MCP server output format."""
    return {
        "message_id": "msg_test_001",
        "thread_id": "thread_test_001",
        "subject": "Exciting SWE Opportunity at TechCorp",
        "sender": "Jane Doe <jane.doe@techcorp.com>",
        "recipient": "user@example.com",
        "date": "2025-01-15T10:30:00Z",
        "body_text": (
            "Hi there,\n\n"
            "I'm Jane Doe, a Senior Technical Recruiter at TechCorp. "
            "I came across your profile and I'm impressed by your experience. "
            "We have an open Senior Software Engineer position in our "
            "San Francisco office (hybrid, 3 days/week).\n\n"
            "The salary range is $180k-$220k + equity.\n\n"
            "Would you be interested in learning more? "
            "Happy to set up a quick call.\n\n"
            "Best,\nJane Doe\nSenior Technical Recruiter\n"
            "TechCorp | jane.doe@techcorp.com\n"
            "LinkedIn: linkedin.com/in/janedoe"
        ),
        "body_html": None,
        "labels": ["INBOX", "UNREAD"],
        "attachments": [],
        "is_read": False,
    }


@pytest.fixture
def sample_rejection_email() -> dict:
    """Return a sample rejection email."""
    return {
        "message_id": "msg_test_002",
        "thread_id": "thread_test_002",
        "subject": "Update on your application to TechCorp",
        "sender": "noreply@techcorp.com",
        "recipient": "user@example.com",
        "date": "2025-02-01T14:00:00Z",
        "body_text": (
            "Dear Applicant,\n\n"
            "Thank you for your interest in TechCorp and for taking the time "
            "to apply for the Senior Software Engineer position.\n\n"
            "After careful consideration, we have decided to move forward "
            "with other candidates whose qualifications more closely align "
            "with our current needs.\n\n"
            "We encourage you to apply for future openings.\n\n"
            "Best regards,\nTechCorp Recruiting Team"
        ),
        "body_html": None,
        "labels": ["INBOX", "UNREAD"],
        "attachments": [],
        "is_read": False,
    }


@pytest.fixture
def sample_interview_email() -> dict:
    """Return a sample interview scheduling email."""
    return {
        "message_id": "msg_test_003",
        "thread_id": "thread_test_003",
        "subject": "Interview Invitation - Senior SWE @ TechCorp",
        "sender": "scheduling@techcorp.com",
        "recipient": "user@example.com",
        "date": "2025-01-20T09:00:00Z",
        "body_text": (
            "Hi,\n\n"
            "Congratulations! We'd like to invite you for a technical interview "
            "for the Senior Software Engineer position at TechCorp.\n\n"
            "Details:\n"
            "- Date: January 25, 2025 at 2:00 PM PST\n"
            "- Duration: 60 minutes\n"
            "- Format: Virtual (Zoom)\n"
            "- Link: https://zoom.us/j/123456789\n"
            "- Interviewer: John Smith, Engineering Manager\n\n"
            "Please confirm your availability.\n\n"
            "Best,\nTechCorp Scheduling"
        ),
        "body_html": None,
        "labels": ["INBOX", "UNREAD"],
        "attachments": [],
        "is_read": False,
    }


@pytest.fixture
def initialized_db(tmp_path: Path):
    """Return a DatabaseManager connected to an initialized test database."""
    from career_tracker.db.database import DatabaseManager

    db = DatabaseManager(db_path=tmp_path / "test.db")
    db.initialize()
    return db
