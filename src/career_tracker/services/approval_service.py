"""Service for managing the email draft approval queue, generation, and dispatch."""

import json
import traceback
from datetime import datetime
from typing import Dict, Any

from openai import OpenAI

from career_tracker.config import get_settings
from career_tracker.db.database import get_database
from career_tracker.db.repositories.event_repo import EventRepository
from career_tracker.db.repositories.user_profile_repo import UserProfileRepository
from career_tracker.graph.nodes.draft_reply import draft_reply_node
from career_tracker.graph.nodes.extract_job_info import extract_job_info_node
from career_tracker.graph.nodes.extract_recruiter_info import extract_recruiter_info_node
from career_tracker.mcp_servers.gmail_server import send_email
from career_tracker.memory.store import APPROVED_RESPONSES, get_memory_store


def _get_draft_details_for_bot(approval_id: str) -> str:
    """Load draft payload from database and format as a clean markdown card for the bot."""
    try:
        db = get_database()
        rows = db.execute('SELECT id, payload FROM approval_queue WHERE id = ?', (approval_id,))
        if not rows:
            return '*(Draft not found in database)*'
            
        p = json.loads(rows[0]['payload'] or '{}') if isinstance(rows[0]['payload'], str) else rows[0]['payload']
        draft = p.get('draft', {}) if isinstance(p, dict) else {}
        
        to = draft.get('to') or '—'
        subject = draft.get('subject') or '—'
        body = draft.get('body') or ''
        
        reasoning = draft.get('generation_reasoning') or p.get('generation_reasoning')
        if not reasoning or not str(reasoning).strip():
            if 'noreply' in str(to).lower() or 'donotreply' in str(to).lower():
                reasoning = 'The recipient is an automated no-reply address.'
            else:
                reasoning = 'The AI determined that a response is not necessary or appropriate for this specific email.'
                
        display_body = body.strip() if body.strip() else f'*(No email body generated. Reason: {reasoning})*'
        suggested_resume = draft.get('suggested_resume') or p.get('suggested_resume')
        
        if suggested_resume:
            prompt_footer = "*Would you like to **approve** this (type 'yes' - 📎 CV will be attached automatically), **edit** it (type feedback), or **skip** (type 'skip')?*"
        else:
            prompt_footer = "*Would you like to **approve** this (type 'yes' or 'yes with cv' to attach CV), **edit** it (type feedback), or **skip** (type 'skip')?*"
            
        return f'**Draft ID:** `{approval_id[:8]}`\n**To:** {to}\n**Subject:** {subject}\n\n**Email Body:**\n```\n{display_body}\n```\n\n{prompt_footer}'
    except Exception as e:
        return f'*(Error loading draft details: {e})*'


def _generate_draft_on_demand(approval_id: str) -> str:
    """Generate draft reply on-demand for a pending approval queue entry."""
    try:
        db = get_database()
        rows = db.execute('SELECT id, payload, related_email_id FROM approval_queue WHERE id = ?', (approval_id,))
        if not rows:
            return '*(Draft not found in database)*'
            
        payload = json.loads(rows[0]['payload'] or '{}') if isinstance(rows[0]['payload'], str) else rows[0]['payload']
        related_email_id = rows[0]['related_email_id']
        
        if payload.get('draft'):
            return _get_draft_details_for_bot(approval_id)
            
        classification = payload.get('classification') or {}
        category = classification.get('category', 'APPLY_JOB')
        
        email_rows = db.execute('SELECT * FROM emails WHERE id = ?', (related_email_id,))
        if not email_rows:
            return '*(Associated email not found in database)*'
            
        r = email_rows[0]
        try:
            labels = json.loads(r['labels']) if r.get('labels') else []
        except json.JSONDecodeError:
            labels = []
            
        email_dict = {
            'message_id': r['id'],
            'thread_id': r.get('thread_id', ''),
            'subject': r.get('subject', ''),
            'sender': r.get('sender', ''),
            'recipient': r.get('recipient', ''),
            'date': r.get('date', ''),
            'body_text': r.get('body_text', ''),
            'body_html': r.get('body_html'),
            'labels': labels,
            'is_read': bool(r.get('is_read'))
        }
        
        state: Dict[str, Any] = {
            'current_email': email_dict,
            'emails': [email_dict],
            'classification': classification,
            'job_info': None,
            'recruiter_info': None,
            'draft_reply': None,
            'suggested_resume': None,
            'suggested_cover_letter': None,
            'pending_approvals': [],
            'processed_email_ids': [],
            'errors': [],
            'fetch_stats': None,
            'current_node': 'start',
            'should_continue': True
        }
        
        if category == 'APPLY_JOB':
            try:
                res = extract_job_info_node(state)
                state.update(res)
            except Exception as e:
                print(f'Error in extract_job_info_node: {e}')
        elif category == 'REPLY_RECRUITER':
            try:
                res = extract_recruiter_info_node(state)
                state.update(res)
            except Exception as e:
                print(f'Error in extract_recruiter_info_node: {e}')
                
        res = draft_reply_node(state)
        state.update(res)
        draft = state.get('draft_reply')
        
        if not draft:
            return '*(Agent failed to generate draft professional reply)*'
            
        payload['draft'] = draft
        payload['job_info'] = state.get('job_info')
        payload['recruiter_info'] = state.get('recruiter_info')
        payload['suggested_resume'] = state.get('suggested_resume')
        payload['suggested_cover_letter'] = state.get('suggested_cover_letter')
        
        db.execute_write('UPDATE approval_queue SET payload = ? WHERE id = ?', (json.dumps(payload), approval_id))
        
        to = draft.get('to', '—')
        subject = draft.get('subject', '—')
        body = draft.get('body', '—')
        suggested_resume = draft.get('suggested_resume') or payload.get('suggested_resume')
        
        if suggested_resume:
            prompt_footer = "*Would you like to **approve** this (type 'yes' - 📎 CV will be attached automatically), **edit** it (type feedback), or **skip** (type 'skip')?*"
        else:
            prompt_footer = "*Would you like to **approve** this (type 'yes' or 'yes with cv' to attach CV), **edit** it (type feedback), or **skip** (type 'skip')?*"
            
        return f'**Draft ID:** `{approval_id[:8]}`\n**To:** {to}\n**Subject:** {subject}\n\n**Email Body:**\n```\n{body}\n```\n\n{prompt_footer}'
    except Exception as e:
        return f'*(Error generating draft reply: {e}\n{traceback.format_exc()})*'


def _send_approval_immediately(approval_id: str, attach_cv: bool = False) -> str:
    """Immediately dispatch the approved draft via Gmail API, record memory and events."""
    try:
        db = get_database()
        rows = db.execute('SELECT id, payload, action_type FROM approval_queue WHERE id = ?', (approval_id,))
        if not rows:
            return 'Error: Draft not found.'
            
        full_id = rows[0]['id']
        payload = rows[0]['payload']
        p = json.loads(payload or '{}') if isinstance(payload, str) else payload
        draft = p.get('draft', {}) if isinstance(p, dict) else {}
        
        if not draft:
            return 'Error: Draft payload is empty.'
            
        to = draft.get('to')
        subject = draft.get('subject')
        body = draft.get('body')
        reply_to = draft.get('reply_to_message_id')
        
        if not to or not subject or not body:
            return 'Error: Draft is missing required fields (To, Subject, or Body).'
            
        attachment_path = None
        if attach_cv:
            settings = get_settings()
            resumes_dir = settings.resolve_path(settings.resumes_dir)
            cv_path = resumes_dir / 'my_cv.pdf'
            if cv_path.exists():
                attachment_path = str(cv_path)
                
        sender_email = p.get('receiver_email') or p.get('email_recipient')
        
        send_result = send_email(
            to=to, 
            subject=subject, 
            body=body, 
            reply_to_message_id=reply_to, 
            attachment_path=attachment_path, 
            sender_email=sender_email
        )
        
        try:
            store = get_memory_store()
            store.save(
                collection=APPROVED_RESPONSES, 
                doc_id=send_result.get('message_id', reply_to or ''), 
                content=body, 
                metadata={
                    'company': p.get('job_info', {}).get('company', '') if isinstance(p, dict) else '', 
                    'role': p.get('job_info', {}).get('role', '') if isinstance(p, dict) else '', 
                    'to': to, 
                    'subject': subject, 
                    'outcome': 'sent'
                }
            )
        except Exception:
            pass
            
        EventRepository().log(
            event_type='email_sent', 
            entity_type='email', 
            entity_id=send_result.get('message_id', ''), 
            data={'to': to, 'subject': subject, 'reply_to': reply_to, 'via': 'interactive_chatbot'}
        )
        
        now = datetime.utcnow().isoformat()
        db.execute_write(
            "UPDATE approval_queue SET status='APPROVED', reviewed_at=?, reviewer_notes='Sent immediately via interactive chatbot' WHERE id=?", 
            (now, full_id)
        )
        db.execute_write(
            "UPDATE emails SET status='APPROVED' WHERE id = (SELECT related_email_id FROM approval_queue WHERE id = ?)", 
            (full_id,)
        )
        
        return f'Email successfully sent to `{to}`!'
    except Exception as e:
        return f'Failed to send email immediately: {e}'


def _rewrite_draft_with_feedback(approval_id: str, feedback: str) -> str:
    """Call LLM to update the draft body based on user feedback, updating database payload."""
    try:
        db = get_database()
        rows = db.execute('SELECT id, payload FROM approval_queue WHERE id = ?', (approval_id,))
        if not rows:
            return 'Error: Draft not found.'
            
        payload = rows[0]['payload']
        p = json.loads(payload or '{}') if isinstance(payload, str) else payload
        draft = p.get('draft', {}) if isinstance(p, dict) else {}
        
        to = draft.get('to', '—')
        subject = draft.get('subject', '—')
        body = draft.get('body', '—')
        original_email_body = p.get('email_body', '')
        
        user_profile_str = ''
        try:
            profile = UserProfileRepository().get_default()
            if profile:
                user_profile_str = json.dumps(profile, indent=2, default=str)
        except Exception:
            pass
            
        settings = get_settings()
        system_prompt = (
            "You are an expert career assistant. The user wants to edit an email drafted to a recruiter/employer, "
            "or generate one from scratch if the current draft is empty.\n"
            "Rewrite or generate the email body based strictly on their feedback. Maintain a highly professional, polite, and engaging tone.\n"
            "If you need to sign off the email, USE the user's actual name and contact details from the user profile. "
            "Do NOT use placeholders like [Your Name] or [Your Phone Number].\n\n"
            f"USER PROFILE (Use this for your signature/contact details):\n{user_profile_str or 'No profile available. Try to infer name from context or leave minimal.'}\n\n"
            f"ORIGINAL RECEIVED EMAIL:\n{original_email_body}\n\n"
            f"CURRENT DRAFT DETAILS:\nTo: {to}\nSubject: {subject}\n\n"
            f"CURRENT DRAFT BODY:\n{body}\n\n"
            f"USER FEEDBACK:\n{feedback}\n\n"
            "Output ONLY the final email body. Do not include any introductory or concluding text, no subject line, "
            "no markdown backticks around the text unless it is part of the email body itself.\n"
        )
        
        client = OpenAI(
            api_key=settings.openai_api_key, 
            base_url=settings.openai_api_base or 'https://api.openai.com/v1'
        )
        
        resp = client.chat.completions.create(
            model=settings.llm_model or 'gpt-4o-mini', 
            messages=[
                {'role': 'system', 'content': system_prompt}, 
                {'role': 'user', 'content': feedback}
            ], 
            max_tokens=600, 
            temperature=0.3
        )
        
        new_body = resp.choices[0].message.content or ''
        new_body = new_body.strip()
        
        if new_body.startswith('```') and new_body.endswith('```'):
            lines = new_body.splitlines()
            if len(lines) > 2:
                new_body = '\n'.join(lines[1:-1]).strip()
                
        draft['body'] = new_body
        p['draft'] = draft
        db.execute_write('UPDATE approval_queue SET payload=? WHERE id=?', (json.dumps(p), approval_id))
        
        suggested_resume = draft.get('suggested_resume') or p.get('suggested_resume')
        if suggested_resume:
            prompt_footer = "*Type 'yes' to approve (📎 CV will be attached automatically).*"
        else:
            prompt_footer = "*Type 'yes' to approve (or 'yes with cv' to attach CV).*"
            
        return f'**Draft ID:** `{approval_id[:8]}`\n**To:** {to}\n**Subject:** {subject}\n\n**Email Body:**\n```\n{new_body}\n```\n\n{prompt_footer}'
    except Exception as e:
        return f'*(Failed to rewrite draft: {e})*\n\n**Email Body:**\n```\n{body}\n```'


def _create_draft_from_linkedin_job(job_id: str) -> Dict[str, Any]:
    """Generate a cold application email draft for a LinkedIn job opportunity and insert it into the approval queue."""
    import uuid
    db = get_database()
    
    # 1. Load the job details
    rows = db.execute("SELECT * FROM intel_posts WHERE id = ?", (job_id,))
    if not rows:
        raise ValueError(f"Job posting with ID {job_id} not found.")
        
    job = rows[0]
    company = job.get("author") or "Unknown Company"
    text_content = job.get("text_content") or ""
    job_url = job.get("url") or ""
    
    # 2. Try to get job title from text_content
    # Usually it starts with "Job Title: "
    job_title = "Software Engineer"
    for line in text_content.splitlines():
        if "job title:" in line.lower():
            job_title = line.split(":", 1)[1].strip()
            break
            
    # 3. Load user profile
    user_profile_str = ''
    user_name = "Candidate"
    try:
        profile = UserProfileRepository().get_default()
        if profile:
            user_profile_str = json.dumps(profile, indent=2, default=str)
            user_name = profile.get("name") or "Candidate"
    except Exception:
        pass
        
    # 4. Call OpenAI to generate email subject and body
    settings = get_settings()
    system_prompt = (
        "You are an expert career assistant. The user wants to generate a professional application/referral request email "
        "for a job opportunity they found on LinkedIn.\n"
        "Create a highly tailored, professional, and compelling email body and subject line. "
        "Highlight the candidate's matched skills and express enthusiasm for the role.\n"
        "Sign off with the candidate's actual name and contact details from their profile. "
        "Do NOT use placeholders like [Your Name].\n\n"
        f"CANDIDATE PROFILE:\n{user_profile_str}\n\n"
        f"JOB DETAILS:\nCompany: {company}\n{text_content}\n"
    )
    
    client = OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_api_base or 'https://api.openai.com/v1'
    )
    
    # Request JSON output structure
    user_prompt = "Generate the email. You MUST return a JSON object with 'subject' and 'body' keys."
    
    # Use json_mode or simple parsing
    resp = client.chat.completions.create(
        model=settings.llm_model or 'gpt-4o-mini',
        response_format={"type": "json_object"},
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ],
        max_tokens=800,
        temperature=0.3
    )
    
    result_json = json.loads(resp.choices[0].message.content or '{}')
    subject = result_json.get("subject") or f"Application for {job_title} role at {company}"
    body = result_json.get("body") or ""
    
    # Cleanup markdown block backticks if LLM added them inside JSON string
    if body.startswith('```') and body.endswith('```'):
        lines = body.splitlines()
        if len(lines) > 2:
            body = '\n'.join(lines[1:-1]).strip()
            
    import os
    receiver_email = os.getenv('GMAIL_EMAIL', '')
    if not receiver_email:
        try:
            profile = UserProfileRepository().get_default()
            if profile:
                receiver_email = profile.get("email") or ""
        except Exception:
            pass

    # 5. Insert into approval queue
    approval_id = f"linkedin_app_{uuid.uuid4().hex[:12]}"
    
    payload = {
        "draft": {
            "to": f"jobs@{company.lower().replace(' ', '').replace(',', '')}.com",
            "subject": subject,
            "body": body,
            "suggested_resume": "Default Resume"
        },
        "job_title": job_title,
        "company_name": company,
        "apply_url": job_url,
        "suggested_resume": "Default Resume",
        "receiver_email": receiver_email
    }
    
    db.execute_write(
        """INSERT INTO approval_queue 
            (id, action_type, payload, status, created_at) 
           VALUES (?, ?, ?, ?, ?)""",
        (
            approval_id,
            "sent_mail",
            json.dumps(payload, default=str),
            "PENDING_APPROVAL",
            datetime.utcnow().isoformat()
        )
    )
    
    EventRepository().log(
        event_type="approval_queued",
        entity_type="approval",
        entity_id=approval_id,
        data={"action_type": "sent_mail", "source": "linkedin_job_conversion", "job_id": job_id},
    )
    
    return {"status": "success", "approval_id": approval_id}
