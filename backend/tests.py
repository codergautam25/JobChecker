import os
import sys
import unittest
import json

# Set python path to backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import (
    init_db, save_profile, get_latest_profile, insert_job, 
    update_job_match, get_all_jobs, update_job_status
)
from backend.agents.parser import chunk_text
from backend.agents.matcher import heuristic_match
from backend.agents.submitter import sanitize_dom, heuristic_form_mapping

class TestAgenticJobFlow(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Override DB for testing to a test file
        os.environ["SQLITE_DB_PATH"] = "./test_jobchecker.db"
        init_db()
        
    @classmethod
    def tearDownClass(cls):
        # Clean up test DB file
        if os.path.exists("./test_jobchecker.db"):
            os.remove("./test_jobchecker.db")
            
    def test_database_crud(self):
        """Test standard SQLite schema operations."""
        # Test profile save/retrieve
        save_profile("resume_test.pdf", "pdf", "Candidate Gautam Kumar, Python Engineer with FastAPI.")
        prof = get_latest_profile()
        self.assertIsNotNone(prof)
        self.assertEqual(prof["filename"], "resume_test.pdf")
        self.assertIn("Gautam", prof["parsed_text"])
        
        # Test job insertion
        job_id = insert_job("Tech Lead", "Acme Corp", "FastAPI Python SQL developer", "https://acme.org/jobs/1")
        self.assertIsNotNone(job_id)
        
        # Test update match details
        update_job_match(job_id, 80, "High", ["Docker", "Kubernetes"])
        
        jobs = get_all_jobs()
        match_job = [j for j in jobs if j["id"] == job_id][0]
        self.assertEqual(match_job["match_percentage"], 80)
        self.assertEqual(match_job["probability_tier"], "High")
        self.assertIn("Docker", match_job["skill_gaps"])
        
        # Test status transition
        update_job_status(job_id, "applied")
        jobs = get_all_jobs()
        match_job = [j for j in jobs if j["id"] == job_id][0]
        self.assertEqual(match_job["status"], "applied")

    def test_parser_chunking(self):
        """Test resume parsing sliding-window chunking text logic."""
        text = "Hello " * 150 # 150 words
        chunks = chunk_text(text, chunk_size=200, overlap=50)
        # Should split text into multiple chunks
        self.assertTrue(len(chunks) > 1)
        self.assertIn("Hello", chunks[0])

    def test_matcher_heuristics(self):
        """Test match ranking engine heuristics (Ollama offline fallback)."""
        resume = "Candidate is a Python Developer with FastAPI and Postgres database expertise."
        job_desc = "Looking for a Software Engineer with skills in Python, FastAPI, and Docker."
        
        pct, tier, gaps = heuristic_match(job_desc, resume)
        
        # Should detect Python and FastAPI matching, Docker missing
        self.assertGreater(pct, 0)
        self.assertIn("Docker", gaps)
        self.assertNotIn("Python", gaps)

    def test_dom_sanitizer_and_heuristics(self):
        """Test BeautifulSoup sanitization and input mappings."""
        raw_html = """
        <html>
            <head>
                <style>body { color: red; }</style>
                <script>console.log('ignored');</script>
            </head>
            <body>
                <nav>Header Nav Bar</nav>
                <form id="apply">
                    <div class="row">
                        <label>Email Address</label>
                        <input id="email" name="candidate_email" type="email" placeholder="example@domain.com">
                    </div>
                </form>
            </body>
        </html>
        """
        sanitized = sanitize_dom(raw_html)
        self.assertNotIn("Header Nav Bar", sanitized)
        self.assertNotIn("console.log", sanitized)
        self.assertIn("candidate_email", sanitized)
        
        mappings = heuristic_form_mapping(sanitized)
        self.assertEqual(mappings.get("email"), "#email")

if __name__ == "__main__":
    unittest.main()
