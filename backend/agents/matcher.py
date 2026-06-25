import os
import json
import requests
from dotenv import load_dotenv
from backend.db.vector_store import query_resume
from backend.database import update_job_match, get_latest_profile

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

def heuristic_match(job_description, resume_text):
    """Fallback text match logic when local Ollama is offline or model is missing."""
    import re
    # Simple overlap checking for common technical keywords
    keywords = [
        "python", "fastapi", "django", "flask", "docker", "kubernetes", "aws", "gcp",
        "sql", "postgresql", "react", "streamlit", "typescript", "javascript", "machine learning",
        "llm", "langgraph", "crewai", "playwright", "scraping", "git", "ci/cd", "apis"
    ]
    
    desc_lower = job_description.lower()
    res_lower = resume_text.lower()
    
    matched_skills = []
    missing_skills = []
    
    for kw in keywords:
        in_desc = re.search(r'\b' + re.escape(kw) + r'\b', desc_lower)
        in_res = re.search(r'\b' + re.escape(kw) + r'\b', res_lower)
        
        if in_desc:
            if in_res:
                matched_skills.append(kw.capitalize())
            else:
                missing_skills.append(kw.capitalize())
                
    if not matched_skills and not missing_skills:
        # Fallback if no keywords overlap
        return 50, "Medium", ["Specific Technical Frameworks"]
        
    total_relevant = len(matched_skills) + len(missing_skills)
    match_percentage = int((len(matched_skills) / total_relevant) * 100) if total_relevant > 0 else 0
    
    if match_percentage >= 75:
        tier = "High"
    elif match_percentage >= 40:
        tier = "Medium"
    else:
        tier = "Low"
        
    return match_percentage, tier, missing_skills

def match_job_with_ollama(job_title, company, job_description):
    """Asks Ollama to rank fit, check skill gaps, and return structured JSON."""
    profile = get_latest_profile()
    if not profile:
        print("[Matcher] No active candidate profile found in DB. Cannot perform match.")
        return 0, "Low", ["No candidate profile uploaded."]
        
    resume_text = profile["parsed_text"]
    
    # Retrieve relevant snippets from ChromaDB
    relevant_chunks = query_resume(job_description, n_results=3)
    retrieved_resume_context = "\n\n".join(relevant_chunks) if relevant_chunks else resume_text[:2000]
    
    prompt = f"""
    Analyze the fit between this Candidate Profile and the Job Description.
    
    ### Candidate Profile (Relevant fragments):
    {retrieved_resume_context}
    
    ### Job Title: {job_title} at {company}
    ### Job Description:
    {job_description}
    
    Determine the following:
    1. match_percentage: Integer (0-100) based on overlapping technical skill requirements, years of experience, and role responsibilities.
    2. probability_tier: String ('High', 'Medium', or 'Low') assessing target fit.
    3. skill_gaps: A list of key technical skills or certifications explicitly mentioned in the job description that are missing or weak in the candidate's profile.
    
    Return the response ONLY as a valid JSON object matching this schema. Do not output conversational text or wrapper blocks.
    {{
        "match_percentage": 85,
        "probability_tier": "High",
        "skill_gaps": ["React", "Kubernetes"]
    }}
    """
    
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "format": "json",
                "stream": False
            },
            timeout=25
        )
        response.raise_for_status()
        res_json = json.loads(response.json()["response"])
        
        match_pct = int(res_json.get("match_percentage", 0))
        tier = res_json.get("probability_tier", "Low")
        gaps = res_json.get("skill_gaps", [])
        
        return match_pct, tier, gaps
        
    except Exception as e:
        print(f"[Matcher] Ollama API error: {e}. Falling back to heuristic match.")
        return heuristic_match(job_description, resume_text)

def generate_email_response(job_id, email_sender, email_subject, email_body):
    """Generates a professional response draft mirroring the user's tone and background."""
    profile = get_latest_profile()
    candidate_name = "Gautam" # Fallback
    resume_context = ""
    if profile:
        candidate_name = "Gautam" # Can parse from resume or default
        resume_context = profile["parsed_text"][:1500]
        
    prompt = f"""
    Write a professional, warm email reply to a recruiter. 
    Maintain a polished, highly qualified, and natural human tone. 
    
    ### Candidate Info:
    Name: {candidate_name}
    Profile Details:
    {resume_context}
    
    ### Received Email Details:
    Sender: {email_sender}
    Subject: {email_subject}
    Email Content:
    {email_body}
    
    Draft an email response that:
    1. Expresses appreciation for the message.
    2. Mentions alignment with the role based on candidate details.
    3. Confirms availability for next Tuesday and Wednesday between 10:00 AM and 3:00 PM EST, or asks to align schedules.
    4. Concludes with a clean signature block.
    
    Return the result ONLY as a JSON object:
    {{
        "subject": "Re: [Original Subject]",
        "body": "[Email Body]"
    }}
    """
    
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "format": "json",
                "stream": False
            },
            timeout=25
        )
        response.raise_for_status()
        res_json = json.loads(response.json()["response"])
        return res_json.get("subject", f"Re: {email_subject}"), res_json.get("body", "")
    except Exception as e:
        print(f"[Matcher] Ollama draft generation failed: {e}. Using template draft.")
        # Fallback template draft
        subject = f"Re: {email_subject}"
        body = f"""Hi,

Thank you for reaching out! I would love to schedule a call to discuss the Software Engineer opportunity at Vertex Corp. 

I am available next Tuesday and Wednesday between 10:00 AM and 3:00 PM EST. Please let me know what time works best on your end.

Best regards,
Gautam"""
        return subject, body

def run_job_matcher(job_id):
    """Convenience function to match a job and update its SQL state."""
    from backend.database import get_job_by_id
    job = get_job_by_id(job_id)
    if not job:
        return None
        
    match_pct, tier, gaps = match_job_with_ollama(
        job["title"],
        job["company"],
        job["description"]
    )
    
    update_job_match(job_id, match_pct, tier, gaps, status='matched')
    return {
        "match_percentage": match_pct,
        "probability_tier": tier,
        "skill_gaps": gaps
    }
