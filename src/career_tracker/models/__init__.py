"""Pydantic data models for the Career Tracker application."""

from career_tracker.models.email import (
    AttachmentInfo,
    DraftReply,
    EmailCategory,
    EmailClassification,
    EmailMessage,
)
from career_tracker.models.application import ApplicationStatus, JobApplication
from career_tracker.models.recruiter import Recruiter
from career_tracker.models.interview import Interview, InterviewType
from career_tracker.models.approval import ApprovalAction, ApprovalStatus
from career_tracker.models.state import WorkflowError, WorkflowState

__all__ = [
    "AttachmentInfo",
    "DraftReply",
    "EmailCategory",
    "EmailClassification",
    "EmailMessage",
    "ApplicationStatus",
    "JobApplication",
    "Recruiter",
    "Interview",
    "InterviewType",
    "ApprovalAction",
    "ApprovalStatus",
    "WorkflowError",
    "WorkflowState",
]
