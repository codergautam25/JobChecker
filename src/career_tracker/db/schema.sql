-- =============================================================================
-- Career Tracker — SQLite Schema  (Phase 1)
-- =============================================================================
-- All tables use TEXT primary keys (UUIDs) for portability.
-- JSON arrays are stored as TEXT and parsed in the application layer.
-- =============================================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ── User Profiles ───────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS user_profiles (
    id                   TEXT PRIMARY KEY,
    name                 TEXT NOT NULL,
    email                TEXT NOT NULL,
    phone                TEXT,
    linkedin_url         TEXT,
    github_url           TEXT,
    portfolio_url        TEXT,
    target_roles         TEXT,          -- JSON array of desired roles
    target_locations     TEXT,          -- JSON array of desired locations
    min_salary           INTEGER,
    preferred_industries TEXT,          -- JSON array
    skills               TEXT,          -- JSON array
    experience           TEXT,          -- JSON array of dicts
    education            TEXT,          -- JSON array of dicts
    certifications       TEXT,          -- JSON array of dicts
    projects             TEXT,          -- JSON array of dicts
    publications         TEXT,          -- JSON array of dicts
    awards               TEXT,          -- JSON array of strings
    languages            TEXT,          -- JSON array of strings
    social_links         TEXT,          -- JSON array or dict
    parsed_files         TEXT,          -- JSON array of filenames
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── Recruiters ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS recruiters (
    id                   TEXT PRIMARY KEY,
    name                 TEXT NOT NULL,
    email                TEXT NOT NULL UNIQUE,
    company              TEXT,
    title                TEXT,
    linkedin_url         TEXT,
    phone                TEXT,
    notes                TEXT,
    first_contact_date   TIMESTAMP,
    last_contact_date    TIMESTAMP,
    interaction_count    INTEGER DEFAULT 0,
    sentiment            TEXT,          -- positive | neutral | negative
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── Applications ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS applications (
    id                   TEXT PRIMARY KEY,
    company              TEXT NOT NULL,
    role                 TEXT NOT NULL,
    status               TEXT NOT NULL DEFAULT 'DISCOVERED',
    url                  TEXT,
    location             TEXT,
    salary_range         TEXT,
    job_description      TEXT,
    recruiter_id         TEXT REFERENCES recruiters(id) ON DELETE SET NULL,
    resume_used          TEXT,
    cover_letter_used    TEXT,
    applied_at           TIMESTAMP,
    source_email_id      TEXT,
    notes                TEXT,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── Emails ──────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS emails (
    id                          TEXT PRIMARY KEY,   -- Gmail message ID
    thread_id                   TEXT,
    subject                     TEXT,
    sender                      TEXT NOT NULL,
    recipient                   TEXT,
    date                        TIMESTAMP,
    body_text                   TEXT,
    body_html                   TEXT,
    labels                      TEXT,               -- JSON array
    is_read                     INTEGER DEFAULT 0,
    status                      TEXT DEFAULT 'PENDING',
    category                    TEXT,               -- EmailCategory enum
    classification_confidence   REAL,
    classification_reasoning    TEXT,
    application_id              TEXT REFERENCES applications(id) ON DELETE SET NULL,
    recruiter_id                TEXT REFERENCES recruiters(id) ON DELETE SET NULL,
    processed_at                TIMESTAMP,
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    attachments_metadata        TEXT,               -- JSON array of attachment info
    attachment_extracted_text   TEXT,               -- Extracted text from PDF/DOC/TXT
    matched_skills              TEXT                -- JSON array of matched skills
);

-- ── Interviews ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS interviews (
    id                   TEXT PRIMARY KEY,
    application_id       TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    interview_type       TEXT NOT NULL,
    scheduled_at         TIMESTAMP,
    duration_minutes     INTEGER,
    location             TEXT,
    interviewer_names    TEXT,          -- JSON array
    notes                TEXT,
    status               TEXT DEFAULT 'SCHEDULED',
    source_email_id      TEXT REFERENCES emails(id) ON DELETE SET NULL,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── Events (Audit Log) ─────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS events (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type           TEXT NOT NULL,     -- e.g. email_classified, reply_drafted
    entity_type          TEXT,              -- application, email, recruiter, etc.
    entity_id            TEXT,
    data                 TEXT,              -- JSON payload with full context
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── Approval Queue ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS approval_queue (
    id                       TEXT PRIMARY KEY,
    action_type              TEXT NOT NULL,
    payload                  TEXT NOT NULL,     -- JSON
    status                   TEXT DEFAULT 'PENDING_APPROVAL',
    related_email_id         TEXT REFERENCES emails(id) ON DELETE SET NULL,
    related_application_id   TEXT REFERENCES applications(id) ON DELETE SET NULL,
    reviewer_notes           TEXT,
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at              TIMESTAMP
);

-- ── Indexes ─────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_emails_thread       ON emails(thread_id);
CREATE INDEX IF NOT EXISTS idx_emails_sender       ON emails(sender);
CREATE INDEX IF NOT EXISTS idx_emails_category     ON emails(category);
CREATE INDEX IF NOT EXISTS idx_emails_date         ON emails(date);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_applications_company ON applications(company);
CREATE INDEX IF NOT EXISTS idx_interviews_app      ON interviews(application_id);
CREATE INDEX IF NOT EXISTS idx_interviews_date     ON interviews(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_events_entity       ON events(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_events_type         ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_approval_status     ON approval_queue(status);

CREATE TABLE IF NOT EXISTS intel_posts (
    id TEXT PRIMARY KEY,
    author TEXT,
    text_content TEXT,
    is_job_opportunity INTEGER DEFAULT 0,
    url TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    raw_html TEXT,
    matched_skills TEXT
);
