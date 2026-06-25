from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from backend.database import init_db, get_all_jobs, get_job_by_id, get_latest_profile
from backend.agents.orchestrator import process_scraped_job
from backend.agents.scraper import JobScraper
from backend.agents.gmail_daemon import check_gmail_imap

# Initialize SQLite database
init_db()

app = FastAPI(
    title="AgenticJobFlow API",
    description="Local background services for job indexing, matching, and drafting",
    version="1.0"
)

# Enable CORS for local Streamlit and Chrome Extension scripts
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ScrapeRequest(BaseModel):
    keywords: str = "Python Engineer"
    location: str = "Remote"
    real_scrape: bool = False

class IntelPostRequest(BaseModel):
    title: str
    company: str
    description: str
    deep_link: str


@app.get("/")
def read_root():
    return {"status": "running", "agent": "AgenticJobFlow"}

@app.get("/jobs")
def list_jobs(status: str = None):
    return get_all_jobs(status=status)

@app.post("/scrape")
def trigger_scrape(req: ScrapeRequest, background_tasks: BackgroundTasks):
    """Triggers background scraping and runs matches."""
    def run_sync():
        import asyncio
        scraper = JobScraper(req.keywords, req.location)
        # Execute scraper
        asyncio.run(scraper.run(mock_fallback=not req.real_scrape))
        
        # Run matching pipeline on any newly scraped jobs
        new_jobs = get_all_jobs(status="scraped")
        for nj in new_jobs:
            process_scraped_job(nj["id"])
            
    background_tasks.add_task(run_sync)
    return {"message": "Scrape task started in background."}

@app.post("/gmail/sync")
def trigger_gmail_sync(background_tasks: BackgroundTasks):
    background_tasks.add_task(check_gmail_imap)
    return {"message": "Gmail sync task started in background."}

@app.post("/api/intel/posts")
def receive_intel_post(req: IntelPostRequest, background_tasks: BackgroundTasks):
    from backend.database import insert_job
    job_id = insert_job(
        title=req.title,
        company=req.company,
        description=req.description,
        deep_link=req.deep_link,
        status='scraped'
    )
    if job_id:
        background_tasks.add_task(process_scraped_job, job_id)
        return {"message": "Scraped post received, scoring in background.", "job_id": job_id}
    return {"message": "Job link already exists, skipping."}

@app.get("/api/profile")
def get_profile_api():
    return get_latest_profile() or {}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
