import os
import imaplib
import email
from email.header import decode_header
import time
import random
import schedule
import threading
from dotenv import load_dotenv
from backend.database import insert_job, create_draft, get_all_jobs
from backend.agents.matcher import generate_email_response

load_dotenv()

def match_email_to_job(sender, subject, body):
    """Finds a matching job for an incoming email or creates one."""
    jobs = get_all_jobs()
    company = "Unknown Company"
    title = "Software Engineer"
    
    if "@" in sender:
        domain = sender.split("@")[1].split(".")[0]
        company = domain.capitalize()
        
    for j in jobs:
        if company.lower() in j["company"].lower() or j["company"].lower() in company.lower():
            return j["id"]
            
    # Insert a new job context for this unexpected outreach
    job_id = insert_job(
        title=title,
        company=company,
        description=f"Recruitment outreach email: {subject}\n\n{body[:250]}...",
        deep_link=f"mailto:{sender}?subject={subject}",
        status="interviewing"
    )
    return job_id

def decode_mime_words(s):
    """Decode standard email header words."""
    clean_parts = []
    for part, encoding in decode_header(s or ""):
        if isinstance(part, bytes):
            clean_parts.append(part.decode(encoding or "utf-8", errors="ignore"))
        else:
            clean_parts.append(part)
    return "".join(clean_parts)

def check_gmail_imap(status_callback=None):
    """Connects to Gmail IMAP server and checks for recruiter emails."""
    # Read environment variables dynamically to support hot-reloading from settings/resumes
    gmail_email = os.getenv("GMAIL_EMAIL", "")
    gmail_pwd = os.getenv("GMAIL_APP_PASSWORD", "")

    def log(msg):
        print(f"[Gmail Daemon] {msg}")
        if status_callback:
            status_callback(msg)
            
    if not gmail_email or "your_email" in gmail_email or not gmail_pwd or "your_app_password" in gmail_pwd:
        log("Gmail credentials not configured. Running mock email intake...")
        return run_mock_email_intake(status_callback=status_callback)
        
    try:
        log(f"Checking mailbox {gmail_email}...")
        log("Connecting to imap.gmail.com via SSL...")
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        log("Authenticating credentials...")
        mail.login(gmail_email, gmail_pwd)
        log("Accessing inbox folder...")
        mail.select("inbox")
        
        # Try X-GM-RAW search first for last 24h, fallback to UNSEEN
        log("Searching folder for recruitment-related keywords...")
        try:
            status, messages = mail.search(None, 'X-GM-RAW', 'newer_than:24h')
        except Exception:
            status, messages = mail.search(None, 'UNSEEN')
        
        if status != "OK" or not messages or not messages[0]:
            log("No messages found or search failed.")
            mail.logout()
            return []
            
        mail_ids = messages[0].split()
        log(f"Found {len(mail_ids)} potential recruiter emails in search window.")
        
        from career_tracker.mcp_servers.gmail_server import is_job_related
        
        processed_emails = []
        for mail_id in mail_ids[-10:]: # Look at the 10 most recent
            status, data = mail.fetch(mail_id, "(RFC822 FLAGS)")
            if status != "OK" or not data:
                continue
                
            raw_email = None
            is_read = False
            for part in data:
                if isinstance(part, tuple):
                    raw_email = part[1]
                    if b"\\Seen" in part[0]:
                        is_read = True
                        
            if not raw_email:
                continue
                
            msg = email.message_from_bytes(raw_email)
            
            subject = decode_mime_words(msg["Subject"])
            sender = decode_mime_words(msg["From"])
            recipient = decode_mime_words(msg["To"] or msg["Delivered-To"] or gmail_email)
            date_str = decode_mime_words(msg["Date"])
            message_id = msg["Message-ID"] or f"imap_{mail_id.decode()}"
            
            # Extract body
            body_text = ""
            body_html = ""
            
            def extract_body(payload_msg):
                nonlocal body_text, body_html
                if payload_msg.is_multipart():
                    for part in payload_msg.walk():
                        content_type = part.get_content_type()
                        content_disposition = str(part.get("Content-Disposition"))
                        if "attachment" not in content_disposition:
                            payload = part.get_payload(decode=True)
                            if payload:
                                if content_type == "text/plain":
                                    body_text = payload.decode(errors="ignore")
                                elif content_type == "text/html":
                                    body_html = payload.decode(errors="ignore")
                else:
                    payload = payload_msg.get_payload(decode=True)
                    if payload:
                        if payload_msg.get_content_type() == "text/html":
                            body_html = payload.decode(errors="ignore")
                        else:
                            body_text = payload.decode(errors="ignore")
                            
            extract_body(msg)
            
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
                    log(f"HTML parsing failed: {str(e)}")

            # Apply plain-text job-specific filtering
            if not is_job_related(subject, body_text, sender):
                log(f"Skipping unrelated email: '{subject}'")
                continue
                
            log(f"Reading recruitment email: '{subject}' from {sender}...")
            
            # Match email to job and create draft in the background
            log(f"Matching email sender to database job contexts...")
            job_id = match_email_to_job(sender, subject, body_text)
            
            # Generate email reply
            log(f"Generating automated response draft...")
            try:
                reply_subject, reply_body = generate_email_response(job_id, sender, subject, body_text)
                create_draft(job_id, sender, reply_subject, reply_body)
            except Exception as ge:
                log(f"Failed to generate draft: {ge}")
            
            processed_emails.append({
                "message_id": message_id,
                "thread_id": message_id,
                "subject": subject,
                "sender": sender,
                "recipient": recipient,
                "date": date_str,
                "body_text": body_text,
                "body_html": body_html or None,
                "labels": ["INBOX"],
                "is_read": is_read
            })
            
            log(f"Saved response draft for {sender} successfully.")
            
        mail.logout()
        log("Gmail mailbox checked and disconnected successfully.")
        return processed_emails
        
    except Exception as e:
        log(f"Connection error: {e}. Falling back to mock email intake.")
        return run_mock_email_intake(status_callback=status_callback)

def run_mock_email_intake(status_callback=None):
    """Simulates receiving a recruiter email for local testing/demo."""
    def log(msg):
        print(f"[Gmail Daemon] {msg}")
        if status_callback:
            status_callback(msg)
            
    log("Simulating recruitment email intake...")
    mock_email = {
        "sender": "recruit@vertexcorp.com",
        "subject": "Interview scheduling for Software Engineer position at Vertex Corp",
        "body": """
        Hi Gautam,
        
        Thank you for your interest in Vertex Corp. We reviewed your resume and would love to schedule a 30-minute technical screening call with our engineering lead.
        
        Please let us know your availability for next Tuesday and Wednesday between 10:00 AM and 3:00 PM EST.
        
        Best regards,
        Sarah Jenkins
        Talent Acquisition, Vertex Corp
        """
    }
    
    # Store this context or trigger draft generation if we have a matching job
    # Check if a matching job already exists, else create one
    jobs = get_all_jobs()
    vertex_job = None
    for j in jobs:
        if "Vertex" in j["company"]:
            vertex_job = j
            break
            
    if not vertex_job:
        log("Vertex Corp job context not found. Creating new job context...")
        job_id = insert_job(
            title="Software Engineer",
            company="Vertex Corp",
            description="Software development position involving Python, APIs, and microservices.",
            deep_link="https://vertexcorp.com/careers/se-python",
            status="matched"
        )
    else:
        job_id = vertex_job["id"]
        
    # Generate draft response and save to DB
    log("Generating response draft response for Vertex Corp...")
    reply_subject, reply_body = generate_email_response(
        job_id, 
        mock_email["sender"], 
        mock_email["subject"], 
        mock_email["body"]
    )
    create_draft(job_id, mock_email["sender"], reply_subject, reply_body)
    
    log(f"Generated and stored response draft for Job ID: {job_id} successfully.")
    return [mock_email]

def start_gmail_daemon():
    """Starts the background checking thread."""
    def run_loop():
        # Check immediately on start
        check_gmail_imap()
        
        # Then check every 15 minutes
        schedule.every(15).minutes.do(check_gmail_imap)
        
        while True:
            schedule.run_pending()
            time.sleep(1)
            
    daemon_thread = threading.Thread(target=run_loop, daemon=True)
    daemon_thread.start()
    print("[Gmail Daemon] Background listener thread started successfully.")

if __name__ == "__main__":
    # Test IMAP check
    check_gmail_imap()
