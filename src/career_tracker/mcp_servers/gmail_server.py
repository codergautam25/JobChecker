"""Gmail MCP Tool Server.

Exposes Gmail API operations as MCP tools that the LangGraph workflow
can invoke. Handles OAuth2 authentication, token refresh, and message
parsing.

Usage (standalone)::

    python -m career_tracker.mcp_servers.gmail_server

Or as an MCP server via stdio transport.
"""

from __future__ import annotations

import base64
import json
import os
import re
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Optional

import structlog
from mcp.server.fastmcp import FastMCP

from career_tracker.config import get_settings

logger = structlog.get_logger(__name__)

mcp = FastMCP("GmailToolServer")


def get_all_authenticated_accounts() -> list[str]:
    settings = get_settings()
    tokens_dir = settings.resolve_path(Path("data/tokens"))
    
    accounts = []
    if tokens_dir.exists():
        for f in tokens_dir.glob("*.json"):
            accounts.append(f.stem)
            
    # Always check for legacy token.json and append if it exists
    legacy_token = settings.resolve_path(settings.gmail_token_path)
    if legacy_token.exists():
        accounts.append("legacy")
            
    return accounts

def _get_gmail_service(email_address: str = None):
    """Build and return an authenticated Gmail API service.

    Handles the OAuth2 flow:
    1. If token.json exists and is valid, use it.
    2. If token.json is expired, refresh it.
    3. If no token.json, open browser for OAuth consent.
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    settings = get_settings()
    creds_path = settings.resolve_path(settings.gmail_credentials_path)
    
    tokens_dir = settings.resolve_path(Path("data/tokens"))
    tokens_dir.mkdir(parents=True, exist_ok=True)
    
    token_path = None
    if email_address and email_address != "legacy":
        token_path = tokens_dir / f"{email_address}.json"
    else:
        # If no specific email, try legacy token or first available
        legacy_token = settings.resolve_path(settings.gmail_token_path)
        if legacy_token.exists():
            token_path = legacy_token
        else:
            accounts = get_all_authenticated_accounts()
            if accounts:
                token_path = tokens_dir / f"{accounts[0]}.json"
            else:
                token_path = settings.resolve_path(settings.gmail_token_path) # Fallback to creating legacy if all fails

    scopes = settings.gmail_scopes

    creds = None

    # Load existing token
    if token_path and token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)

    # Refresh or re-authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            logger.info("gmail.token_refreshed")
        else:
            if not creds_path.exists():
                raise FileNotFoundError(
                    f"Gmail credentials not found at {creds_path}. "
                    "Download credentials.json from Google Cloud Console "
                    "and place it in the data/ directory."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), scopes)
            creds = flow.run_local_server(port=0)
            logger.info("gmail.authenticated_via_browser")

            # Try to get the email address immediately to save it correctly
            try:
                temp_service = build("gmail", "v1", credentials=creds)
                profile = temp_service.users().getProfile(userId="me").execute()
                new_email = profile.get("emailAddress")
                if new_email:
                    token_path = tokens_dir / f"{new_email}.json"
                    # We might have started with legacy path, so update the token_path to the new one
            except Exception as e:
                logger.warning(f"Could not fetch email profile during auth: {e}")

        # Save token for future runs
        if token_path:
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def _parse_message(msg: dict, receiver_email: str = "") -> dict:
    """Parse a raw Gmail API message into a structured dict."""
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}

    # Extract body
    body_text = ""
    body_html = ""
    attachments = []

    def _extract_parts(payload: dict) -> None:
        nonlocal body_text, body_html
        mime_type = payload.get("mimeType", "")

        if "parts" in payload:
            for part in payload["parts"]:
                _extract_parts(part)
        elif mime_type == "text/plain" and "data" in payload.get("body", {}):
            body_text = base64.urlsafe_b64decode(
                payload["body"]["data"]
            ).decode("utf-8", errors="replace")
        elif mime_type == "text/html" and "data" in payload.get("body", {}):
            body_html = base64.urlsafe_b64decode(
                payload["body"]["data"]
            ).decode("utf-8", errors="replace")

        # Track attachments
        if payload.get("filename"):
            attachments.append({
                "attachment_id": payload.get("body", {}).get("attachmentId", ""),
                "filename": payload["filename"],
                "mime_type": mime_type,
                "size_bytes": int(payload.get("body", {}).get("size", 0)),
            })

    _extract_parts(msg.get("payload", {}))

    # If body_text is empty or too short / placeholder, parse body_html to extract clean text
    if (not body_text or len(body_text.strip()) < 50 or "enable html" in body_text.lower()) and body_html:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(body_html, "html.parser")
            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text(separator=" ")
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            extracted_text = "\n".join(chunk for chunk in chunks if chunk)
            if len(extracted_text.strip()) > len(body_text.strip()):
                body_text = extracted_text
        except Exception as e:
            logger.warning("gmail.html_parse_failed", error=str(e))

    return {
        "message_id": msg["id"],
        "thread_id": msg.get("threadId", ""),
        "subject": headers.get("subject", "(no subject)"),
        "sender": headers.get("from", ""),
        "recipient": receiver_email or headers.get("to", ""),
        "receiver_email": receiver_email or headers.get("to", ""),
        "date": headers.get("date", ""),
        "body_text": body_text,
        "body_html": body_html or None,
        "labels": msg.get("labelIds", []),
        "attachments": attachments,
        "is_read": "UNREAD" not in msg.get("labelIds", []),
    }


@mcp.tool()
def list_unread_emails(max_results: int = 20, label: str = "INBOX") -> list[dict]:
    """List unread emails from Gmail (legacy — prefer fetch_recent_emails).

    Args:
        max_results: Maximum number of emails to fetch (default 20).
        label: Gmail label to filter by (default INBOX).

    Returns:
        List of parsed email dicts with message_id, subject, sender, body, etc.
    """
    service = _get_gmail_service()

    results = (
        service.users()
        .messages()
        .list(
            userId="me",
            labelIds=[label, "UNREAD"],
            maxResults=max_results,
        )
        .execute()
    )

    messages = results.get("messages", [])
    if not messages:
        logger.info("gmail.no_unread_emails")
        return []

    parsed = []
    for msg_stub in messages:
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=msg_stub["id"], format="full")
            .execute()
        )
        parsed.append(_parse_message(msg))

    logger.info("gmail.fetched_emails", count=len(parsed))
    return parsed


TRUSTED_JOB_DOMAINS = [
    'linkedin.com', 'naukri.com', 'naukri.info', 'naukrigulf.com',
    'hirist.com', 'hirist.tech', 'indeed.com', 'glassdoor.com',
    'wellfound.com', 'monster.com', 'shine.com', 'iimjobs.com',
    'instahyre.com', 'cutshort.io', 'angel.co', 'foundit.in',
    'apna.co', 'internshala.com', 'unstop.com',
]


def is_job_related(subject: str, body_text: str, sender: str) -> bool:
    """Determine if an email is specific to jobs or job invitations.
    Filters out transactional, financial, security, newsletters, and other clutter.
    """
    subject_lower = subject.lower()
    body_lower = body_text.lower()
    sender_lower = sender.lower()
    
    # Check if sender is from a trusted job platform
    is_trusted_platform = any(domain in sender_lower for domain in TRUSTED_JOB_DOMAINS)
    
    # 1. Quick discard based on sender and subject for security alerts, OTP, bank alerts
    block_subjects = [
        "device registration", "new device", "sign-in", "sign in", "login", 
        "otp", "one-time password", "verification code", "e-statement", "statement for", 
        "reward point", "points balance", "account statement", "payment received", 
        "invoice", "receipt", "your bill", "security alert", "password reset", 
        "confirm your email", "verify your account", "verify email", "transaction alert", 
        "order confirmed", "your order", "shipment update", "delivered", "package update",
        "subscription confirmation", "welcome to", "auto-reply", "out of office"
    ]
    if not is_trusted_platform and any(s in subject_lower for s in block_subjects):
        return False
        
    block_senders = [
        "alert", "security", "noreply", "no-reply", "billing", "support", 
        "transaction", "statement", "banking", "marketing", "newsletter",
        "promo", "offer@", "info@", "update@", "notification"
    ]
    
    # Check if subject has a strong job keyword
    has_strong_subject_job_keyword = any(
        kw in subject_lower for kw in [
            "job", "hiring", "interview", "application", "applied", "position", 
            "role", "candidate", "resume", "cv", "recruiter", "rejection", "offer"
        ]
    )
    
    if not is_trusted_platform and any(s in sender_lower for s in block_senders) and not has_strong_subject_job_keyword:
        return False
        
    # 2. Check for recruitment keywords with word boundaries
    keywords = [
        "job", "role", "position", "opportunity", "recruiter", "hiring",
        "interview", "application", "applied", "candidate", "career",
        "opening", "vacancy", "offer", "resume", "cv", "talent",
        "engineer", "developer", "analyst", "manager", "intern",
        "naukri", "linkedin", "hirist", "indeed", "glassdoor",
        "instahyre", "cutshort", "internshala", "unstop",
    ]
    
    pattern = r'\b(' + '|'.join(keywords) + r')s?\b'
    regex = re.compile(pattern, re.IGNORECASE)
    
    text_to_check = f"{subject}\n{body_text}"
    if not regex.search(text_to_check):
        return False
        
    # 3. Exclude cases where only title/weak/marketing keywords match but subject is unrelated
    matched_words = set(regex.findall(text_to_check.lower()))
    
    title_keywords = {"developer", "engineer", "manager", "analyst", "intern"}
    weak_keywords = {"career", "opportunity", "talent", "offer"}
    
    if matched_words.issubset(title_keywords.union(weak_keywords)) and not has_strong_subject_job_keyword:
        return False
        
    return True


@mcp.tool()
def fetch_recent_emails(
    hours: int = 24,
    max_results: int = 50,
    since_timestamp: Optional[int] = None,
) -> dict:
    """Fetch all emails from the last N hours or since a specific timestamp, with full counts for the funnel display.
    Iterates through ALL authenticated accounts in data/tokens.
    """
    accounts = get_all_authenticated_accounts()
    if not accounts:
        # Fallback to default
        accounts = ["legacy"]

    keywords = "(job OR role OR position OR opportunity OR recruiter OR hiring OR interview OR application OR applied OR candidate OR career OR opening OR vacancy OR offer OR resume OR cv OR talent OR engineer OR developer OR analyst OR manager OR intern OR naukri OR linkedin OR hirist OR indeed OR glassdoor OR instahyre OR cutshort OR internshala OR unstop)"
    if since_timestamp:
        query = f"after:{since_timestamp} (in:inbox OR in:spam) {keywords}"
    else:
        query = f"newer_than:{hours}h (in:inbox OR in:spam) {keywords}"
    
    all_parsed = []
    total_in_window = 0
    unread_count = 0

    for account in accounts:
        try:
            service = _get_gmail_service(account if account != "legacy" else None)
            
            # Fetch profile to get exact email if possible, or use account stem
            real_email = account
            if account == "legacy":
                try:
                    profile = service.users().getProfile(userId="me").execute()
                    real_email = profile.get("emailAddress", "legacy")
                except:
                    pass

            results = (
                service.users()
                .messages()
                .list(
                    userId="me",
                    q=query,
                    maxResults=max_results,
                )
                .execute()
            )

            messages = results.get("messages", [])
            total_in_window += results.get("resultSizeEstimate", len(messages))

            for msg_stub in messages:
                msg = (
                    service.users()
                    .messages()
                    .get(userId="me", id=msg_stub["id"], format="full")
                    .execute()
                )
                email = _parse_message(msg, receiver_email=real_email)
                if is_job_related(email.get("subject", ""), email.get("body_text", ""), email.get("sender", "")):
                    all_parsed.append(email)
                    if not email["is_read"]:
                        unread_count += 1
        except Exception as e:
            logger.error(f"gmail.fetch_recent_emails.account_error", account=account, error=str(e))

    logger.info(
        "gmail.fetched_recent",
        hours=hours,
        total_in_window=total_in_window,
        fetched=len(all_parsed),
        unread=unread_count,
        accounts=len(accounts)
    )
    return {
        "emails": all_parsed,
        "total_in_window": total_in_window,
        "unread_count": unread_count,
    }


@mcp.tool()
def get_email(message_id: str) -> dict:
    """Get full email content by Gmail message ID.

    Args:
        message_id: The Gmail API message ID.

    Returns:
        Parsed email dict with full body, headers, and attachment info.
    """
    service = _get_gmail_service()
    msg = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )
    return _parse_message(msg)


@mcp.tool()
def send_email(
    to: str,
    subject: str,
    body: str,
    reply_to_message_id: Optional[str] = None,
    attachment_path: Optional[str] = None,
    sender_email: Optional[str] = None,
) -> dict:
    """Send an email via Gmail.

    IMPORTANT: This tool should only be called AFTER human approval.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Email body text.
        reply_to_message_id: If replying, the original message ID for threading.
        attachment_path: Optional absolute file path of an attachment.
        sender_email: Which authenticated account to use to send the email.

    Returns:
        Dict with the sent message ID and thread ID.
    """
    import os
    gmail_email = os.getenv('GMAIL_EMAIL', '')
    gmail_pwd = os.getenv('GMAIL_APP_PASSWORD', '')

    if gmail_email and gmail_pwd and 'your_email' not in gmail_email:
        # Use SMTP app password fallback
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.base import MIMEBase
        from email import encoders
        from pathlib import Path
        import uuid

        logger.info(f"Sending email via SMTP App Password fallback: {gmail_email} -> {to}")

        if attachment_path:
            message = MIMEMultipart()
            message["To"] = to
            message["From"] = gmail_email
            message["Subject"] = subject
            message.attach(MIMEText(body))
            
            p = Path(attachment_path)
            if p.exists():
                part = MIMEBase("application", "octet-stream")
                part.set_payload(p.read_bytes())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename={p.name}",
                )
                message.attach(part)
        else:
            message = MIMEText(body)
            message["To"] = to
            message["From"] = gmail_email
            message["Subject"] = subject

        # If replying, set threading headers
        if reply_to_message_id:
            message["In-Reply-To"] = reply_to_message_id
            message["References"] = reply_to_message_id

        # Send via SMTP
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_email, gmail_pwd)
            server.send_message(message)

        sent_msg_id = f"smtp_sent_{uuid.uuid4().hex[:12]}"
        return {
            "message_id": sent_msg_id,
            "thread_id": reply_to_message_id or sent_msg_id
        }

    service = _get_gmail_service(sender_email)

    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders

    if attachment_path:
        message = MIMEMultipart()
        message["to"] = to
        message["subject"] = subject
        message.attach(MIMEText(body))
        
        # Attach the file
        p = Path(attachment_path)
        if p.exists():
            part = MIMEBase("application", "octet-stream")
            part.set_payload(p.read_bytes())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={p.name}",
            )
            message.attach(part)
    else:
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject

    # If replying, set threading headers
    if reply_to_message_id:
        original = (
            service.users()
            .messages()
            .get(userId="me", id=reply_to_message_id, format="metadata",
                 metadataHeaders=["Message-ID", "References", "In-Reply-To"])
            .execute()
        )
        headers = {
            h["name"]: h["value"]
            for h in original.get("payload", {}).get("headers", [])
        }
        if "Message-ID" in headers:
            message["In-Reply-To"] = headers["Message-ID"]
            message["References"] = headers.get("References", "") + " " + headers["Message-ID"]

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    body_payload: dict[str, Any] = {"raw": raw}

    if reply_to_message_id:
        # Get the thread ID from the original message
        original_msg = (
            service.users()
            .messages()
            .get(userId="me", id=reply_to_message_id, format="minimal")
            .execute()
        )
        body_payload["threadId"] = original_msg.get("threadId")

    sent = (
        service.users()
        .messages()
        .send(userId="me", body=body_payload)
        .execute()
    )

    logger.info("gmail.email_sent", to=to, subject=subject, message_id=sent["id"])
    return {
        "message_id": sent["id"],
        "thread_id": sent.get("threadId", ""),
        "status": "sent",
    }


@mcp.tool()
def download_attachment(
    message_id: str,
    attachment_id: str,
    filename: str,
) -> str:
    """Download an email attachment to local storage.

    Args:
        message_id: Gmail message ID containing the attachment.
        attachment_id: The attachment ID within the message.
        filename: Desired filename for the downloaded file.

    Returns:
        The local file path where the attachment was saved.
    """
    settings = get_settings()
    service = _get_gmail_service()

    attachment = (
        service.users()
        .messages()
        .attachments()
        .get(userId="me", messageId=message_id, id=attachment_id)
        .execute()
    )

    data = base64.urlsafe_b64decode(attachment["data"])

    save_dir = settings.resolve_path(settings.attachments_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / filename

    # Avoid overwriting — add suffix if file exists
    counter = 1
    original_stem = save_path.stem
    while save_path.exists():
        save_path = save_dir / f"{original_stem}_{counter}{save_path.suffix}"
        counter += 1

    save_path.write_bytes(data)
    logger.info("gmail.attachment_downloaded", path=str(save_path), size=len(data))
    return str(save_path)


def extract_email_attachment_text(message_id: str, attachment_id: str, mime_type: str, receiver_email: str = None) -> str:
    """Fetch an attachment payload and attempt to extract text."""
    try:
        service = _get_gmail_service(receiver_email)
        attachment = service.users().messages().attachments().get(
            userId="me", messageId=message_id, id=attachment_id
        ).execute()
        
        data = attachment.get("data")
        if not data:
            return ""
            
        file_data = base64.urlsafe_b64decode(data)
        
        if mime_type == "application/pdf":
            import io
            import pypdf
            pdf_reader = pypdf.PdfReader(io.BytesIO(file_data))
            text = []
            for page in pdf_reader.pages:
                text.append(page.extract_text() or "")
            return "\n".join(text).strip()
            
        elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            import io
            import docx
            doc = docx.Document(io.BytesIO(file_data))
            return "\n".join([p.text for p in doc.paragraphs]).strip()
            
        elif mime_type == "text/plain":
            return file_data.decode("utf-8", errors="replace").strip()
            
        return f"[Attachment type {mime_type} not supported for text extraction]"
    except Exception as e:
        logger.warning("attachment.extraction_failed", error=str(e), message_id=message_id)
        return f"[Failed to extract attachment: {str(e)}]"


if __name__ == "__main__":
    mcp.run(transport="stdio")
