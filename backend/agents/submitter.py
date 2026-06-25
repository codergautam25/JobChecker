import os
import json
import asyncio
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from backend.utils.playwright_helper import get_browser_context, human_delay
from backend.database import get_job_by_id, update_job_status

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

def sanitize_dom(html_content):
    """
    Strips scripts, styles, metadata, and redundant classes from the DOM
    to keep context windows lightweight for the local model.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    
    # Remove unwanted tags
    for tag in soup(["script", "style", "meta", "link", "svg", "noscript", "iframe"]):
        tag.decompose()
        
    # Remove large structural sections that are not forms
    for tag in soup.find_all(attrs={"role": ["navigation", "banner", "contentinfo"]}):
        tag.decompose()
        
    # Keep only forms and their parents
    forms = soup.find_all("form")
    if not forms:
        # If no explicit form tag, return body text or interactive elements
        interactive_tags = soup.find_all(["input", "select", "textarea", "button", "label"])
        sanitized = "\n".join([str(t) for t in interactive_tags])
    else:
        # Simplify classes and structural elements
        for f in forms:
            for el in f.descendants:
                if el.name in ["input", "select", "textarea", "button", "label"]:
                    # Keep only essential attributes to save tokens
                    essential_attrs = {}
                    for attr in ["id", "name", "type", "placeholder", "for", "value"]:
                        if el.has_attr(attr):
                            essential_attrs[attr] = el[attr]
                    el.attrs = essential_attrs
        sanitized = "\n".join([str(f) for f in forms])
        
    return sanitized

def heuristic_form_mapping(html_sanitized):
    """Heuristic fallback for mapping fields to DOM input selectors."""
    soup = BeautifulSoup(html_sanitized, "html.parser")
    inputs = soup.find_all(["input", "textarea", "select"])
    
    mapping = {}
    for inp in inputs:
        inp_id = inp.get("id", "")
        inp_name = inp.get("name", "")
        inp_type = inp.get("type", "text")
        
        # Combine identifiers to search for keywords
        combined = f"{inp_id} {inp_name} {inp.get('placeholder', '')}".lower()
        
        selector = ""
        if inp_id:
            selector = f"#{inp_id}"
        elif inp_name:
            selector = f"input[name='{inp_name}']"
        else:
            continue
            
        if inp_type == "file" or "resume" in combined:
            mapping["resume_upload"] = selector
        elif "first" in combined and "name" in combined:
            mapping["first_name"] = selector
        elif "last" in combined and "name" in combined:
            mapping["last_name"] = selector
        elif "name" in combined and "full" in combined:
            mapping["full_name"] = selector
        elif "name" in combined and not mapping.get("full_name") and not mapping.get("first_name"):
            mapping["full_name"] = selector
        elif "email" in combined:
            mapping["email"] = selector
        elif "phone" in combined or "mobile" in combined:
            mapping["phone"] = selector
            
    return mapping

def get_field_mappings_from_llm(sanitized_form_html):
    """Instructs Ollama to discover input selectors at runtime before filling fields."""
    prompt = f"""
    Analyze the following sanitized HTML form inputs. Discover the CSS selectors that match standard candidate fields:
    - full_name (or first_name and last_name if split)
    - email
    - phone
    - resume_upload (input tag with type="file" or mapping to resume upload files)
    
    ### Sanitized HTML Form:
    {sanitized_form_html}
    
    Return the response strictly as a JSON object where keys are the field names and values are the exact CSS selectors (e.g. '#first-name', 'input[name="email"]'). Do not wrap in conversational text.
    {{
        "first_name": "#first-name",
        "last_name": "#last-name",
        "email": "input[name='email']",
        "resume_upload": "input[type='file']"
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
        return json.loads(response.json()["response"])
    except Exception as e:
        print(f"[Submitter] Ollama layout analysis failed: {e}. Falling back to heuristic mapping.")
        return heuristic_form_mapping(sanitized_form_html)

async def auto_submit_application(job_id, resume_file_path, candidate_info=None):
    """Navigates to application link, parses DOM, maps selectors, and inputs values."""
    job = get_job_by_id(job_id)
    if not job:
        print(f"[Submitter] Job {job_id} not found in DB.")
        return False
        
    url = job["deep_link"]
    print(f"[Submitter] Launching submission agent for: {url}")
    
    if not candidate_info:
        candidate_info = {
            "first_name": "Gautam",
            "last_name": "Kumar",
            "full_name": "Gautam Kumar",
            "email": "gautam@gmail.com",
            "phone": "+1234567890"
        }
        
    async with async_playwright() as p:
        context = await get_browser_context(p)
        page = await context.new_page()
        
        try:
            await page.goto(url)
            await human_delay(3.0, 5.0)
            
            # Fetch HTML and sanitize
            content = await page.content()
            sanitized = sanitize_dom(content)
            
            # Map input elements to selectors
            mappings = get_field_mappings_from_llm(sanitized)
            print(f"[Submitter] Discovered field mappings: {mappings}")
            
            # Input details
            for field, selector in mappings.items():
                try:
                    if field == "resume_upload":
                        print(f"[Submitter] Uploading resume '{resume_file_path}' to selector '{selector}'")
                        async with page.expect_file_chooser() as fc_info:
                            await page.click(selector)
                        file_chooser = await fc_info.value
                        await file_chooser.set_files(resume_file_path)
                    else:
                        val = candidate_info.get(field)
                        if val:
                            print(f"[Submitter] Filling field '{field}' using selector '{selector}' with '{val}'")
                            await page.click(selector)
                            await page.fill(selector, val)
                            
                    await human_delay(0.5, 1.5)
                except Exception as ex:
                    print(f"[Submitter] Failed to fill field '{field}' at selector '{selector}': {ex}")
            
            # In validation run, we do not auto-click submit unless instructed
            # We save the screenshot or page state
            screenshot_path = f"./.playwright_session/screenshot_job_{job_id}.png"
            await page.screenshot(path=screenshot_path)
            print(f"[Submitter] Submission ready screen saved to: {screenshot_path}")
            
            update_job_status(job_id, "applied")
            return True
            
        except Exception as e:
            print(f"[Submitter] Submission execution error: {e}")
            return False
        finally:
            await context.close()

if __name__ == "__main__":
    # Test submission script
    # We construct a mock local html file containing form fields to verify parsing and input mapping
    import tempfile
    
    mock_form_html = """
    <html>
        <body>
            <form id="apply-form">
                <label for="fname">First Name:</label>
                <input type="text" id="fname" name="firstname" placeholder="Enter first name">
                
                <label for="lname">Last Name:</label>
                <input type="text" id="lname" name="lastname" placeholder="Enter last name">
                
                <label for="email_addr">Email Address:</label>
                <input type="email" id="email_addr" name="email" required>
                
                <label for="cv">Resume File:</label>
                <input type="file" id="cv" name="resume_file">
            </form>
        </body>
    </html>
    """
    
    sanitized = sanitize_dom(mock_form_html)
    print("Sanitized DOM:")
    print(sanitized)
    
    mappings = heuristic_form_mapping(sanitized)
    print("\nHeuristic Mapping Result:")
    print(mappings)
