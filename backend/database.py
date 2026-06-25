import sqlite3
import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("SQLITE_DB_PATH", "./jobchecker.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create profile table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS profile (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        file_type TEXT NOT NULL,
        parsed_text TEXT NOT NULL,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Create jobs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        company TEXT NOT NULL,
        description TEXT NOT NULL,
        deep_link TEXT UNIQUE,
        match_percentage INTEGER DEFAULT 0,
        probability_tier TEXT DEFAULT 'Low',
        skill_gaps TEXT, -- JSON string list
        status TEXT DEFAULT 'scraped', -- scraped, matched, ignored, draft_generated, applied
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Create drafts table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS drafts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER,
        recipient_email TEXT,
        subject TEXT,
        body TEXT,
        status TEXT DEFAULT 'pending', -- pending, approved, sent, discarded
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES jobs (id) ON DELETE CASCADE
    )
    """)
    
    conn.commit()
    conn.close()
    populate_mock_jobs()

def populate_mock_jobs():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM jobs")
    row = cursor.fetchone()
    if row['count'] <= 3:  # If DB is empty or has only the test ones, populate it
        # Clear out existing ones to avoid conflicts
        cursor.execute("DELETE FROM jobs")
        mock_jobs = [
            ("Python Backend Engineer", "Mock Tech Inc", "Looking for Python Developer with FastAPI and Docker.", "https://mocktech.com/jobs/123", "matched", 85, "High", json.dumps(["Kubernetes"])),
            ("AI Platform Agent Specialist", "NeuralLoop Systems", "Join our AI Core team to build multi-agent loops.", "https://neuralloop.systems/jobs/ai-agent-eng", "applied", 90, "High", json.dumps(["React"])),
            ("Senior API Architect", "CloudScale Solutions", "Scale APIs using Python, PostgreSQL, and AWS.", "https://cloudscale.io/careers/senior-backend", "interviewing", 75, "High", json.dumps(["Docker", "CI/CD"])),
            ("MLOps Automation Engineer", "Vertex Corp", "Maintain pipelines and models inside containers.", "https://vertexcorp.com/careers/mlops", "offer", 95, "High", json.dumps([])),
            ("React/Streamlit Web Developer", "DesignVibe Digital", "Seeking a frontend visual engineer.", "https://designvibe.digital/careers/frontend-dev", "rejected", 40, "Low", json.dumps(["Python"]))
        ]
        cursor.executemany("""
            INSERT INTO jobs (title, company, description, deep_link, status, match_percentage, probability_tier, skill_gaps)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, mock_jobs)
        conn.commit()
        print("Mock stage jobs populated in DB.")
    conn.close()

# Profile Operations
def save_profile(filename, file_type, parsed_text):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Delete old profile to maintain single active profile context
    cursor.execute("DELETE FROM profile")
    cursor.execute(
        "INSERT INTO profile (filename, file_type, parsed_text) VALUES (?, ?, ?)",
        (filename, file_type, parsed_text)
    )
    conn.commit()
    conn.close()

def get_latest_profile():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM profile ORDER BY last_updated DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# Job Operations
def insert_job(title, company, description, deep_link, status='scraped'):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO jobs (title, company, description, deep_link, status) VALUES (?, ?, ?, ?, ?)",
            (title, company, description, deep_link, status)
        )
        conn.commit()
        job_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        # Job already exists
        cursor.execute("SELECT id FROM jobs WHERE deep_link = ?", (deep_link,))
        row = cursor.fetchone()
        job_id = row['id'] if row else None
    conn.close()
    return job_id

def update_job_match(job_id, match_percentage, probability_tier, skill_gaps, status='matched'):
    conn = get_db_connection()
    cursor = conn.cursor()
    gaps_str = json.dumps(skill_gaps) if isinstance(skill_gaps, list) else skill_gaps
    cursor.execute(
        """
        UPDATE jobs 
        SET match_percentage = ?, probability_tier = ?, skill_gaps = ?, status = ?
        WHERE id = ?
        """,
        (match_percentage, probability_tier, gaps_str, status, job_id)
    )
    conn.commit()
    conn.close()

def get_all_jobs(status=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if status:
        cursor.execute("SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC", (status,))
    else:
        cursor.execute("SELECT * FROM jobs ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_job_by_id(job_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_job_status(job_id, status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
    conn.commit()
    conn.close()

# Draft Operations
def create_draft(job_id, recipient_email, subject, body):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO drafts (job_id, recipient_email, subject, body, status) VALUES (?, ?, ?, ?, 'pending')",
        (job_id, recipient_email, subject, body)
    )
    conn.commit()
    draft_id = cursor.lastrowid
    conn.close()
    return draft_id

def get_pending_drafts():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT drafts.*, jobs.title as job_title, jobs.company as job_company 
        FROM drafts 
        JOIN jobs ON drafts.job_id = jobs.id 
        WHERE drafts.status = 'pending' 
        ORDER BY drafts.created_at DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_draft(draft_id, subject, body, status='pending'):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE drafts SET subject = ?, body = ?, status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (subject, body, status, draft_id)
    )
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
