"""ClassifyEmailNode — classifies emails using LLM structured output.

Uses the classification prompt to categorize emails into one of six
categories with confidence scoring and reasoning.
"""

from __future__ import annotations

from datetime import datetime

import structlog

from career_tracker.config import get_settings
from career_tracker.llm.client import get_structured_llm
from career_tracker.llm.prompts import CLASSIFY_EMAIL_SYSTEM, CLASSIFY_EMAIL_USER
from career_tracker.models.email import EmailCategory, EmailClassification
from career_tracker.models.state import WorkflowState
from career_tracker.db.repositories.email_repo import EmailRepository
from career_tracker.db.repositories.event_repo import EventRepository

logger = structlog.get_logger(__name__)


def classify_email_node(state: WorkflowState) -> dict:
    """Classify the current email using LLM structured output.

    Returns the classification result and stores it in the email record.
    If confidence is below the threshold, forces HUMAN_REVIEW.
    """
    current_email = state.get("current_email")
    if not current_email:
        logger.warning("node.classify_email.no_current_email")
        return {"current_node": "classify_email", "should_continue": False}

    logger.info(
        "node.classify_email.start",
        message_id=current_email.get("message_id"),
        subject=current_email.get("subject", "")[:50],
    )

    settings = get_settings()

    sender_lower = current_email.get("sender", "").lower()
    if "noreply" in sender_lower or "no-reply" in sender_lower:
        logger.info("node.classify_email.auto_ignore_noreply", sender=current_email.get("sender"))
        result = EmailClassification(
            category=EmailCategory.IGNORE,
            confidence=1.0,
            reasoning="Automated sender (no-reply/noreply address). Auto-ignored to prevent bounce replies."
        )
        try:
            email_repo = EmailRepository()
            email_repo.update_classification(current_email["message_id"], classification=result)
            EventRepository().log(
                event_type="email_classified",
                entity_type="email",
                entity_id=current_email["message_id"],
                data={
                    "category": result.category.value,
                    "confidence": result.confidence,
                    "reasoning": result.reasoning,
                    "subject": current_email.get("subject", ""),
                },
            )
        except Exception as e:
            logger.error("node.classify_email.db_error", error=str(e))
            
        return {
            "classification": {
                "category": result.category.value,
                "confidence": result.confidence,
                "reasoning": result.reasoning,
            },
            "current_node": "classify_email",
        }

    try:
        llm = get_structured_llm(EmailClassification)
        
        thread_id = current_email.get("thread_id")
        thread_history_str = "None"
        if thread_id:
            try:
                repo = EmailRepository()
                thread_emails = repo.get_by_thread(thread_id)
                past_emails = [e for e in thread_emails if e["id"] != current_email.get("message_id")]
                if past_emails:
                    history_lines = []
                    for pe in past_emails:
                        history_lines.append(f"--- On {pe.get('date')} {pe.get('sender')} wrote: ---\n{pe.get('body_text', '')[:500]}")
                    thread_history_str = "\n\n".join(history_lines)
            except Exception as e:
                logger.warning("node.classify_email.thread_fetch_failed", error=str(e))

        user_prompt = CLASSIFY_EMAIL_USER.format(
            thread_history=thread_history_str,
            sender=current_email.get("sender", ""),
            subject=current_email.get("subject", ""),
            date=current_email.get("date", ""),
            body=current_email.get("body_text", "")[:1500],  # Truncate long emails to save tokens
        )

        result: EmailClassification = llm.invoke([
            {"role": "system", "content": CLASSIFY_EMAIL_SYSTEM},
            {"role": "user", "content": user_prompt},
        ])

        # Force HUMAN_REVIEW if confidence is below threshold
        if result.confidence < settings.classification_confidence_threshold:
            logger.info(
                "node.classify_email.low_confidence",
                confidence=result.confidence,
                original_category=result.category.value,
            )
            result = EmailClassification(
                category=EmailCategory.HUMAN_REVIEW,
                confidence=result.confidence,
                reasoning=f"Low confidence ({result.confidence:.2f}). "
                          f"Original classification: {result.category.value}. "
                          f"{result.reasoning}",
            )

    except Exception as e:
        logger.error(
            "node.classify_email.llm_error",
            error=str(e),
            error_type=type(e).__name__,
        )
        # On LLM failure, default to HUMAN_REVIEW
        result = EmailClassification(
            category=EmailCategory.HUMAN_REVIEW,
            confidence=0.0,
            reasoning=f"LLM classification failed: {type(e).__name__}: {str(e)}",
        )

    # Store classification in database
    try:
        email_repo = EmailRepository()
        email_repo.update_classification(current_email["message_id"], classification=result)

        # Log audit event
        EventRepository().log(
            event_type="email_classified",
            entity_type="email",
            entity_id=current_email["message_id"],
            data={
                "category": result.category.value,
                "confidence": result.confidence,
                "reasoning": result.reasoning,
                "subject": current_email.get("subject", ""),
            },
        )
        
        # --- NEW: Lazy Attachment Extraction ---
        # If the LLM has deemed this email relevant, extract its attachments now
        relevant_categories = [
            EmailCategory.APPLY_JOB.value, 
            EmailCategory.REPLY_RECRUITER.value, 
            EmailCategory.INTERVIEW.value, 
            EmailCategory.HUMAN_REVIEW.value
        ]
        
        if result.category.value in relevant_categories and current_email.get("attachments"):
            from career_tracker.mcp_servers.gmail_server import extract_email_attachment_text
            from career_tracker.db.database import get_database
            
            extracted_texts = []
            for att in current_email["attachments"]:
                mime = att.get("mime_type", "")
                if mime in ["application/pdf", "text/plain", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
                    logger.info("node.classify_email.extracting_attachment", attachment_id=att.get("attachment_id"))
                    text = extract_email_attachment_text(
                        message_id=current_email["message_id"],
                        attachment_id=att["attachment_id"],
                        mime_type=mime,
                        receiver_email=current_email.get("recipient")
                    )
                    if text and not text.startswith("[Failed"):
                        extracted_texts.append(f"--- Attachment: {att.get('filename')} ---\n{text}")
            
            if extracted_texts:
                final_extracted_text = "\n\n".join(extracted_texts)
                db = get_database()
                db.execute_write(
                    "UPDATE emails SET attachment_extracted_text = ? WHERE id = ?",
                    (final_extracted_text, current_email["message_id"])
                )
                current_email["attachment_extracted_text"] = final_extracted_text
                logger.info("node.classify_email.attachment_extracted_success", length=len(final_extracted_text))

        # --- NEW: Zero-Token Skill Matching ---
        if result.category.value in relevant_categories:
            from career_tracker.db.repositories.user_profile_repo import UserProfileRepository
            import re
            import json
            
            try:
                repo = UserProfileRepository()
                profile = repo.get_default()
                if profile and profile.get("skills"):
                    user_skills = profile["skills"]
                    if isinstance(user_skills, str):
                        user_skills = json.loads(user_skills)
                        
                    # Combine body and attachment text
                    full_text = (current_email.get("subject", "") + "\n" + 
                               current_email.get("body_text", "") + "\n" + 
                               current_email.get("attachment_extracted_text", "")).lower()
                               
                    matched = []
                    for skill in user_skills:
                        if not skill.strip():
                            continue
                        # Use simple word boundary regex
                        pattern = r'\b' + re.escape(skill.lower()) + r'\b'
                        if re.search(pattern, full_text):
                            matched.append(skill)
                            
                    if matched:
                        from career_tracker.db.database import get_database
                        db = get_database()
                        db.execute_write(
                            "UPDATE emails SET matched_skills = ? WHERE id = ?",
                            (json.dumps(matched), current_email["message_id"])
                        )
                        current_email["matched_skills"] = matched
                        logger.info("node.classify_email.skills_matched", count=len(matched))
            except Exception as se:
                logger.warning("node.classify_email.skill_match_error", error=str(se))

    except Exception as e:
        logger.error("node.classify_email.db_error", error=str(e))

    classification_dict = {
        "category": result.category.value,
        "confidence": result.confidence,
        "reasoning": result.reasoning,
    }

    logger.info(
        "node.classify_email.complete",
        category=result.category.value,
        confidence=result.confidence,
    )

    return {
        "classification": classification_dict,
        "current_node": "classify_email",
    }
