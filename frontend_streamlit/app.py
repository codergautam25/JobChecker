import os
import sys
import streamlit as st
import json
import requests
import subprocess
from datetime import datetime

# Set page config first
st.set_page_config(
    page_title="AgenticJobFlow: Local AI Job Search & Application Agent",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Set python path to find backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import (
    get_latest_profile, get_all_jobs, get_pending_drafts, 
    update_draft, update_job_status, init_db, insert_job
)
from backend.agents.parser import process_and_index_resume
from backend.agents.scraper import JobScraper
from backend.agents.gmail_daemon import check_gmail_imap
from backend.agents.orchestrator import process_scraped_job
from backend.agents.submitter import auto_submit_application

# Initialize SQLite database
init_db()

# Load Custom CSS
css_path = os.path.join(os.path.dirname(__file__), "style.css")
if os.path.exists(css_path):
    with open(css_path, "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Helper function to check connection statuses
def check_linkedin_auth_status():
    session_dir = os.getenv("PLAYWRIGHT_USER_DATA_DIR", "./.playwright_session")
    if os.path.exists(session_dir) and os.path.isdir(session_dir):
        # Check if contains any files or cookies
        files = os.listdir(session_dir)
        if len(files) > 0:
            return True
    return False

def check_gmail_auth_status():
    gmail = os.getenv("GMAIL_EMAIL", "")
    password = os.getenv("GMAIL_APP_PASSWORD", "")
    if gmail and password and "your_email" not in gmail and "your_app_password" not in password:
        return True
    return False

# ----------------- SIDEBAR -----------------
st.sidebar.markdown('<h2 class="grad-text">AgenticJobFlow</h2>', unsafe_allow_html=True)
st.sidebar.caption("v1.0 (Local-First Agent)")

# Sidebar Navigation Selector under App Name
nav_selection = st.sidebar.radio(
    "Navigation Menu",
    options=[
        "🎯 Intel Feed", 
        "✉️ Recruiter Inbox", 
        "📋 Approvals Kanban", 
        "📄 Resume & Profile",
        "🔄 Sync & Integrations",
        "🤖 Career Assistant",
        "⚙️ Settings & System"
    ],
    label_visibility="collapsed"
)

st.sidebar.markdown("---")

# Display active context in the sidebar
current_profile = get_latest_profile()
if current_profile:
    st.sidebar.markdown(
        f"""
        <div style="background-color:rgba(46, 204, 113, 0.08); border: 1px solid rgba(46, 204, 113, 0.2); padding:12px; border-radius:10px; margin-bottom:15px;">
            <p style="margin:0; font-size:0.8rem; font-weight:600; color:#2ecc71; text-transform:uppercase; letter-spacing:0.5px;">Candidate Profile</p>
            <p style="margin:6px 0 0 0; font-size:0.9rem; font-family:monospace; color:#e5e9f0; font-weight:500;">{current_profile['filename']}</p>
        </div>
        """,
        unsafe_allow_html=True
    )
else:
    st.sidebar.markdown(
        """
        <div style="background-color:rgba(241, 196, 15, 0.08); border: 1px solid rgba(241, 196, 15, 0.2); padding:12px; border-radius:10px; margin-bottom:15px;">
            <p style="margin:0; font-size:0.8rem; font-weight:600; color:#f1c40f; text-transform:uppercase; letter-spacing:0.5px;">Candidate Profile</p>
            <p style="margin:6px 0 0 0; font-size:0.9rem; color:#e5e9f0; font-weight:500;">No resume context uploaded.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

# Connection Badges in Sidebar
st.sidebar.markdown("### 🔌 Integrations State")
linkedin_ok = check_linkedin_auth_status()
gmail_ok = check_gmail_auth_status()

if linkedin_ok:
    st.sidebar.markdown('🟢 **LinkedIn:** <span style="color:#2ecc71; font-weight:600;">Active Session</span>', unsafe_allow_html=True)
else:
    st.sidebar.markdown('🟡 **LinkedIn:** <span style="color:#f1c40f; font-weight:600;">Unauthenticated</span>', unsafe_allow_html=True)
    
if gmail_ok:
    st.sidebar.markdown('🟢 **Gmail IMAP:** <span style="color:#2ecc71; font-weight:600;">Configured</span>', unsafe_allow_html=True)
else:
    st.sidebar.markdown('🔴 **Gmail IMAP:** <span style="color:#e74c3c; font-weight:600;">Unconfigured</span>', unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.caption("Privacy Mode: 100% Local (SQLite + Chroma)")

# ----------------- MAIN PANEL -----------------
st.markdown('<h1 class="grad-text">AI-Driven Job Search & Application Agent</h1>', unsafe_allow_html=True)
st.markdown("Absolute privacy job hunting. Powered by local LLMs (Ollama), vector embeddings (ChromaDB), and Playwright workflow automation.")
st.markdown("---")

# ----------------- 1. INTEL FEED TAB -----------------
if nav_selection == "🎯 Intel Feed":
    st.subheader("Market Intelligence & Scraped Job Openings")
    
    all_jobs = get_all_jobs()
    review_jobs = [j for j in all_jobs if j["status"] in ["scraped", "matched"]]
    
    if not review_jobs:
        st.markdown(
            """
            <div class="glass-card" style="text-align: center; padding: 45px 20px;">
                <h4 style="margin:0 0 10px 0;">No new leads in Intel Feed</h4>
                <p style="color:#b2bec3; margin:0;">Configure keywords and run the scraper in **Sync & Integrations** to populate openings.</p>
            </div>
            """, 
            unsafe_allow_html=True
        )
    else:
        for job in review_jobs:
            tier = job.get("probability_tier", "Low")
            pct = job.get("match_percentage", 0)
            
            if tier == "High":
                pill_html = f'<span class="pill pill-high">High Fit ({pct}%)</span>'
            elif tier == "Medium":
                pill_html = f'<span class="pill pill-medium">Medium Fit ({pct}%)</span>'
            else:
                pill_html = f'<span class="pill pill-low">Low Fit ({pct}%)</span>'
                
            skill_gaps_list = []
            if job.get("skill_gaps"):
                try:
                    skill_gaps_list = json.loads(job["skill_gaps"])
                except Exception:
                    skill_gaps_list = [g.strip() for g in job["skill_gaps"].split(",")]
                    
            gaps_html = ""
            if skill_gaps_list:
                gaps_html = " ".join([f'<code class="gap-badge">{g}</code>' for g in skill_gaps_list])
            else:
                gaps_html = '<span style="color:#2ecc71; font-size:0.9rem;">No gaps identified</span>'
                
            col_left, col_right = st.columns([4, 1])
            
            with col_left:
                st.markdown(
                    f"""
                    <div class="glass-card">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                            <h3 style="margin:0; font-size:1.3rem; font-weight:600;">{job['title']}</h3>
                            {pill_html}
                        </div>
                        <h4 style="margin:0 0 10px 0; font-size:1.0rem; color:#0984e3; font-weight:500;">{job['company']}</h4>
                        <p style="font-size:0.88rem; color:#b2bec3; margin-bottom:12px; line-height:1.5;">{job['description'][:280]}...</p>
                        <div style="font-size:0.85rem; margin-top:8px;">
                            <strong>Skill Gaps:</strong> {gaps_html}
                        </div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
            
            with col_right:
                st.write("") # Spacer
                st.write("")
                st.link_button("View Original", job["deep_link"], use_container_width=True)
                
                if st.button("Auto-Apply", key=f"intel_apply_{job['id']}", use_container_width=True, type="primary"):
                    if not current_profile:
                        st.error("Please upload a resume first.")
                    else:
                        with st.spinner("Playwright completing application form..."):
                            temp_resume_path = os.path.abspath(f"./.temp_uploads/{current_profile['filename']}")
                            success = auto_submit_application(
                                job_id=job["id"],
                                resume_file_path=temp_resume_path
                            )
                            if success:
                                st.success("Applied successfully!")
                                st.rerun()
                            else:
                                st.error("Automation form fill failed. Check browser logs.")
                                
                if st.button("Ignore Lead", key=f"intel_ignore_{job['id']}", use_container_width=True):
                    update_job_status(job["id"], "ignored")
                    st.rerun()
            st.markdown(" ")

# ----------------- 2. RECRUITER INBOX TAB -----------------
if nav_selection == "✉️ Recruiter Inbox":
    st.subheader("Response Autodraft & Outreach Review")
    
    pending_drafts = get_pending_drafts()
    
    if not pending_drafts:
        st.markdown(
            """
            <div class="glass-card" style="text-align: center; padding: 45px 20px;">
                <h4 style="margin:0 0 10px 0;">Inbox Clean</h4>
                <p style="color:#b2bec3; margin:0;">Recruitment emails detected via Gmail Sync will populate here with responses.</p>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        for draft in pending_drafts:
            st.markdown(
                f"""
                <div class="glass-card" style="border-left: 4px solid #00cec9; padding-left: 15px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                        <span style="font-weight:600; font-size:1.15rem; color:#00cec9;">{draft['job_company']}</span>
                        <span style="font-size:0.8rem; color:#636e72;">{draft['created_at']}</span>
                    </div>
                    <div style="font-size:0.9rem; margin-bottom:12px; color:#b2bec3;">
                        <strong>Position:</strong> {draft['job_title']} | 
                        <strong>Recruiter:</strong> <code>{draft['recipient_email']}</code>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            
            subject_input = st.text_input("Subject", draft["subject"], key=f"inbox_subj_{draft['id']}")
            body_input = st.text_area("Response Email Draft", draft["body"], key=f"inbox_body_{draft['id']}", height=180)
            
            col_approve, col_discard = st.columns([1, 1])
            
            with col_approve:
                if st.button("Approve & Send", key=f"inbox_appr_{draft['id']}", use_container_width=True, type="primary"):
                    update_draft(draft["id"], subject_input, body_input, status="approved")
                    st.success("Draft approved! Transmitted.")
                    st.rerun()
            with col_discard:
                if st.button("Discard Response", key=f"inbox_disc_{draft['id']}", use_container_width=True):
                    update_draft(draft["id"], subject_input, body_input, status="discarded")
                    st.rerun()
            st.markdown("---")

# ----------------- 3. APPROVALS KANBAN TAB -----------------
if nav_selection == "📋 Approvals Kanban":
    st.subheader("Approvals Kanban Board")
    st.caption("Manage application statuses. Move jobs through recruitment stages using the cards below.")
    
    jobs = get_all_jobs()
    
    matched = [j for j in jobs if j["status"] in ["matched", "scraped", "draft_generated"]]
    applied = [j for j in jobs if j["status"] == "applied"]
    interviewing = [j for j in jobs if j["status"] == "interviewing"]
    offer = [j for j in jobs if j["status"] == "offer"]
    rejected = [j for j in jobs if j["status"] == "rejected"]
    
    col_match, col_apply, col_interview, col_offer, col_reject = st.columns(5)
    
    # Column 1: Match Review
    with col_match:
        st.markdown('<div class="kanban-header match-header">📋 Match Review</div>', unsafe_allow_html=True)
        if not matched:
            st.caption("Empty")
        for j in matched:
            with st.container():
                st.markdown(
                    f"""
                    <div class="kanban-card card-match">
                        <div style="font-weight:600; font-size:0.95rem; color:#e5e9f0;">{j['title']}</div>
                        <div style="font-size:0.8rem; color:#0984e3; margin-top:2px;">{j['company']}</div>
                        <div style="font-size:0.75rem; margin-top:6px; color:#2ecc71;">Score: {j['match_percentage']}%</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Apply", key=f"kb_m_ap_{j['id']}", use_container_width=True):
                        update_job_status(j["id"], "applied")
                        st.rerun()
                with c2:
                    if st.button("Reject", key=f"kb_m_re_{j['id']}", use_container_width=True):
                        update_job_status(j["id"], "rejected")
                        st.rerun()
                st.markdown('<div style="margin-bottom:12px;"></div>', unsafe_allow_html=True)

    # Column 2: Applied
    with col_apply:
        st.markdown('<div class="kanban-header apply-header">🚀 Applied</div>', unsafe_allow_html=True)
        if not applied:
            st.caption("Empty")
        for j in applied:
            with st.container():
                st.markdown(
                    f"""
                    <div class="kanban-card card-apply">
                        <div style="font-weight:600; font-size:0.95rem; color:#e5e9f0;">{j['title']}</div>
                        <div style="font-size:0.8rem; color:#a4b0be; margin-top:2px;">{j['company']}</div>
                        <div style="font-size:0.75rem; margin-top:6px; color:#eccc68;">Status: Applied</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Interview", key=f"kb_a_in_{j['id']}", use_container_width=True):
                        update_job_status(j["id"], "interviewing")
                        st.rerun()
                with c2:
                    if st.button("Reject", key=f"kb_a_re_{j['id']}", use_container_width=True):
                        update_job_status(j["id"], "rejected")
                        st.rerun()
                st.markdown('<div style="margin-bottom:12px;"></div>', unsafe_allow_html=True)

    # Column 3: Interviewing
    with col_interview:
        st.markdown('<div class="kanban-header interview-header">🗣️ Interviewing</div>', unsafe_allow_html=True)
        if not interviewing:
            st.caption("Empty")
        for j in interviewing:
            with st.container():
                st.markdown(
                    f"""
                    <div class="kanban-card card-interview">
                        <div style="font-weight:600; font-size:0.95rem; color:#e5e9f0;">{j['title']}</div>
                        <div style="font-size:0.8rem; color:#ffa502; margin-top:2px;">{j['company']}</div>
                        <div style="font-size:0.75rem; margin-top:6px; color:#ff7f50;">Status: Screening</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Got Offer", key=f"kb_i_of_{j['id']}", use_container_width=True):
                        update_job_status(j["id"], "offer")
                        st.rerun()
                with c2:
                    if st.button("Rejected", key=f"kb_i_re_{j['id']}", use_container_width=True):
                        update_job_status(j["id"], "rejected")
                        st.rerun()
                st.markdown('<div style="margin-bottom:12px;"></div>', unsafe_allow_html=True)

    # Column 4: Offers
    with col_offer:
        st.markdown('<div class="kanban-header offer-header">🏆 Offers</div>', unsafe_allow_html=True)
        if not offer:
            st.caption("Empty")
        for j in offer:
            with st.container():
                st.markdown(
                    f"""
                    <div class="kanban-card card-offer">
                        <div style="font-weight:600; font-size:0.95rem; color:#e5e9f0;">{j['title']}</div>
                        <div style="font-size:0.8rem; color:#2ecc71; margin-top:2px;">{j['company']}</div>
                        <div style="font-size:0.75rem; margin-top:6px; color:#2ecc71; font-weight:bold;">Status: Offer Received!</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                if st.button("Archive Offer", key=f"kb_o_ar_{j['id']}", use_container_width=True):
                    update_job_status(j["id"], "applied")
                    st.rerun()
                st.markdown('<div style="margin-bottom:12px;"></div>', unsafe_allow_html=True)

    # Column 5: Rejected
    with col_reject:
        st.markdown('<div class="kanban-header reject-header">❌ Rejected</div>', unsafe_allow_html=True)
        if not rejected:
            st.caption("Empty")
        for j in rejected:
            with st.container():
                st.markdown(
                    f"""
                    <div class="kanban-card card-reject">
                        <div style="font-weight:600; font-size:0.95rem; color:#e5e9f0;">{j['title']}</div>
                        <div style="font-size:0.8rem; color:#e74c3c; margin-top:2px;">{j['company']}</div>
                        <div style="font-size:0.75rem; margin-top:6px; color:#e74c3c;">Status: Rejected</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                if st.button("Reconsider", key=f"kb_r_re_{j['id']}", use_container_width=True):
                    update_job_status(j["id"], "matched")
                    st.rerun()
                st.markdown('<div style="margin-bottom:12px;"></div>', unsafe_allow_html=True)

# ----------------- 4. RESUME & PROFILE TAB -----------------
if nav_selection == "📄 Resume & Profile":
    st.subheader("📄 Candidate Resume & Vector Context")
    st.caption("Upload your CV to parse structural components, identify gaps, and update matches.")
    
    # Injected Resume Upload
    uploaded_file_tab = st.file_uploader(
        "Choose a Resume (PDF, MD, TXT)", 
        type=["pdf", "md", "txt"],
        key="profile_tab_uploader",
        help="Reads text, computes segment embeddings, and loads profile context."
    )
    
    if uploaded_file_tab:
        # Check if the active profile in database is already this file
        is_already_active = current_profile and current_profile["filename"] == uploaded_file_tab.name
        
        # Check if we already processed it in the current session state
        is_already_processed = st.session_state.get("processed_resume") == uploaded_file_tab.name
        
        if not is_already_active and not is_already_processed:
            temp_dir = "./.temp_uploads"
            os.makedirs(temp_dir, exist_ok=True)
            file_path = os.path.join(temp_dir, uploaded_file_tab.name)
            
            with open(file_path, "wb") as f:
                f.write(uploaded_file_tab.getbuffer())
                
            with st.spinner("Extracting segments & indexing semantic chunks..."):
                try:
                    res = process_and_index_resume(file_path)
                    st.session_state["processed_resume"] = uploaded_file_tab.name
                    st.success(f"Successfully processed: **{res['filename']}**")
                    
                    # Re-run match orchestrator on existing jobs to update matching fit
                    all_jobs = get_all_jobs()
                    if all_jobs:
                        with st.spinner("Re-evaluating target fits with new profile..."):
                            for job in all_jobs:
                                process_scraped_job(job["id"])
                            st.success("Re-evaluation complete!")
                            st.rerun()
                except Exception as e:
                    st.error(f"Error parsing resume: {e}")
                
    st.markdown("---")
    
    # Active Profile Context Details
    if current_profile:
        st.markdown("### Currently Active Profile Context")
        st.markdown(
            f"""
            <div style="background-color:rgba(30, 34, 42, 0.4); border:1px solid rgba(255,255,255,0.08); padding:16px; border-radius:12px; margin-bottom:15px;">
                <strong>Filename:</strong> <code>{current_profile['filename']}</code> | 
                <strong>File Type:</strong> <code>{current_profile['file_type']}</code> | 
                <strong>Last Updated:</strong> <code>{current_profile['last_updated']}</code>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        with st.expander("Show Extracted Resume Text"):
            st.text_area("Parsed Text Context", current_profile["parsed_text"], height=350, disabled=True)
            
        st.markdown("### ChromaDB Vector Store Indexes")
        st.caption("These semantic segment chunks are checked at runtime by matching engines.")
        
        # Pull chunks from ChromaDB for display
        from backend.db.vector_store import get_resume_collection
        try:
            collection = get_resume_collection()
            results = collection.get(where={"doc_id": "resume"})
            if results and results["documents"]:
                for idx, doc in enumerate(results["documents"]):
                    st.markdown(
                        f"""
                        <div class="glass-card" style="padding:15px; margin-bottom:10px;">
                            <div style="font-weight:600; font-size:0.85rem; color:#0984e3; margin-bottom:4px;">Vector Chunk #{idx}</div>
                            <div style="font-size:0.85rem; color:#b2bec3; line-height:1.4;">{doc}</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
            else:
                st.info("No semantic chunks found in ChromaDB. Try uploading a resume PDF.")
        except Exception as e:
            st.error(f"Failed to fetch vector chunks: {e}")
    else:
        st.info("No active candidate profile. Please drag-and-drop or select your resume file above.")

# ----------------- 5. SYNC & INTEGRATIONS TAB -----------------
if nav_selection == "🔄 Sync & Integrations":
    st.subheader("🔄 Control Center: Syncing & Auth Integrations")
    st.caption("Explicit operations to hook into email inbox and automate LinkedIn portal queries.")
    st.markdown("---")
    
    col_gmail, col_linkedin = st.columns(2)
    
    # Column A: Gmail IMAP integration
    with col_gmail:
        st.markdown('<div class="glass-card" style="height: 100%;">', unsafe_allow_html=True)
        st.markdown("### 📧 Gmail Inbox Checker")
        st.caption("Checks folders for recruiter screening offers, interviews, or rejections.")
        
        if gmail_ok:
            st.markdown(
                '<div style="background-color:rgba(46,204,113,0.1); color:#2ecc71; border:1px solid rgba(46,204,113,0.3); padding:10px; border-radius:8px; font-weight:600; text-align:center; margin-bottom:15px; font-size:0.85rem;">🟢 Checks folders for recruiter screening offers, interviews, or rejections.</div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                '<div style="background-color:rgba(231,76,60,0.1); color:#e74c3c; border:1px solid rgba(231,76,60,0.3); padding:10px; border-radius:8px; font-weight:600; text-align:center; margin-bottom:15px; font-size:0.85rem;">🔴 DISCONNECTED: Missing Credentials</div>',
                unsafe_allow_html=True
            )
            
        st.write("Configure your 16-character google app password in settings to verify mailbox credentials.")
        
        st.write("")
        if st.button("Sync Gmail Inbox Now", key="sync_gmail_tab", use_container_width=True, type="primary"):
            status_container = st.empty()
            log_messages = []
            
            def log_callback(msg):
                log_messages.append(f"⏱️ {datetime.now().strftime('%H:%M:%S')} - {msg}")
                status_container.code("\n".join(log_messages))
                
            with st.spinner("Connecting and running Gmail sync operations..."):
                try:
                    emails = check_gmail_imap(status_callback=log_callback)
                    st.success(f"Sync complete! Checked inbox details successfully.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Gmail synchronization failed: {e}")
        st.markdown('</div>', unsafe_allow_html=True)
        
    # Column B: LinkedIn & Playwright portal integration
    with col_linkedin:
        st.markdown('<div class="glass-card" style="height: 100%;">', unsafe_allow_html=True)
        st.markdown("### 🔗 LinkedIn Scraper & Authentication")
        st.caption("Handles automated board queries and keeps your cookies session alive.")
        
        if linkedin_ok:
            st.markdown(
                '<div style="background-color:rgba(46,204,113,0.1); color:#2ecc71; border:1px solid rgba(46,204,113,0.3); padding:8px; border-radius:6px; font-weight:600; text-align:center; margin-bottom:15px;">SESSION ACTIVE: Persistent Cookies Found</div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                '<div style="background-color:rgba(241,196,15,0.1); color:#f1c40f; border:1px solid rgba(241,196,15,0.3); padding:8px; border-radius:6px; font-weight:600; text-align:center; margin-bottom:15px;">SESSION INACTIVE: Solve login manually</div>',
                unsafe_allow_html=True
            )
            
        sync_keywords = st.text_input("Job Search Keywords", "Python Engineer", key="sync_kw")
        sync_location = st.text_input("Job Search Location", "Remote", key="sync_loc")
        
        st.write("")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if st.button("Launch LinkedIn Session", key="sync_headful", use_container_width=True):
                st.info("Browser window opening on your screen. Complete login, close the browser window, then refresh this page.")
                # Run the helper script as a subprocess using the current python executable to keep virtualenv packages
                subprocess.run([sys.executable, "backend/utils/playwright_helper.py"])
                st.success("Session saved.")
                st.rerun()
        with col_s2:
            if st.button("Sync LinkedIn Scraper", key="sync_scraper_tab", use_container_width=True, type="primary"):
                with st.spinner("Scraping job openings..."):
                    scraper = JobScraper(sync_keywords, sync_location)
                    import asyncio
                    # Use real scraper if LinkedIn session is authenticated, otherwise mock fallback
                    use_fallback = not linkedin_ok
                    asyncio.run(scraper.run(mock_fallback=use_fallback))
                    
                    # Score scraped entries
                    new_jobs = get_all_jobs(status="scraped")
                    for nj in new_jobs:
                        process_scraped_job(nj["id"])
                    st.success("Synchronized leads!")
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# ----------------- 6. CAREER ASSISTANT TAB -----------------
if nav_selection == "🤖 Career Assistant":
    st.subheader("🤖 Local Career Assistant Chatbot")
    st.caption("Ask questions about your matching jobs, profile gaps, or requests to draft application outreach responses.")
    
    # Initialize chatbot messages
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Hi Gautam! I am your Career Assistant. I have context on your active profile details, target applications, and response drafts. How can I help you today?"
            }
        ]
        
    # Render message history
    for msg in st.session_state.messages:
        role_class = "user-bubble" if msg["role"] == "user" else "assistant-bubble"
        st.markdown(
            f"""
            <div class="{role_class}">
                <strong>{'You' if msg['role'] == 'user' else 'Assistant'}:</strong><br/>
                {msg['content']}
            </div>
            """,
            unsafe_allow_html=True
        )
        
    chat_input = st.chat_input("Ask a question (e.g. 'What are my skill gaps for Vertex Corp?')")
    
    if chat_input:
        # Display user message
        st.session_state.messages.append({"role": "user", "content": chat_input})
        st.markdown(
            f"""
            <div class="user-bubble">
                <strong>You:</strong><br/>
                {chat_input}
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Build prompt context with DB information
        jobs = get_all_jobs()
        profile = get_latest_profile()
        
        db_context = f"Candidate Profile Uploaded: {profile['filename'] if profile else 'None'}\n"
        db_context += f"Total Jobs Logged: {len(jobs)}\n"
        for j in jobs:
            db_context += f"- {j['title']} at {j['company']} (Stage: {j['status']}, Fit: {j['match_percentage']}%)\n"
            
        prompt = f"""
        You are a helpful, conversational Local Career Assistant. 
        You have direct access to the database context:
        {db_context}
        
        Candidate Question: {chat_input}
        
        Provide a concise, professional answer.
        """
        
        # Call Ollama
        OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        
        assistant_reply = ""
        with st.spinner("Generating reply..."):
            try:
                response = requests.post(
                    f"{OLLAMA_BASE_URL}/api/generate",
                    json={
                        "model": OLLAMA_MODEL,
                        "prompt": prompt,
                        "stream": False
                    },
                    timeout=15
                )
                response.raise_for_status()
                assistant_reply = response.json()["response"]
            except Exception as e:
                # Local heuristic responder if Ollama is unreachable
                keywords = chat_input.lower()
                if "gap" in keywords or "skill" in keywords:
                    gaps = []
                    for j in jobs:
                        if j["skill_gaps"] and j["skill_gaps"] != "[]":
                            try:
                                gaps.extend(json.loads(j["skill_gaps"]))
                            except Exception:
                                pass
                    gaps = list(set(gaps))
                    assistant_reply = f"Based on your profile, here are the main skill gaps identified across matching opportunities: {', '.join(gaps) if gaps else 'None detected!'}"
                elif "vertex" in keywords or "corporation" in keywords:
                    vertex_jobs = [j for j in jobs if "vertex" in j["company"].lower()]
                    if vertex_jobs:
                        vj = vertex_jobs[0]
                        assistant_reply = f"For **{vj['title']}** at **Vertex Corp**, you have a **{vj['match_percentage']}%** fit. Identified gaps: `{vj['skill_gaps']}`."
                    else:
                        assistant_reply = "No listings found for Vertex Corp in the database."
                elif "how many" in keywords or "jobs" in keywords or "stage" in keywords:
                    applied_c = len([j for j in jobs if j["status"] == "applied"])
                    interview_c = len([j for j in jobs if j["status"] == "interviewing"])
                    offer_c = len([j for j in jobs if j["status"] == "offer"])
                    assistant_reply = f"You currently have **{len(jobs)}** total jobs. Stages breakdown: **{applied_c}** Applied, **{interview_c}** Interviewing, and **{offer_c}** Offers!"
                else:
                    assistant_reply = "Hi! Ollama is currently offline. Here's what I found in your local database: You have " + f"**{len(jobs)}** active job profiles tracked. Upload a resume or run the portal scraper to gather more context!"
                    
        # Update session state and refresh
        st.session_state.messages.append({"role": "assistant", "content": assistant_reply})
        st.markdown(
            f"""
            <div class="assistant-bubble">
                <strong>Assistant:</strong><br/>
                {assistant_reply}
            </div>
            """,
            unsafe_allow_html=True
        )
        st.rerun()

# ----------------- 7. SETTINGS TAB -----------------
if nav_selection == "⚙️ Settings & System":
    st.subheader("⚙️ System Configuration")
    st.caption("Customize model properties, local paths, and check logs.")
    
    # Display system path parameters
    st.markdown("### Configured Environment Properties")
    
    ollama_url_val = st.text_input("Ollama Base URL", value=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    ollama_model_val = st.text_input("Ollama LLM Model", value=os.getenv("OLLAMA_MODEL", "llama3.1:8b"))
    sqlite_db_val = st.text_input("SQLite DB Path", value=os.getenv("SQLITE_DB_PATH", "./jobchecker.db"))
    
    st.markdown("### 📧 Gmail Authentication Settings")
    st.caption("Generate a 16-character App Password in Google Account settings (Security -> 2-Step Verification -> App Passwords).")
    
    gmail_email_val = st.text_input("Gmail Address", value=os.getenv("GMAIL_EMAIL", ""))
    gmail_pwd_val = st.text_input("Gmail App Password (16 chars)", value=os.getenv("GMAIL_APP_PASSWORD", ""), type="password")
    
    # Save settings button
    if st.button("Save Environment Config"):
        # Save to current environment dynamically
        os.environ["OLLAMA_BASE_URL"] = ollama_url_val
        os.environ["OLLAMA_MODEL"] = ollama_model_val
        os.environ["SQLITE_DB_PATH"] = sqlite_db_val
        os.environ["GMAIL_EMAIL"] = gmail_email_val
        os.environ["GMAIL_APP_PASSWORD"] = gmail_pwd_val
        
        # Read existing .env to preserve structure
        env_dict = {}
        if os.path.exists(".env"):
            with open(".env", "r") as f:
                for line in f.readlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env_dict[k.strip()] = v.strip()
                        
        # Merge updates
        env_dict["OLLAMA_BASE_URL"] = ollama_url_val
        env_dict["OLLAMA_MODEL"] = ollama_model_val
        env_dict["SQLITE_DB_PATH"] = sqlite_db_val
        env_dict["GMAIL_EMAIL"] = gmail_email_val
        env_dict["GMAIL_APP_PASSWORD"] = gmail_pwd_val
        
        try:
            with open(".env", "w") as f:
                f.write("# Ollama Local Service Configuration\n")
                f.write(f"OLLAMA_BASE_URL={env_dict.get('OLLAMA_BASE_URL', 'http://localhost:11434')}\n")
                f.write(f"OLLAMA_MODEL={env_dict.get('OLLAMA_MODEL', 'llama3.1:8b')}\n")
                f.write(f"OLLAMA_EMBEDDING_MODEL={env_dict.get('OLLAMA_EMBEDDING_MODEL', 'nomic-embed-text')}\n\n")
                
                f.write("# ChromaDB Config\n")
                f.write(f"CHROMADB_HOST={env_dict.get('CHROMADB_HOST', 'localhost')}\n")
                f.write(f"CHROMADB_PORT={env_dict.get('CHROMADB_PORT', '8000')}\n")
                f.write(f"CHROMADB_PERSIST_DIRECTORY={env_dict.get('CHROMADB_PERSIST_DIRECTORY', './chromadb_storage')}\n\n")
                
                f.write("# SQLite DB Path\n")
                f.write(f"SQLITE_DB_PATH={env_dict.get('SQLITE_DB_PATH', './jobchecker.db')}\n\n")
                
                f.write("# Gmail Daemon Credentials\n")
                f.write(f"GMAIL_EMAIL={env_dict.get('GMAIL_EMAIL', '')}\n")
                f.write(f"GMAIL_APP_PASSWORD={env_dict.get('GMAIL_APP_PASSWORD', '')}\n\n")
                
                f.write("# Playwright Browser Config\n")
                f.write(f"PLAYWRIGHT_USER_DATA_DIR={env_dict.get('PLAYWRIGHT_USER_DATA_DIR', './.playwright_session')}\n")
                f.write(f"PLAYWRIGHT_HEADLESS={env_dict.get('PLAYWRIGHT_HEADLESS', 'false')}\n")
                
            st.success("Configuration saved to .env file! Rerunning application...")
            # Reload dotenv values
            from dotenv import load_dotenv
            load_dotenv(override=True)
            st.rerun()
        except Exception as e:
            st.error(f"Failed to write .env file: {e}")
        
    st.markdown("---")
    st.markdown("### System Statistics")
    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        st.metric("Total Jobs Indexed", len(all_jobs))
    with col_s2:
        st.metric("Pending Auto-replies", len(pending_drafts))
    with col_s3:
        st.metric("ChromaDB Persistence Status", "ONLINE" if os.path.exists("./chromadb_storage") else "OFFLINE")
