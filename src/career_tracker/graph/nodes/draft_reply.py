"""DraftReplyNode — generates a professional reply draft using LLM.

Uses semantic memory to find similar past responses for context-aware
drafting. Suggests resume/cover letter attachments.
"""

from __future__ import annotations

import json
from typing import Optional

import structlog
from pydantic import BaseModel, Field

from career_tracker.llm.client import get_structured_llm
from career_tracker.llm.prompts import DRAFT_REPLY_SYSTEM, DRAFT_REPLY_USER
from career_tracker.memory.store import APPROVED_RESPONSES, get_memory_store
from career_tracker.mcp_servers.filesystem_server import list_cover_letters, list_resumes
from career_tracker.models.state import WorkflowState

logger = structlog.get_logger(__name__)


class GeneratedDraft(BaseModel):
    """Schema for LLM-generated reply draft."""

    to: str = Field(description="Recipient email")
    subject: str = Field(description="Reply subject line")
    body: str = Field(description="Reply body text")
    generation_reasoning: str = Field(default="", description="Why this draft was generated")
    suggested_resume: Optional[str] = Field(
        default=None, description="Resume filename to attach"
    )
    suggested_cover_letter: Optional[str] = Field(
        default=None, description="Cover letter filename to attach"
    )


def draft_reply_node(state: WorkflowState) -> dict:
    """Generate a professional reply draft for the current email.

    Steps:
    1. Search semantic memory for similar past approved responses.
    2. List available resumes and cover letters.
    3. Send context + email to LLM for draft generation.
    """
    current_email = state.get("current_email")
    if not current_email:
        return {"current_node": "draft_reply"}

    logger.info(
        "node.draft_reply.start",
        message_id=current_email.get("message_id"),
    )

    # 1. Search for similar past responses
    similar_responses = ""
    try:
        store = get_memory_store()
        results = store.search(
            collection=APPROVED_RESPONSES,
            query=f"{current_email.get('subject', '')} {current_email.get('body_text', '')[:500]}",
            n_results=3,
        )
        if results:
            similar_responses = "\n\n---\n\n".join(
                f"[Past response for {r.get('metadata', {}).get('company', 'unknown')} - "
                f"{r.get('metadata', {}).get('role', 'unknown')}]\n{r['content']}"
                for r in results
            )
    except Exception as e:
        logger.warning("node.draft_reply.memory_search_failed", error=str(e))

    # 2. Search for User Preferences
    user_preferences = "No specific instructions."
    try:
        from career_tracker.memory.store import USER_PREFERENCES
        pref_results = store.search(
            collection=USER_PREFERENCES,
            query="all instructions",
            n_results=10,
        )
        if pref_results:
            user_preferences = "\n".join(f"- {r['content']}" for r in pref_results)
    except Exception as e:
        logger.warning("node.draft_reply.preference_search_failed", error=str(e))

    # 3. List available documents
    try:
        resumes = list_resumes()
        available_resumes = "\n".join(f"- {r['filename']}" for r in resumes) or "No resumes available"
    except Exception:
        available_resumes = "Unable to list resumes"

    try:
        cover_letters = list_cover_letters()
        available_cls = "\n".join(f"- {cl['filename']}" for cl in cover_letters) or "No cover letters available"
    except Exception:
        available_cls = "Unable to list cover letters"

    # 3. Get user profile for context
    user_profile = ""
    try:
        from career_tracker.db.repositories.user_profile_repo import UserProfileRepository
        profile = UserProfileRepository().get_default()
        if profile:
            user_profile = json.dumps(profile, indent=2, default=str)
    except Exception:
        pass

    # 4. Fetch thread history
    thread_history_str = "None"
    try:
        from career_tracker.db.repositories.email_repo import EmailRepository
        thread_id = current_email.get("thread_id")
        if thread_id:
            repo = EmailRepository()
            thread_emails = repo.get_by_thread(thread_id)
            past_emails = [e for e in thread_emails if e["id"] != current_email.get("message_id")]
            if past_emails:
                history_lines = []
                for pe in past_emails:
                    history_lines.append(f"--- On {pe.get('date')} {pe.get('sender')} wrote: ---\n{pe.get('body_text', '')[:500]}")
                thread_history_str = "\n\n".join(history_lines)
    except Exception as e:
        logger.warning("node.draft_reply.thread_fetch_failed", error=str(e))

    # 5. Generate draft
    try:
        llm = get_structured_llm(GeneratedDraft)

        job_info = state.get("job_info", {}) or {}
        job_info_str = json.dumps(job_info, indent=2, default=str) if job_info else "Not extracted"

        system_prompt = DRAFT_REPLY_SYSTEM.format(
            user_preferences=user_preferences,
            similar_responses=similar_responses or "No similar past responses found.",
            user_profile=user_profile or "No user profile configured.",
        )

        user_prompt = DRAFT_REPLY_USER.format(
            thread_history=thread_history_str,
            sender=current_email.get("sender", ""),
            subject=current_email.get("subject", ""),
            date=current_email.get("date", ""),
            body=current_email.get("body_text", "")[:1500],
            job_info=job_info_str,
            available_resumes=available_resumes,
            available_cover_letters=available_cls,
        )

        result: GeneratedDraft = llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])

        draft_dict = result.model_dump(mode="json")
        draft_dict["reply_to_message_id"] = current_email.get("message_id")

        logger.info(
            "node.draft_reply.complete",
            to=result.to,
            subject=result.subject[:50],
        )

        return {
            "draft_reply": draft_dict,
            "suggested_resume": result.suggested_resume,
            "suggested_cover_letter": result.suggested_cover_letter,
            "current_node": "draft_reply",
        }

    except Exception as e:
        logger.error("node.draft_reply.error", error=str(e))
        return {
            "errors": [{
                "node": "draft_reply",
                "error_type": type(e).__name__,
                "message": str(e),
                "retryable": True,
            }],
            "current_node": "draft_reply",
        }
