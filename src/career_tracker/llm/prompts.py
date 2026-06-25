"""Prompt templates for LLM-powered workflow nodes.

All prompts use structured output constraints to ensure reliable JSON parsing.
Templates are designed to work with any OpenAI-compatible model.
"""

from __future__ import annotations

# ── Email Classification ─────────────────────────────────────────────────────

CLASSIFY_EMAIL_SYSTEM = """\
You are an AI assistant that classifies emails related to job searching and recruitment.

Analyze the email below and classify it into exactly ONE of these categories:

- **APPLY_JOB**: Job posting, job opportunity, or invitation to apply for a role.
- **REPLY_RECRUITER**: A recruiter reaching out about a potential opportunity, requesting a conversation, or following up.
- **INTERVIEW**: Interview scheduling, confirmation, rescheduling, or interview-related logistics.
- **REJECTION**: Application rejection, position filled, or "moving forward with other candidates."
- **IGNORE**: Newsletters, marketing, spam, unrelated automated emails, or anything not job-related.
- **HUMAN_REVIEW**: Ambiguous emails that don't clearly fit any category, or emails requiring nuanced judgment.

Rules:
1. If the email mentions a specific job title and asks the recipient to apply → APPLY_JOB.
2. If a recruiter is introducing themselves and asking about interest → REPLY_RECRUITER.
3. If the email contains scheduling details (date, time, video link) for an interview → INTERVIEW.
4. If the language indicates the candidate is not moving forward → REJECTION.
5. If confidence is below 0.6, classify as HUMAN_REVIEW.
6. Generic job board alerts (Indeed, LinkedIn digest) → IGNORE.

Additionally, evaluate if the email is suspicious or spam:
- Set `is_suspicious=true` if it looks like a phishing attempt, scam, or contains suspicious links or sender details.

Return your analysis as structured JSON with:
- category: The classification category
- confidence: A float between 0.0 and 1.0 indicating how confident you are
- reasoning: A brief explanation of why you chose this category
- is_suspicious: A boolean indicating if the email is suspicious or spam\
"""

CLASSIFY_EMAIL_USER = """\
Classify the following email:

**Previous Thread Context:**
{thread_history}

**Current Email:**
**From:** {sender}
**Subject:** {subject}
**Date:** {date}

**Body:**
{body}\
"""


# ── Job Information Extraction ────────────────────────────────────────────────

EXTRACT_JOB_INFO_SYSTEM = """\
You are an AI assistant that extracts structured job information from emails.

Extract the following fields from the email. If a field is not present or cannot
be determined, return null for that field.

Fields to extract:
- **company**: The hiring company name (not the recruiting agency).
- **role**: The exact job title or role name.
- **url**: Any link to a job posting or application page.
- **location**: Work location (city, state, remote, hybrid).
- **salary_range**: Any mentioned compensation range.
- **job_description**: A brief summary of the role if described in the email.

Return the extracted data as structured JSON.\
"""

EXTRACT_JOB_INFO_USER = """\
Extract job information from this email:

**From:** {sender}
**Subject:** {subject}

**Body:**
{body}\
"""


# ── Recruiter Information Extraction ──────────────────────────────────────────

EXTRACT_RECRUITER_INFO_SYSTEM = """\
You are an AI assistant that extracts recruiter contact information from emails.

Extract the following fields. If a field is not present, return null.

Fields to extract:
- **name**: The recruiter's full name.
- **email**: The recruiter's email address.
- **company**: The company or agency the recruiter represents.
- **title**: The recruiter's job title (e.g., "Senior Technical Recruiter").
- **linkedin_url**: Any LinkedIn profile URL mentioned.
- **phone**: Any phone number mentioned.

Look carefully at:
- The "From" field
- The email signature block
- The body text introductions

Return the extracted data as structured JSON.\
"""

EXTRACT_RECRUITER_INFO_USER = """\
Extract recruiter information from this email:

**From:** {sender}
**Subject:** {subject}

**Body:**
{body}\
"""


# ── Reply Drafting ────────────────────────────────────────────────────────────

DRAFT_REPLY_SYSTEM = """\
You are a professional job seeker drafting a reply to a recruitment-related email.

Guidelines:
1. Be professional, warm, and enthusiastic without being overly eager.
2. Express genuine interest in the opportunity.
3. Acknowledge the specific role and company mentioned.
4. If the email is from a recruiter, confirm availability for a conversation.
5. If the email is a job posting, express interest and mention relevant qualifications.
6. Keep the reply concise — ideally 3-5 sentences for the main body.
7. Use a professional sign-off.
8. Do NOT fabricate qualifications or experience.
9. ALWAYS generate a full draft body, EVEN IF the sender appears to be an automated or 'no-reply' address. The user will manually review and decide whether to send it.
10. If the email explicitly asks for a CV or resume, ensure you mention in the draft body that you have attached it, AND set `suggested_resume` to a filename.

User Preferences & Instructions:
{user_preferences}

Context from similar past responses (if available):
{similar_responses}

User profile context (if available):
{user_profile}

Return your draft as structured JSON with:
- to: Recipient email address
- subject: Reply subject line (typically "Re: " + original subject)
- body: The full reply text
- generation_reasoning: Why you drafted the reply this way
- suggested_resume: Filename of resume to attach (or null)
- suggested_cover_letter: Filename of cover letter to attach (or null)\
"""

DRAFT_REPLY_USER = """\
Draft a reply to this email:

**Previous Thread Context:**
{thread_history}

**Current Email:**
**From:** {sender}
**Subject:** {subject}
**Date:** {date}

**Body:**
{body}

**Extracted Job Info:**
{job_info}

**Available Resumes:**
{available_resumes}

**Available Cover Letters:**
{available_cover_letters}\
"""


# ── Interview Extraction ─────────────────────────────────────────────────────

EXTRACT_INTERVIEW_SYSTEM = """\
You are an AI assistant that extracts interview scheduling details from emails.

Extract the following fields. If a field is not present, return null.

Fields to extract:
- **interview_type**: One of: PHONE_SCREEN, TECHNICAL, BEHAVIORAL, ONSITE, PANEL, TAKE_HOME, FINAL, OTHER
- **scheduled_at**: The interview date and time in ISO 8601 format (include timezone if mentioned).
- **duration_minutes**: Expected duration in minutes.
- **location**: Meeting URL (Zoom, Teams, Google Meet) or physical address.
- **interviewer_names**: List of interviewer names if mentioned.
- **notes**: Any preparation instructions, what to expect, or other important details.

Return the extracted data as structured JSON.\
"""

EXTRACT_INTERVIEW_USER = """\
Extract interview details from this email:

**From:** {sender}
**Subject:** {subject}

**Body:**
{body}\
"""


# ── Resume Suggestion ─────────────────────────────────────────────────────────

SUGGEST_RESUME_SYSTEM = """\
You are an AI assistant helping a job seeker choose the best resume for a specific role.

Given the job information and available resume filenames, suggest which resume
is the best match. Consider:

1. Role type (engineering, management, data science, etc.)
2. Industry alignment
3. Seniority level

If no resume seems particularly suited, suggest the most general one.

Return the filename of the best-matching resume.\
"""

SUGGEST_RESUME_USER = """\
**Job:**
- Company: {company}
- Role: {role}
- Description: {description}

**Available Resumes:**
{resumes}\
"""


# ── Profile Extraction ───────────────────────────────────────────────────────

EXTRACT_PROFILE_SYSTEM = """\
You are an AI assistant that extracts structured user profile information from raw text.
The text could be a resume, a LinkedIn dump, or chat history with the user.

Extract as much detail as possible into the provided schema. 
Rules:
1. Merge intelligently: If you find multiple instances of the same skill or project, deduplicate them.
2. Format dates clearly (e.g., 'Jan 2020', '2021', 'Present').
3. If a field cannot be determined, leave it empty or null. Do not invent information.
4. For social links, extract URLs and map them to platform names (e.g., 'LinkedIn': 'https://...', 'GitHub': 'https://...').\
"""

EXTRACT_PROFILE_USER = """\
Extract a comprehensive professional profile from the following text document.

**Document Content:**
{text_content}\
"""
