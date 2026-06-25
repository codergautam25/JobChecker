import os
import random
import asyncio
from playwright.async_api import async_playwright
from backend.utils.playwright_helper import get_browser_context, human_delay, human_scroll
from backend.database import insert_job, init_db

class JobScraper:
    def __init__(self, keywords="Python Engineer", location="Remote"):
        self.keywords = keywords
        self.location = location

    async def scrape_linkedin(self):
        """Scrapes jobs from LinkedIn using the persistent session."""
        print(f"Starting LinkedIn scraper for: '{self.keywords}' in '{self.location}'")
        jobs_found = []
        
        async with async_playwright() as p:
            context = await get_browser_context(p)
            page = await context.new_page()
            
            # Go to LinkedIn job search with keywords
            search_url = f"https://www.linkedin.com/jobs/search/?keywords={self.keywords.replace(' ', '%20')}&location={self.location.replace(' ', '%20')}"
            
            try:
                await page.goto(search_url)
                await human_delay(3.0, 5.0)
                
                # Check if we are redirected to a login gate
                if "login" in page.url:
                    print("[Warning] LinkedIn redirecting to login page. Session may need re-auth.")
                    # In a real environment, we'd warn the user or attempt session restoration.
                
                # Try to scroll and load job list
                await human_scroll(page)
                
                # Selector targets
                # LinkedIn public search or private search selectors differ
                # We check for common selectors
                job_selectors = [
                    "div.job-card-container",
                    "li.jobs-search-results__list-item",
                    "div.base-card"
                ]
                
                job_cards = []
                for selector in job_selectors:
                    job_cards = await page.query_selector_all(selector)
                    if job_cards:
                        print(f"Found cards using selector: '{selector}'")
                        break
                
                for idx, card in enumerate(job_cards[:10]): # Limit to 10 for safety/speed
                    try:
                        # Extract title
                        title_el = await card.query_selector(".job-card-list__title, .base-search-card__title")
                        title = (await title_el.inner_text()).strip() if title_el else "Unknown Job"
                        
                        # Extract company
                        company_el = await card.query_selector(".job-card-container__company-name, .base-search-card__subtitle")
                        company = (await company_el.inner_text()).strip() if company_el else "Unknown Company"
                        
                        # Extract deep link
                        link_el = await card.query_selector("a.job-card-list__title, a.base-card__full-link")
                        deep_link = await link_el.get_attribute("href") if link_el else ""
                        if deep_link:
                            deep_link = deep_link.split("?")[0] # Clean query params
                        else:
                            deep_link = f"https://www.linkedin.com/jobs/view/mock-{idx}-{random.randint(1000, 9999)}"
                        
                        # Click on card to load description on the right panel
                        await card.click()
                        await human_delay(1.5, 2.5)
                        
                        # Extract description
                        desc_el = await page.query_selector(".jobs-description__content, .jobs-search__content-inner")
                        description = (await desc_el.inner_text()).strip() if desc_el else "Detailed description not found or requires authentication."
                        
                        jobs_found.append({
                            "title": title,
                            "company": company,
                            "description": description,
                            "deep_link": deep_link
                        })
                        
                    except Exception as e:
                        print(f"Error parsing job card index {idx}: {e}")
                        
            except Exception as e:
                print(f"Navigation/Scraping error: {e}")
            finally:
                await context.close()
                
        return jobs_found

    async def scrape_mock_jobs(self):
        """Generates mock job data for demonstration and testing when offline or unauthenticated."""
        print("Generating mock job results for local testing...")
        await asyncio.sleep(1) # Mimic some latency
        
        mock_jobs = [
            {
                "title": "Backend Software Engineer - Python & FastAPI",
                "company": "TechStream Solutions",
                "description": """
                We are looking for a Backend Engineer with strong experience in Python, FastAPI, and PostgreSQL.
                Key Requirements:
                - 3+ years experience building APIs in Python.
                - Strong experience with SQL databases and ORMs.
                - Knowledge of Docker and CI/CD pipelines.
                - Experience with local LLMs, Ollama, ChromaDB, or RAG models is a huge plus.
                - Familiarity with unit testing (pytest).
                """,
                "deep_link": "https://careers.techstream.io/jobs/309"
            },
            {
                "title": "AI Platform Engineer (Stateful Agents)",
                "company": "NeuralLoop Systems",
                "description": """
                Join our AI Core team to build agentic pipelines.
                Key Requirements:
                - Experience building multi-agent systems using LangGraph or CrewAI.
                - Strong Python coding, including async execution.
                - Experience with Vector Databases (ChromaDB, Qdrant, Milvus).
                - Knowledge of LLM fine-tuning, prompt engineering, and structured JSON outputs.
                """,
                "deep_link": "https://neuralloop.systems/jobs/ai-agent-eng"
            },
            {
                "title": "Frontend Developer (React / Streamlit)",
                "company": "DesignVibe Digital",
                "description": """
                We are seeking a Frontend Developer to build clean dashboards.
                Key Requirements:
                - Strong experience with React or Streamlit.
                - High attention to design aesthetics, styling, custom CSS.
                - Knowledge of REST APIs and WebSocket communication.
                - Experience with building responsive web interfaces.
                """,
                "deep_link": "https://designvibe.digital/careers/frontend-dev"
            }
        ]
        return mock_jobs

    async def run(self, mock_fallback=True):
        """Runs the scraper and persists found jobs in SQLite."""
        init_db()
        jobs = []
        
        if not mock_fallback:
            jobs = await self.scrape_linkedin()
            
        # Fallback to mock data if no jobs scraped or explicit fallback enabled
        if not jobs and mock_fallback:
            jobs = await self.scrape_mock_jobs()
            
        saved_count = 0
        for j in jobs:
            job_id = insert_job(
                title=j["title"],
                company=j["company"],
                description=j["description"],
                deep_link=j["deep_link"],
                status='scraped'
            )
            if job_id:
                saved_count += 1
                
        print(f"Scrape completed: {saved_count} jobs saved to database.")
        return jobs

if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="Job Scraper CLI")
    parser.add_argument("--keywords", default="Python Engineer", help="Keywords to search")
    parser.add_argument("--location", default="Remote", help="Job location")
    parser.add_argument("--real", action="store_true", help="Run real LinkedIn scrape instead of mock fallback")
    
    args = parser.parse_args()
    
    scraper = JobScraper(args.keywords, args.location)
    asyncio.run(scraper.run(mock_fallback=not args.real))
