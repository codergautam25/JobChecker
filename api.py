import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import asyncio

from career_tracker.services import _get_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Career Tracker API")

# Enable CORS for React development server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def run_db_cleanup():
    """Cleanup database on startup to remove existing unrelated emails and old scraped posts."""
    try:
        from career_tracker.services import _get_db
        from career_tracker.mcp_servers.gmail_server import is_job_related
        
        db = _get_db()
        rows = db.execute("SELECT id, subject, sender, body_text FROM emails")
        to_delete = []
        for r in rows:
            if not is_job_related(r["subject"], r["body_text"], r["sender"]):
                to_delete.append(r["id"])
                
        if to_delete:
            logger.info(f"Cleanup: Found {len(to_delete)} unrelated emails. Deleting them...")
            for email_id in to_delete:
                db.execute("DELETE FROM emails WHERE id = ?", (email_id,))
            logger.info("Cleanup complete.")
        else:
            logger.info("No unrelated emails found in database.")
            
        # Purge scraped post data older than 7 days
        logger.info("Purging scraped posts older than 7 days...")
        db.execute_write("DELETE FROM intel_posts WHERE created_at < datetime('now', '-7 days')")
        logger.info("Scraped posts purge complete.")
    except Exception as e:
        logger.error(f"Error running database cleanup on startup: {e}")

PORTAL_LOGS = {}

class ConnectionManager:
    def __init__(self):
        self.active_connections = {}

    async def connect(self, websocket: WebSocket, workflow_id: str):
        await websocket.accept()
        if workflow_id not in self.active_connections:
            self.active_connections[workflow_id] = []
        self.active_connections[workflow_id].append(websocket)
        
        if workflow_id in PORTAL_LOGS:
            for log_line in PORTAL_LOGS[workflow_id]:
                try:
                    await websocket.send_text(log_line)
                except Exception:
                    pass

    def disconnect(self, websocket: WebSocket, workflow_id: str):
        if workflow_id in self.active_connections:
            if websocket in self.active_connections[workflow_id]:
                self.active_connections[workflow_id].remove(websocket)
            if not self.active_connections[workflow_id]:
                del self.active_connections[workflow_id]

    async def broadcast(self, message: str, workflow_id: str):
        if workflow_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[workflow_id]:
                try:
                    await connection.send_text(message)
                except Exception:
                    disconnected.append(connection)
            for d in disconnected:
                self.disconnect(d, workflow_id)

manager = ConnectionManager()

@app.websocket("/ws/logs/{workflow_id}")
async def websocket_logs(websocket: WebSocket, workflow_id: str):
    await manager.connect(websocket, workflow_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, workflow_id)

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

@app.get("/api/dashboard/weekly-reach")
def get_weekly_reach(weeks: int = 8):
    """Return weekly application reach data for the seismic graph."""
    from datetime import datetime, timedelta
    db = _get_db()
    
    today = datetime.utcnow()
    # Align to the start of the current week (Monday)
    start_of_week = today - timedelta(days=today.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    
    result = []
    for i in range(weeks - 1, -1, -1):
        week_start = start_of_week - timedelta(weeks=i)
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        
        ws = week_start.strftime('%Y-%m-%d')
        we = week_end.strftime('%Y-%m-%d 23:59:59')
        
        # Count applications applied in this week
        app_rows = db.execute(
            "SELECT COUNT(*) as c FROM applications WHERE status='APPLIED' AND (applied_at BETWEEN ? AND ? OR (applied_at IS NULL AND created_at BETWEEN ? AND ?))",
            (ws, we, ws, we)
        )
        app_count = app_rows[0]['c'] if app_rows else 0
        
        # Count approved agent_apply approvals in this week
        appr_rows = db.execute(
            "SELECT COUNT(*) as c FROM approval_queue WHERE action_type='agent_apply' AND status IN ('APPROVED', 'APPLIED') AND (reviewed_at BETWEEN ? AND ? OR (reviewed_at IS NULL AND created_at BETWEEN ? AND ?))",
            (ws, we, ws, we)
        )
        appr_count = appr_rows[0]['c'] if appr_rows else 0
        
        total = app_count + appr_count
        
        # Week label
        week_num = weeks - i
        label = f"Week {week_num}"
        date_label = f"{week_start.strftime('%b %d')} – {week_end.strftime('%b %d')}"
        
        result.append({
            "week": week_num,
            "label": label,
            "date_range": date_label,
            "start": ws,
            "end": we,
            "count": total,
        })
    
    return {"weeks": result}

@app.get("/api/dashboard")
def get_dashboard():
    # We query the DB directly to return JSON for the Next.js frontend
    db = _get_db()
    
    # 1. Total Jobs tracked
    row = db.execute("SELECT COUNT(*) as c FROM applications")
    total_jobs = row[0]['c'] if row else 0

    # 2. Resumes parsed (We'll just count user profiles for now)
    row = db.execute("SELECT COUNT(*) as c FROM user_profiles")
    total_resumes = row[0]['c'] if row else 0

    # 3. Emails processed
    row = db.execute("SELECT COUNT(*) as c FROM emails")
    total_emails = row[0]['c'] if row else 0

    # 4. Applications tracked
    row = db.execute("SELECT COUNT(*) as c FROM applications WHERE status='APPLIED'")
    total_applied = row[0]['c'] if row else 0

    # 5. Classifications (for Pie Chart)
    classifications = db.execute("SELECT category as name, COUNT(*) as value FROM emails WHERE category IS NOT NULL GROUP BY category")
    
    # 6. Application Volume (for Bar Chart)
    volume = db.execute("SELECT date(created_at) as date, COUNT(*) as applications FROM applications WHERE created_at >= date('now', '-30 days') GROUP BY date(created_at) ORDER BY date ASC")
    
    # 7. Conversion Metrics
    interviews = db.execute("SELECT COUNT(*) as c FROM interviews")
    total_interviews = interviews[0]['c'] if interviews else 0
    conversion_rate = round((total_interviews / total_applied) * 100, 1) if total_applied > 0 else 0

    # Recent Activity (mocked or simplified if events table schema is unknown)
    try:
        activity_rows = db.execute("SELECT created_at as timestamp, entity_type, entity_id, event_type FROM events ORDER BY created_at DESC LIMIT 10")
        for r in activity_rows:
            r['event_name'] = r['event_type']
    except Exception:
        activity_rows = []
    
    return {
        "stats": {
            "total_jobs": total_jobs,
            "total_resumes": total_resumes,
            "total_emails": total_emails,
            "total_applied": total_applied,
            "total_interviews": total_interviews,
            "conversion_rate": conversion_rate
        },
        "classifications": classifications,
        "volume": volume,
        "activity": activity_rows
    }

@app.get("/api/emails")
def get_emails(status: str = "ALL", limit: int = 50, page: int = 1, search: str = "", account: str = "ALL"):
    db = _get_db()
    
    offset = (page - 1) * limit
    
    count_query = "SELECT COUNT(*) as cnt FROM emails"
    query = "SELECT id, date, sender, recipient, subject, status, labels FROM emails"
    params = []
    conditions = []
    
    if status != "ALL":
        conditions.append("status = ?")
        params.append(status)
    
    if search.strip():
        conditions.append("subject LIKE ?")
        params.append(f"%{search.strip()}%")
        
    if account and account != "ALL":
        conditions.append("recipient = ?")
        params.append(account)
    
    where_clause = ""
    if conditions:
        where_clause = " WHERE " + " AND ".join(conditions)
        
    count_query = f"SELECT COUNT(DISTINCT COALESCE(thread_id, id)) as cnt FROM emails {where_clause}"
        
    count_rows = db.execute(count_query, tuple(params))
    total = count_rows[0]["cnt"] if count_rows else 0
        
    query = f"""
    WITH RankedEmails AS (
        SELECT id, thread_id, date, sender, recipient, subject, status, labels, attachments_metadata, attachment_extracted_text, matched_skills,
               ROW_NUMBER() OVER(PARTITION BY COALESCE(thread_id, id) ORDER BY date DESC) as rn,
               COUNT(*) OVER(PARTITION BY COALESCE(thread_id, id)) as thread_count
        FROM emails
        {where_clause}
    )
    SELECT id, thread_id, date, sender, recipient, subject, status, labels, attachments_metadata, attachment_extracted_text, matched_skills, thread_count
    FROM RankedEmails
    WHERE rn = 1
    ORDER BY date DESC LIMIT ? OFFSET ?
    """
    
    params.extend([limit, offset])
    
    rows = db.execute(query, tuple(params))
    return {"emails": rows, "total": total}

from pydantic import BaseModel as BaseModel  # noqa: ensure available

class UpdateEmailStatusRequest(BaseModel):
    status: str

@app.patch("/api/emails/{email_id}/status")
def update_email_status(email_id: str, req: UpdateEmailStatusRequest):
    db = _get_db()
    valid_statuses = ["PENDING", "APPROVED", "REJECTED"]
    if req.status not in valid_statuses:
        return JSONResponse(status_code=400, content={"error": f"Invalid status. Must be one of: {valid_statuses}"})
    db.execute("UPDATE emails SET status = ? WHERE id = ?", (req.status, email_id))
    return {"status": "success", "new_status": req.status}

class UpdateApprovalStatusRequest(BaseModel):
    status: str

@app.patch("/api/approvals/{approval_id}/status")
def update_approval_status(approval_id: str, req: UpdateApprovalStatusRequest):
    db = _get_db()
    db.execute("UPDATE approval_queue SET status = ? WHERE id = ?", (req.status, approval_id))
    return {"status": "success", "new_status": req.status}

@app.get("/api/approvals/sent_mail")
def get_sent_mail_approvals(status: str = "PENDING_APPROVAL", limit: int = 50, account: str = "ALL"):
    db = _get_db()
    
    query = "SELECT id, created_at, action_type, status, payload FROM approval_queue WHERE action_type IN ('sent_mail', 'send_email')"
    params = []
    
    if status != "ALL":
        query += " AND status = ?"
        params.append(status)
        
    if account and account != "ALL":
        # Using SQLite json_extract to filter by receiver_email in payload
        query += " AND json_extract(payload, '$.receiver_email') = ?"
        params.append(account)
        
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    
    rows = db.execute(query, tuple(params))
    return {"approvals": rows}

@app.get("/api/approvals/agent_apply")
def get_agent_apply_approvals(status: str = "PENDING_APPROVAL", limit: int = 50, account: str = "ALL"):
    import os
    db = _get_db()
    
    query = "SELECT id, created_at, action_type, status, payload FROM approval_queue WHERE action_type='agent_apply'"
    params = []
    
    if status != "ALL":
        query += " AND status = ?"
        params.append(status)
        
    if account and account != "ALL":
        query += " AND json_extract(payload, '$.receiver_email') = ?"
        params.append(account)
        
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    
    rows = db.execute(query, tuple(params))
    
    # Check screenshot existence for each row
    screenshot_dir = os.path.abspath(os.path.join(os.getcwd(), "data", "screenshots"))
    for row in rows:
        row["has_screenshot"] = os.path.exists(os.path.join(screenshot_dir, f"{row['id']}.png"))
    
    return {"approvals": rows}

@app.get("/api/approvals/all")
def get_all_approvals(status: str = "PENDING_APPROVAL", limit: int = 50, account: str = "ALL"):
    import os
    db = _get_db()
    
    query = """
        SELECT a.id, a.created_at, a.action_type, a.status, a.payload, e.matched_skills
        FROM approval_queue a
        LEFT JOIN emails e ON a.related_email_id = e.id
        WHERE 1=1
    """
    params = []
    
    if status != "ALL":
        query += " AND a.status = ?"
        params.append(status)
        
    if account and account != "ALL":
        query += " AND json_extract(a.payload, '$.receiver_email') = ?"
        params.append(account)
        
    query += " ORDER BY a.created_at DESC LIMIT ?"
    params.append(limit)
    
    rows = db.execute(query, tuple(params))
    
    # Check screenshot existence for each row
    screenshot_dir = os.path.abspath(os.path.join(os.getcwd(), "data", "screenshots"))
    for row in rows:
        row["has_screenshot"] = os.path.exists(os.path.join(screenshot_dir, f"{row['id']}.png"))
    
    return {"approvals": rows}


@app.get("/api/approvals/screenshot/{approval_id}")
def get_approval_screenshot(approval_id: str):
    import os
    from fastapi.responses import FileResponse, JSONResponse
    
    screenshot_path = os.path.abspath(os.path.join(os.getcwd(), "data", "screenshots", f"{approval_id}.png"))
    if os.path.exists(screenshot_path):
        return FileResponse(screenshot_path, media_type="image/png")
    return JSONResponse(status_code=404, content={"error": "Screenshot not found"})

@app.get("/api/emails/{email_id}")
def get_email_detail(email_id: str):
    """Return full details for a single email, including body content."""
    db = _get_db()
    rows = db.execute("SELECT * FROM emails WHERE id = ?", (email_id,))
    if not rows:
        return JSONResponse(status_code=404, content={"error": "Email not found"})
    r = rows[0]
    result = {
        "id": r.get("id"),
        "thread_id": r.get("thread_id"),
        "date": r.get("date"),
        "sender": r.get("sender"),
        "recipient": r.get("recipient"),
        "subject": r.get("subject"),
        "status": r.get("status", "PENDING"),
        "category": r.get("category"),
        "classification_confidence": r.get("classification_confidence"),
        "classification_reasoning": r.get("classification_reasoning"),
        "body_html": r.get("body_html"),
        "body_text": r.get("body_text"),
        "attachments_metadata": r.get("attachments_metadata"),
        "attachment_extracted_text": r.get("attachment_extracted_text"),
        "matched_skills": r.get("matched_skills"),
        "labels": r.get("labels")
    }
    
    if r.get("thread_id"):
        thread_rows = db.execute("SELECT id, date, sender, body_html, body_text FROM emails WHERE thread_id = ? AND id != ? ORDER BY date ASC", (r.get("thread_id"), email_id))
        result["thread_messages"] = [dict(t) for t in thread_rows]
    else:
        result["thread_messages"] = []
        
    return result

@app.get("/api/emails/sync/status")
def sync_status_endpoint():
    from pathlib import Path
    import json
    
    sync_file = Path("data/last_sync.json")
    if sync_file.exists():
        try:
            data = json.loads(sync_file.read_text())
            return {"last_synced_at": data.get("last_synced_at")}
        except Exception:
            pass
    return {"last_synced_at": None}

@app.post("/api/emails/sync")
def sync_emails_endpoint(lookback_hours: int = 24):
    from career_tracker.mcp_servers.gmail_server import fetch_recent_emails
    from career_tracker.models.email import EmailMessage
    from career_tracker.services import _get_email_repo
    from pathlib import Path
    from datetime import datetime
    import json
    import time
    
    sync_file = Path("data/last_sync.json")
    since_timestamp = None
    if sync_file.exists():
        try:
            data = json.loads(sync_file.read_text())
            if "last_synced_at" in data:
                # Convert ISO string back to timestamp, or handle if it's already an int
                pass # Wait, if I store it as an int, it's easier.
            since_timestamp = data.get("last_synced_timestamp")
        except Exception:
            pass
            
    # Always fetch a bit earlier than exactly the last timestamp to handle drift/delay (e.g. 5 minutes)
    if since_timestamp:
        since_timestamp = max(0, since_timestamp - 300)
    
    try:
        result = fetch_recent_emails(hours=lookback_hours, max_results=1000, since_timestamp=since_timestamp)
    except Exception as gmail_api_err:
        # Fallback to IMAP if Gmail API (OAuth) is not configured
        import os
        gmail_email = os.getenv('GMAIL_EMAIL', '')
        gmail_pwd = os.getenv('GMAIL_APP_PASSWORD', '')
        if gmail_email and gmail_pwd and 'your_email' not in gmail_email:
            from backend.agents.gmail_daemon import check_gmail_imap
            imap_emails = check_gmail_imap()
            result = {
                "emails": imap_emails,
                "total_in_window": len(imap_emails),
                "unread_count": sum(1 for e in imap_emails if not e.get("is_read"))
            }
        else:
            return JSONResponse(status_code=500, content={"error": f"Gmail sync failed: {str(gmail_api_err)}. Configure Gmail credentials in Settings."})
    emails = result.get("emails", [])
    repo = _get_email_repo()
    new_count = 0
    for email_data in emails:
        if not repo.exists(email_data["message_id"]):
            try:
                from email.utils import parsedate_to_datetime
                from datetime import datetime
                dt = parsedate_to_datetime(email_data["date"]) if email_data.get("date") else datetime.utcnow()
            except Exception:
                from datetime import datetime
                dt = datetime.utcnow()
                
            msg = EmailMessage(
                message_id=email_data["message_id"],
                thread_id=email_data.get("thread_id", ""),
                subject=email_data.get("subject", ""),
                sender=email_data.get("sender", ""),
                recipient=email_data.get("recipient", ""),
                date=dt,
                body_text=email_data.get("body_text", ""),
                body_html=email_data.get("body_html"),
                labels=email_data.get("labels", []),
                is_read=email_data.get("is_read", False)
            )
            repo.create(msg)
            new_count += 1
            
    # Save the new sync timestamp
    now_ts = int(time.time())
    now_iso = datetime.utcnow().isoformat() + "Z"
    try:
        sync_file.parent.mkdir(parents=True, exist_ok=True)
        sync_file.write_text(json.dumps({
            "last_synced_at": now_iso,
            "last_synced_timestamp": now_ts
        }))
    except Exception:
        pass

    return {
        "status": "success", 
        "synced": new_count,
        "last_synced_at": now_iso
    }

@app.post("/api/workflow/run")
async def run_workflow_endpoint():
    import threading
    import time
    import asyncio
    
    workflow_id = f"wf_{int(time.time())}"
    PORTAL_LOGS[workflow_id] = ["```bash\n"]
    loop = asyncio.get_running_loop()
    
    def _worker():
        try:
            from career_tracker.graph.workflow import build_workflow, run_workflow
            from datetime import datetime
            
            def _log(msg: str):
                line = msg + "\n"
                PORTAL_LOGS[workflow_id].append(line)
                asyncio.run_coroutine_threadsafe(manager.broadcast(line, workflow_id), loop)
                
            _log(f"[{datetime.now().strftime('%H:%M:%S')}] Starting workflow...")
            _log("Building workflow graph...")
            workflow = build_workflow()
            _log("Scanning local inbox for unprocessed emails...\n")
            
            first_stats = {}
            all_processed = []
            all_pending = []
            all_errors = []
            attempted_ids = set()
            iterations = 0
            
            while iterations < 200:
                iterations += 1
                thread_id = f"backend-api-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{iterations}"
                result = run_workflow(workflow, thread_id=thread_id, log_fn=_log)
                
                stats = result.get("fetch_stats") or {}
                if iterations == 1:
                    first_stats = stats
                    
                all_processed.extend(result.get("processed_email_ids", []))
                all_pending.extend(result.get("pending_approvals", []))
                all_errors.extend(result.get("errors", []))
                
                curr_id = (result.get("current_email") or {}).get("message_id")
                if curr_id:
                    if curr_id in attempted_ids:
                        _log("  [no progress — email already attempted, stopping]")
                        break
                    attempted_ids.add(curr_id)
                    
                if not result.get("should_continue") or not stats.get("new_emails"):
                    break
                    
            _log("\n===============================================")
            _log("SUMMARY")
            _log("===============================================")
            _log(f"  Unprocessed emails found       : {first_stats.get('total_in_window', 0)}")
            _log(f"  Likely recruitment emails      : {first_stats.get('recruitment_emails', 0)}")
            _log("-----------------------------------------------")
            _log(f"  Processed this run             : {len(all_processed)}")
            _log(f"  Drafts queued for approval     : {len(all_pending)}")
            _log(f"  Errors                         : {len(all_errors)}")
            _log("===============================================")
            
            if all_pending:
                _log("\nDrafts in Approvals tab:")
                for a in all_pending:
                    draft = (a.get("payload") or {}).get("draft") or {}
                    subj = draft.get("subject") or a.get("action_type", "?")
                    to = draft.get("to", "")
                    line = f"  [{a.get('id', '?')[:8]}] {subj}"
                    if to: line += f" -> {to}"
                    _log(line)
                    
            _log(f"\n[{datetime.now().strftime('%H:%M:%S')}] Done.")
        except Exception as e:
            _log(f"\n[ERROR] {e}\n")
        finally:
            _log("```\n\n✅ **Workflow Completed!**\n")
            _log("__DONE__")
            
    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    
    return {"workflow_id": workflow_id}

@app.get("/api/approvals/{approval_id}")
def get_approval_detail(approval_id: str):
    """Return full details for a single approval entry, including parsed payload and related data."""
    import os as _os
    import json as _json
    db = _get_db()
    
    # Support short-ID prefix matching (like the old Gradio UI)
    rows = db.execute(
        "SELECT id, action_type, status, related_email_id, created_at, payload, reviewer_notes, reviewed_at "
        "FROM approval_queue WHERE id LIKE ?",
        (f"{approval_id}%",)
    )
    if not rows:
        return JSONResponse(status_code=404, content={"error": "Approval not found"})
    
    row = rows[0]
    payload_raw = row.get("payload", "{}")
    try:
        payload = _json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw
    except Exception:
        payload = {}
    
    draft = payload.get("draft") if isinstance(payload, dict) else {}
    if not isinstance(draft, dict):
        draft = {}
    
    # Fetch job info from applications table if available
    email_id = row.get("related_email_id") or payload.get("email_id")
    job_info = payload.get("job_info")
    if not job_info and email_id:
        try:
            app_rows = db.execute(
                "SELECT company, role, location, salary_range, job_description "
                "FROM applications WHERE source_email_id = ?",
                (email_id,)
            )
            if app_rows:
                job_info = dict(app_rows[0])
        except Exception:
            pass
    
    # Fetch recruiter info
    recruiter_info = payload.get("recruiter_info")
    if not recruiter_info and email_id:
        try:
            rec_rows = db.execute(
                "SELECT name, company, title, email, phone FROM recruiters "
                "WHERE id = (SELECT recruiter_id FROM emails WHERE id = ?)",
                (email_id,)
            )
            if rec_rows:
                recruiter_info = dict(rec_rows[0])
        except Exception:
            pass
    
    # Fetch original email body for context
    email_body = None
    if email_id:
        try:
            email_rows = db.execute("SELECT body_html, body_text, sender, subject, date, matched_skills FROM emails WHERE id = ?", (email_id,))
            if email_rows:
                er = email_rows[0]
                email_body = {
                    "body_html": er.get("body_html"),
                    "body_text": er.get("body_text"),
                    "sender": er.get("sender"),
                    "subject": er.get("subject"),
                    "date": er.get("date"),
                    "matched_skills": er.get("matched_skills"),
                }
        except Exception:
            pass
    
    # Check for screenshot
    full_id = row.get("id", "")
    screenshot_path = _os.path.abspath(_os.path.join(_os.getcwd(), "data", "screenshots", f"{full_id}.png"))
    has_screenshot = _os.path.exists(screenshot_path)
    
    return {
        "id": full_id,
        "action_type": row.get("action_type"),
        "status": row.get("status"),
        "related_email_id": email_id,
        "created_at": row.get("created_at"),
        "reviewer_notes": row.get("reviewer_notes"),
        "reviewed_at": row.get("reviewed_at"),
        "draft": draft,
        "classification": payload.get("classification"),
        "job_info": job_info,
        "recruiter_info": recruiter_info,
        "apply_url": payload.get("apply_url"),
        "email_sender": payload.get("email_sender"),
        "email_subject": payload.get("email_subject"),
        "email_body": email_body,
        "generation_reasoning": draft.get("generation_reasoning") or payload.get("generation_reasoning"),
        "suggested_resume": draft.get("suggested_resume") or payload.get("suggested_resume"),
        "suggested_cover_letter": draft.get("suggested_cover_letter") or payload.get("suggested_cover_letter"),
        "has_screenshot": has_screenshot,
        "screenshot_url": f"/api/approvals/screenshot/{full_id}" if has_screenshot else None,
        "matched_skills": payload.get("matched_skills") or (email_body.get("matched_skills") if email_body else None),
    }

from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    approval_id: str | None = None

class StartReviewRequest(BaseModel):
    approval_id: str
    type: str

from fastapi.responses import JSONResponse, StreamingResponse


@app.get("/api/chat/logs/{approval_id}")
def get_logs(approval_id: str, offset: int = 0):
    logs = PORTAL_LOGS.get(approval_id, [])
    # filter out __DONE__ from actual text, we just use it as a marker
    return {"logs": logs[offset:], "done": "__DONE__" in logs}

@app.post("/api/chat/start_review")
async def start_review(req: StartReviewRequest):
    from career_tracker.services import _generate_draft_on_demand
    import time
    import asyncio
    
    if req.type == "portal":
        import json
        import threading
        from career_tracker.db.database import get_database
        from career_tracker.agents.browser_agent import run_apply_agent_sync
        from career_tracker.db.repositories.user_profile_repo import UserProfileRepository
        
        PORTAL_LOGS[req.approval_id] = ["```bash\n"]
        loop = asyncio.get_running_loop()
        
        def _log_fn(msg):
            line = msg + "\n\n"
            PORTAL_LOGS[req.approval_id].append(line)
            asyncio.run_coroutine_threadsafe(manager.broadcast(line, req.approval_id), loop)
            
        _log_fn("> Initializing Browser Automation for " + req.approval_id[:8] + "...")
        
        def _worker():
            try:
                db = get_database()
                rows = db.execute("SELECT payload FROM approval_queue WHERE id = ?", (req.approval_id,))
                if not rows:
                    _log_fn("> Error: Draft not found.")
                    return
                    
                p = json.loads(rows[0]["payload"])
                apply_url = p.get("apply_url")
                if not apply_url:
                    _log_fn("> Error: No apply URL found in this entry.")
                    return
                    
                profile = UserProfileRepository().get_default()
                _log_fn(f"> Launching browser for {apply_url}...")
                
                res = run_apply_agent_sync(apply_url, profile, headless=False, log_fn=_log_fn, app_id=req.approval_id)
                _log_fn("\n---\n")
                
                if "USER_LOGIN_REQUIRED" in str(res.get("final_result", "")):
                    _log_fn("⚠️ **Login Required**\n\nPlease log into the portal, then click **Automate Application** again!")
                else:
                    from datetime import datetime
                    from career_tracker.db.repositories.event_repo import EventRepository
                    now = datetime.utcnow().isoformat()
                    db.execute_write("UPDATE approval_queue SET status='APPROVED', reviewed_at=? WHERE id=?", (now, req.approval_id))
                    EventRepository().log("portal_applied", "approval", req.approval_id, {"via": "browser_agent"})
                    _log_fn("✅ **Application successfully submitted!**")
            except Exception as e:
                _log_fn(f"❌ **Error:** {str(e)}")
            finally:
                _log_fn("```\n")
                _log_fn("__DONE__")
                
        threading.Thread(target=_worker, daemon=True).start()
        return JSONResponse({"status": "started", "poll": True})
        
    elif req.type == "email":
        def _stream_email():
            yield "```bash\n"
            yield "> Initializing review session for " + req.approval_id[:8] + "...\n"
            time.sleep(0.4)
            yield "> Loading payload and checking draft status...\n"
            time.sleep(0.6)
            yield "> Running drafting nodes if required...\n"
            time.sleep(0.8)
            
            draft_details = _generate_draft_on_demand(req.approval_id)
            
            yield "> Generation complete.\n"
            yield "```\n\n"
            
            msg = f"I have pulled up the details for `{req.approval_id[:8]}`.\n\n---\n{draft_details}\n---\n\n*Would you like to **approve** this (type 'yes'), **edit** it (type feedback below), or **skip** it (type 'skip')?*"
            yield msg
            
        return StreamingResponse(_stream_email(), media_type="text/event-stream")

@app.post("/api/chat")
def handle_chat(req: ChatRequest):
    msg = req.message.strip().lower()
    if not req.approval_id:
        try:
            from career_tracker.services import handle_general_chat
            reply = handle_general_chat(req.message)
            return {"reply": reply, "clearReviewId": False}
        except Exception as e:
            return {"reply": f"*(Error in chat agent: {e})*", "clearReviewId": False}
        
    if msg in ("yes", "approve", "yes with cv", "approve with cv"):
        attach_cv = ("with cv" in msg)
        
        # Check if CV was automatically suggested by the AI
        import json
        from career_tracker.db.database import get_database
        db = get_database()
        rows = db.execute("SELECT payload FROM approval_queue WHERE id = ?", (req.approval_id,))
        if rows:
            p = json.loads(rows[0]["payload"]) if isinstance(rows[0]["payload"], str) else rows[0]["payload"]
            suggested = p.get("suggested_resume") or p.get("draft", {}).get("suggested_resume")
            if suggested:
                attach_cv = True
                
        from career_tracker.services import _send_approval_immediately
        res = _send_approval_immediately(req.approval_id, attach_cv=attach_cv)
        return {"reply": res, "clearReviewId": True}
        
    if msg == "skip":
        return {"reply": "Skipped. You can select another item.", "clearReviewId": True}
        
    # Check action type
    import json
    from career_tracker.db.database import get_database
    db = get_database()
    rows = db.execute("SELECT action_type, payload FROM approval_queue WHERE id = ?", (req.approval_id,))
    if rows:
        action_type = rows[0]["action_type"]
        p = json.loads(rows[0]["payload"]) if isinstance(rows[0]["payload"], str) else rows[0]["payload"]
        
        if action_type == "agent_apply":
            from career_tracker.agents.browser_agent import HUMAN_WAIT_EVENTS
            if req.approval_id in HUMAN_WAIT_EVENTS:
                HUMAN_WAIT_EVENTS[req.approval_id].set()
                return {"reply": "✅ Received your confirmation! The agent will now continue the application process.", "clearReviewId": False}
                
            import re
            urls = re.findall(r"https?://[^\s<>\"'\]\)]+", req.message)
            if urls:
                url = urls[0]
                p["apply_url"] = url
                db.execute_write("UPDATE approval_queue SET payload=? WHERE id=?", (json.dumps(p), req.approval_id))
                return {"reply": f"✅ I've updated the Apply URL to `{url}`.\n\nPlease click **Automate Application** again to run the browser agent!", "clearReviewId": False}
            return {"reply": "⚠️ This is a Portal Application automation task, not an email draft.\n\nIf the Apply URL was missing, please **paste the direct Apply URL** here so I can retry. Or type 'skip' to ignore this application.", "clearReviewId": False}
        
    from career_tracker.services import _rewrite_draft_with_feedback
    res = _rewrite_draft_with_feedback(req.approval_id, req.message)
    return {"reply": f"Here is the updated draft based on your feedback:\n\n{res}", "clearReviewId": False}

from pydantic import BaseModel

class SettingsRequest(BaseModel):
    api_key: str
    api_base: str
    model: str
    poll_interval: str
    cache_ttl: str = "60"

class ProfileRequest(BaseModel):
    name: str
    email: str
    phone: str
    linkedin_url: str
    github_url: str
    portfolio_url: str
    skills: str
    target_roles: str

class GmailAuthRequest(BaseModel):
    email: str

@app.get("/api/settings/gmail/accounts")
def get_gmail_accounts():
    from career_tracker.mcp_servers.gmail_server import get_all_authenticated_accounts
    accounts = get_all_authenticated_accounts()
    return {"accounts": accounts}

@app.post("/api/settings/gmail/auth")
def auth_gmail_account(req: GmailAuthRequest):
    """Authenticate Gmail via Google OAuth2 flow using InstalledAppFlow."""
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from pathlib import Path
    from career_tracker.config import get_settings
    import os
    
    email_addr = req.email.strip()
    if not email_addr:
        return JSONResponse(status_code=400, content={"error": "Gmail address is required."})
        
    settings = get_settings()
    creds_path = settings.resolve_path(settings.gmail_credentials_path)
    scopes = settings.gmail_scopes
    
    if not creds_path.exists():
        return JSONResponse(
            status_code=400, 
            content={
                "error": f"Missing credentials.json at {creds_path}. "
                         f"Please download the OAuth 2.0 Client credentials JSON file from your Google Cloud Console "
                         f"and save it as 'credentials.json' inside the 'data' directory."
            }
        )
        
    try:
        import json
        with open(creds_path, 'r') as f:
            creds_data = json.load(f)
        
        is_web = "web" in creds_data
        auth_port = 8080 if is_web else 0
        
        flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), scopes)
        
        # Monkeypatch webbrowser.get and webbrowser.open to force Google Chrome on macOS
        import webbrowser
        import subprocess
        
        orig_open = webbrowser.open
        orig_get = webbrowser.get
        
        class ChromeController:
            def open(self, url, new=0, autoraise=True):
                for app in ["Google Chrome", "/Applications/Google Chrome.app"]:
                    try:
                        subprocess.run(["open", "-a", app, url], check=True)
                        print(f"Successfully opened OAuth URL in Chrome using: {app}")
                        return True
                    except Exception as e:
                        print(f"Failed to open Chrome using {app}: {e}")
                print("Falling back to default system browser...")
                return orig_open(url, new, autoraise)
                
        def custom_get(name=None):
            return ChromeController()
            
        webbrowser.open = lambda url, *args, **kwargs: ChromeController().open(url)
        webbrowser.get = custom_get
        try:
            # We pass login_hint to prefill the email and prompt='consent' to ensure we get a refresh token
            creds = flow.run_local_server(port=auth_port, login_hint=email_addr, prompt='consent')
        finally:
            webbrowser.open = orig_open
            webbrowser.get = orig_get
        
        # Build service to verify the email address
        temp_service = build("gmail", "v1", credentials=creds)
        profile = temp_service.users().getProfile(userId="me").execute()
        authenticated_email = profile.get("emailAddress")
        
        if not authenticated_email:
            return JSONResponse(status_code=500, content={"error": "Could not extract email address from Google Profile."})
            
        # Save token with the authenticated email address
        tokens_dir = settings.resolve_path(Path("data/tokens"))
        tokens_dir.mkdir(parents=True, exist_ok=True)
        token_path = tokens_dir / f"{authenticated_email}.json"
        token_path.write_text(creds.to_json())
        
        # Update .env settings for the main email
        env_path = Path.cwd() / '.env'
        if env_path.exists():
            lines = env_path.read_text().splitlines()
            new_lines = []
            updated_keys = set()
            updates = {'GMAIL_EMAIL': authenticated_email}
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith('#') and '=' in stripped:
                    k, _, _ = stripped.partition('=')
                    k = k.strip()
                    if k in updates:
                        new_lines.append(f'{k}={updates[k]}')
                        updated_keys.add(k)
                        continue
                new_lines.append(line)
            for k, v in updates.items():
                if k not in updated_keys:
                    new_lines.append(f'{k}={v}')
            env_path.write_text('\n'.join(new_lines) + '\n')
            
        os.environ['GMAIL_EMAIL'] = authenticated_email
        
        return {"status": "success", "email": authenticated_email}
        
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"OAuth Authentication failed: {str(e)}"})

@app.get("/api/settings/gmail/status")
def get_gmail_status():
    """Check if Gmail credentials are configured."""
    from career_tracker.mcp_servers.gmail_server import get_all_authenticated_accounts
    accounts = get_all_authenticated_accounts()
    import os
    gmail_email = os.getenv('GMAIL_EMAIL', '')
    
    if accounts:
        return {"configured": True, "email": gmail_email or accounts[0]}
    return {"configured": False, "email": None}

@app.get("/api/settings/linkedin/status")
def get_linkedin_status():
    from career_tracker.services import _get_db
    import os
    
    db = _get_db()
    rows = db.execute("SELECT created_at FROM events WHERE event_type = 'linkedin_auth' ORDER BY created_at DESC LIMIT 1")
    last_auth = rows[0]["created_at"] if rows else None
    
    profile_path = os.path.abspath(os.path.join(os.getcwd(), "data", "ai_agent_profile"))
    has_profile = os.path.exists(profile_path)
    
    if last_auth and has_profile:
        return {"status": "connected", "last_connected": last_auth}
    return {"status": "disconnected"}

def _find_chrome_path():
    import os
    import sys
    
    if sys.platform == "win32":
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
        ]
        for cp in chrome_paths:
            if os.path.exists(cp):
                return cp
    elif sys.platform == "darwin":
        chrome_paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        ]
        for cp in chrome_paths:
            if os.path.exists(cp):
                return cp
    else: # Linux
        chrome_paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/chrome"
        ]
        for cp in chrome_paths:
            if os.path.exists(cp):
                return cp
    return None

@app.post("/api/settings/linkedin/auth")
def auth_linkedin():
    exec_path = _find_chrome_path()
    if not exec_path:
        return JSONResponse(status_code=500, content={"error": "Google Chrome executable was not found. Please install Chrome."})
        
    import threading
    def _run_browser():
        try:
            import os
            import subprocess
            import sys
            import time
            profile_path = os.path.abspath(os.path.join(os.getcwd(), "data", "ai_agent_profile"))
            os.makedirs(profile_path, exist_ok=True)
            
            # Clean up lingering processes using this profile
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], capture_output=True)
            else:
                subprocess.run(["pkill", "-f", "data/ai_agent_profile"], capture_output=True)
            time.sleep(0.5)
            
            # Launch Chrome natively (bypasses Playwright's automation detection)
            if sys.platform == "darwin":
                # Use macOS native 'open' command with --args and -W to wait for close
                proc = subprocess.Popen([
                    "open", "-W", "-na", "Google Chrome", "--args",
                    f"--user-data-dir={profile_path}",
                    "--disable-infobars",
                    "--no-first-run",
                    "https://www.linkedin.com/login"
                ])
            else:
                proc = subprocess.Popen([
                    exec_path,
                    f"--user-data-dir={profile_path}",
                    "--disable-infobars",
                    "--no-first-run",
                    "https://www.linkedin.com/login"
                ])
            
            # Wait for user to log in and close the browser manually
            proc.wait()
            
            from career_tracker.db.repositories.event_repo import EventRepository
            EventRepository().log(
                event_type="linkedin_auth",
                entity_type="auth",
                entity_id="linkedin",
                data={"status": "success"}
            )
            
        except Exception as e:
            print(f"LinkedIn auth process failed: {e}")
            
    t = threading.Thread(target=_run_browser, daemon=True)
    t.start()
    
    return {"status": "started", "message": "A standard Chrome window has been opened for you to log in securely. Once you log in, simply CLOSE the window to save your session!"}

@app.post("/api/settings/linkedin/open")
def open_linkedin():
    try:
        import os
        import subprocess
        import sys
        import time
        profile_path = os.path.abspath(os.path.join(os.getcwd(), "data", "ai_agent_profile"))
        os.makedirs(profile_path, exist_ok=True)
        
        exec_path = _find_chrome_path()
        if not exec_path:
            return JSONResponse(status_code=500, content={"error": "Google Chrome executable was not found. Please install Chrome."})
            
        # Clean up lingering processes using this profile
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], capture_output=True)
        else:
            subprocess.run(["pkill", "-f", "data/ai_agent_profile"], capture_output=True)
        time.sleep(0.5)
            
        # Launch Chrome natively, do not wait for it
        if sys.platform == "darwin":
            subprocess.Popen([
                "open", "-na", "Google Chrome", "--args",
                f"--user-data-dir={profile_path}",
                "--disable-infobars",
                "--no-first-run",
                "https://www.linkedin.com/feed/"
            ])
        else:
            subprocess.Popen([
                exec_path,
                f"--user-data-dir={profile_path}",
                "--disable-infobars",
                "--no-first-run",
                "https://www.linkedin.com/feed/"
            ])
        
        return {"status": "success"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/quota")
def get_quota():
    from career_tracker.services import _get_db
    import json
    from datetime import datetime
    
    db = _get_db()
    
    total_tokens = 0
    total_cost = 0.0

    try:
        # Calculate lifetime usage (permanent retention)
        rows = db.execute(
            "SELECT data FROM events WHERE event_type = 'llm_api_usage'"
        )
        
        for row in rows:
            try:
                data = json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]
                total_tokens += data.get("total_tokens", 0)
                total_cost += data.get("cost", 0.0)
            except Exception:
                pass
    except Exception as e:
        print(f"Error fetching quota: {e}")
            
    return {
        "tokens_total": total_tokens,
        "cost_total": total_cost
    }

@app.get("/api/settings")
def get_settings_endpoint():
    from career_tracker.services import load_settings
    key, base, model, poll, cache_ttl, msg = load_settings()
    return {"api_key": key, "api_base": base, "model": model, "poll_interval": poll, "cache_ttl": cache_ttl, "message": msg}

@app.post("/api/settings")
def update_settings_endpoint(req: SettingsRequest):
    from career_tracker.services import save_settings
    msg = save_settings(req.api_key, req.api_base, req.model, req.poll_interval, req.cache_ttl)
    return {"status": "success", "message": msg}

@app.get("/api/settings/llm/status")
def get_llm_status():
    """Check if the configured LLM API is reachable and returns connection status."""
    from career_tracker.config import get_settings
    from openai import OpenAI
    import httpx
    
    settings = get_settings()
    api_key = settings.openai_api_key or "ollama"
    api_base = settings.openai_api_base or "http://localhost:11434/v1"
    model = settings.llm_model or "llama3.2:3b"
    
    is_ollama = "localhost" in api_base or "127.0.0.1" in api_base or "ollama" in api_key.lower()
    
    try:
        # Check connection using a short timeout (e.g. 2.0 seconds)
        client = OpenAI(api_key=api_key, base_url=api_base, http_client=httpx.Client(timeout=2.0))
        
        # Test model connection or listing models
        models = client.models.list()
        model_names = [m.id for m in models.data]
        
        connected = model in model_names or any(model in name for name in model_names)
        
        provider = "Ollama (Local)" if is_ollama else "OpenAI / Remote Compatible"
        if is_ollama:
            status_msg = f"Connected locally to Ollama running model: {model}" if connected else f"Connected to Ollama, but model '{model}' not found locally (available: {', '.join(model_names)})"
        else:
            status_msg = f"Connected to remote LLM provider running model: {model}"
            
        return {
            "connected": True,
            "provider": provider,
            "model": model,
            "available_models": model_names,
            "status_message": status_msg
        }
    except Exception as e:
        return {
            "connected": False,
            "provider": "Ollama (Local)" if is_ollama else "OpenAI / Remote Compatible",
            "model": model,
            "status_message": f"Connection failed: {str(e)}"
        }

@app.get("/api/profile")
def get_profile_endpoint():
    try:
        from career_tracker.db.repositories.user_profile_repo import UserProfileRepository
        profile = UserProfileRepository().get_default()
        return {"profile": profile}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/profile")
def update_profile_endpoint(req: ProfileRequest):
    from career_tracker.services import save_profile
    msg = save_profile(
        name=req.name,
        email=req.email,
        phone=req.phone,
        linkedin=req.linkedin_url,
        github=req.github_url,
        portfolio=req.portfolio_url,
        skills_str=req.skills,
        roles_str=req.target_roles
    )
    return {"status": "success", "message": msg}

@app.get("/api/setup/status")
def get_setup_status_endpoint():
    from career_tracker.services import check_setup
    status_text = check_setup()
    return {"status_text": status_text}

from fastapi import UploadFile, File
import shutil
import tempfile
import os

@app.post("/api/upload/cv")
async def upload_cv_endpoint(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks()):
    from career_tracker.services import handle_cv_upload
    # Save the uploaded file to a temporary location
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
            
        res = handle_cv_upload(tmp_path, background_tasks)
        os.unlink(tmp_path)
        return res
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/cv/status")
def get_cv_status_endpoint():
    from career_tracker.services import load_cv_status
    status_text = load_cv_status()
    return {"status_text": status_text}

@app.post("/api/upload/profile")
async def upload_profile_endpoint(file: UploadFile = File(...)):
    from career_tracker.services import handle_profile_upload
    try:
        # Save uploaded file to temp location
        suffix = os.path.splitext(file.filename)[1] if file.filename else ".txt"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
            
        _, msg, _ = handle_profile_upload(tmp_path)
        os.unlink(tmp_path)
        
        if "Error" in msg:
            return JSONResponse(status_code=400, content={"error": msg})
        return {"status": "success", "message": msg}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/memory")
def get_memory_stats():
    from career_tracker.memory.store import get_memory_store, _ALL_COLLECTIONS
    store = get_memory_store()
    stats = []
    for coll in _ALL_COLLECTIONS:
        try:
            count = store.count(coll)
        except Exception:
            count = 0
        stats.append({
            "name": coll,
            "count": count
        })
    return {"collections": stats}

@app.get("/api/memory/graph")
def get_memory_graph():
    from career_tracker.memory.graph_builder import build_knowledge_graph
    try:
        graph = build_knowledge_graph()
        return {"graph": graph}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "Error building memory graph"})

@app.get("/api/memory/{collection_name}")
def get_memory_items(collection_name: str, limit: int = 15):
    from career_tracker.memory.store import get_memory_store
    store = get_memory_store()
    try:
        coll = store._get_collection(collection_name)
        data = coll.get(limit=limit)
        
        items = []
        if data and data.get("ids"):
            for i in range(len(data["ids"])):
                items.append({
                    "id": data["ids"][i],
                    "content": data["documents"][i] if "documents" in data and data["documents"] else None,
                    "metadata": data["metadatas"][i] if "metadatas" in data and data["metadatas"] else None
                })
        return {"items": items}
    except Exception as e:
        return {"error": str(e)}

class PreferenceRequest(BaseModel):
    content: str
    category: str = "general"

@app.post("/api/memory/{collection_name}")
def add_memory_item(collection_name: str, req: PreferenceRequest):
    import uuid
    from career_tracker.memory.store import get_memory_store, _ALL_COLLECTIONS
    if collection_name not in _ALL_COLLECTIONS:
        return JSONResponse(status_code=400, content={"error": "Invalid collection name"})

    store = get_memory_store()
    doc_id = str(uuid.uuid4())
    try:
        store.save(
            collection=collection_name,
            doc_id=doc_id,
            content=req.content,
            metadata={"category": req.category, "source": "manual_entry"}
        )
        return {"status": "success", "id": doc_id}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# --- LinkedIn Intel Endpoints ---

INTEL_AUTOSCROLL = False

@app.post("/api/intel/start")
async def start_intel_session(target: str = "feed"):
    try:
        import os
        import subprocess
        import sys
        import time
        import asyncio
        import json
        import urllib.request
        import websockets
        
        profile_path = os.path.abspath(os.path.join(os.getcwd(), "data", "ai_agent_profile"))
        os.makedirs(profile_path, exist_ok=True)
        ext_paths = [
            os.path.abspath(os.path.join(os.getcwd(), "linkedin_intel_ext")),
            os.path.abspath(os.path.join(os.getcwd(), "linkedin_jobs_ext"))
        ]
        
        exec_path = _find_chrome_path()
                
        if not exec_path:
            return JSONResponse(status_code=500, content={"error": "Chrome not found"})
            
        # Ensure any lingering Chrome processes are killed so the extension reloads fresh
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], capture_output=True)
        else:
            subprocess.run(["pkill", "-f", "data/ai_agent_profile"], capture_output=True)
        time.sleep(1) # Give it a second to clean up
            
        target_url = "https://www.linkedin.com/jobs/search/" if target == "jobs" else "https://www.linkedin.com/feed/"
            
        # Launch Chrome with remote debugging and unsafe extension debugging enabled
        if sys.platform == "win32":
            # Build exact command line string to bypass subprocess list quoting issues on Windows
            cmd = f'"{exec_path}" --user-data-dir="{profile_path}" --enable-unsafe-extension-debugging --disable-infobars --disable-web-security --disable-site-isolation-trials --no-first-run --remote-debugging-port=9333 "{target_url}"'
            subprocess.Popen(cmd, shell=True)
        else:
            cmd = [
                exec_path,
                f"--user-data-dir={profile_path}",
                "--enable-unsafe-extension-debugging",
                "--disable-infobars",
                "--disable-web-security",
                "--disable-site-isolation-trials",
                "--no-first-run",
                "--remote-debugging-port=9333",
                target_url
            ]
            chrome_log_path = os.path.join(os.getcwd(), "data", "chrome_launch.log")
            log_file = open(chrome_log_path, "w")
            subprocess.Popen(cmd, stdout=log_file, stderr=log_file)
        
        # Programmatically load the unpacked extensions via CDP
        browser_ws_url = None
        for _ in range(25):
            try:
                req = urllib.request.urlopen("http://localhost:9333/json/version", timeout=0.5)
                version_data = json.loads(req.read().decode())
                browser_ws_url = version_data["webSocketDebuggerUrl"]
                break
            except Exception:
                await asyncio.sleep(0.2)
                
        if not browser_ws_url:
            return JSONResponse(status_code=500, content={"error": "Failed to connect to Chrome remote debugging port"})
            
        try:
            async with websockets.connect(browser_ws_url) as ws:
                for idx, path in enumerate(ext_paths):
                    load_cmd = {
                        "id": idx + 1,
                        "method": "Extensions.loadUnpacked",
                        "params": {
                            "path": path
                        }
                    }
                    await ws.send(json.dumps(load_cmd))
                    resp = await ws.recv()
                    resp_data = json.loads(resp)
                    print(f"CDP load {os.path.basename(path)} response: {resp_data}", flush=True)
                    if "error" in resp_data:
                        ext_name = os.path.basename(path)
                        return JSONResponse(status_code=500, content={"error": f"Failed to load extension {ext_name} via CDP: {resp_data['error']}"})
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f"Error loading extensions via CDP: {str(e)}"})
        
        return {"status": "success"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

class IntelPostRequest(BaseModel):
    id: str
    author: str
    text_content: str
    is_job_opportunity: int
    url: str
    matched_skills: list[str] = []

@app.post("/api/intel/dump")
async def receive_dump(req: Request):
    body = await req.body()
    with open("linkedin_dump.html", "wb") as f:
        f.write(body)
    return {"status": "success"}

@app.post("/api/intel/posts")
def save_intel_post(req: IntelPostRequest):
    from career_tracker.services import _get_db
    import json
    db = _get_db()
    try:
        skills_json = json.dumps(req.matched_skills) if req.matched_skills else None
        db.execute_write(
            "INSERT OR IGNORE INTO intel_posts (id, author, text_content, is_job_opportunity, url, matched_skills) VALUES (?, ?, ?, ?, ?, ?)",
            (req.id, req.author, req.text_content, req.is_job_opportunity, req.url, skills_json)
        )
        return {"status": "success"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/intel/posts")
def get_intel_posts(limit: int = 100):
    from career_tracker.services import _get_db
    db = _get_db()
    try:
        rows = db.execute("SELECT * FROM intel_posts ORDER BY created_at DESC LIMIT ?", (limit,))
        return {"posts": rows}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/intel/jobs/{job_id}/draft_email")
def draft_email_from_linkedin_job(job_id: str):
    from career_tracker.services import _create_draft_from_linkedin_job
    try:
        res = _create_draft_from_linkedin_job(job_id)
        return res
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/intel/posts/purge")
def purge_intel_posts():
    from career_tracker.services import _get_db
    db = _get_db()
    try:
        db.execute_write("DELETE FROM intel_posts WHERE created_at < datetime('now', '-7 days')")
        return {"status": "success", "message": "Scraped posts older than 7 days purged successfully."}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/intel/autoscroll/toggle")
def toggle_intel_autoscroll():
    global INTEL_AUTOSCROLL
    INTEL_AUTOSCROLL = not INTEL_AUTOSCROLL
    return {"status": "active" if INTEL_AUTOSCROLL else "inactive"}

@app.get("/api/intel/autoscroll/status")
def get_intel_autoscroll_status():
    return {"status": "active" if INTEL_AUTOSCROLL else "inactive"}

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True, reload_dirs=["src"])


@app.get("/api/intel/skill-gap")
def get_skill_gap():
    from career_tracker.services import _get_db
    import json
    from collections import Counter
    
    db = _get_db()
    
    # Get user skills
    user_rows = db.execute("SELECT skills FROM user_profiles LIMIT 1")
    user_skills = []
    if user_rows and user_rows[0].get("skills"):
        try:
            user_skills = json.loads(user_rows[0]["skills"])
            user_skills = [s.lower().strip() for s in user_skills]
        except:
            pass
            
    # Get all matched skills from intel_posts
    intel_rows = db.execute("SELECT matched_skills FROM intel_posts WHERE matched_skills IS NOT NULL")
    
    all_demanded = []
    for r in intel_rows:
        try:
            skills = json.loads(r["matched_skills"])
            for s in skills:
                all_demanded.append(s.strip())
        except:
            pass
            
    # Also fetch from emails if they have matched_skills (optional, let's include it)
    email_rows = db.execute("SELECT matched_skills FROM emails WHERE matched_skills IS NOT NULL AND matched_skills != '[]'")
    for r in email_rows:
        try:
            skills = json.loads(r["matched_skills"])
            for s in skills:
                all_demanded.append(s.strip())
        except:
            pass
            
    counter = Counter(all_demanded)
    top_skills = counter.most_common(15)
    
    results = []
    for skill, count in top_skills:
        has_skill = skill.lower() in user_skills
        results.append({
            "skill": skill,
            "demand": count,
            "has_skill": has_skill
        })
        
    return {"skill_gap": results}
