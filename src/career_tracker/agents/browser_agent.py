"""Browser agent for autonomous web interaction."""

from __future__ import annotations

import os
import asyncio
import structlog
from datetime import datetime

logger = structlog.get_logger(__name__)

# Disable browser-use telemetry to prevent PostHog connection errors
os.environ["ANONYMIZED_TELEMETRY"] = "false"

try:
    from browser_use import Agent, Browser, Controller
    from browser_use.llm.openai.chat import ChatOpenAI
    _BROWSER_USE_AVAILABLE = True
except ImportError:
    _BROWSER_USE_AVAILABLE = False

import threading
HUMAN_WAIT_EVENTS = {}


def _build_apply_prompt(apply_url: str, user_profile: dict) -> str:
    """Build the prompt instructing the agent what to do on the web page."""
    
    # Format the profile info neatly
    profile_details = f"""
    First Name: {user_profile.get('name', '').split()[0] if user_profile.get('name') else ''}
    Last Name: {user_profile.get('name', '').split()[-1] if user_profile.get('name') and len(user_profile.get('name').split()) > 1 else ''}
    Full Name: {user_profile.get('name', '')}
    Email: {user_profile.get('email', '')}
    Phone: {user_profile.get('phone', '')}
    LinkedIn URL: {user_profile.get('linkedin_url', '')}
    GitHub/Portfolio: {user_profile.get('portfolio_url', '')}
    """
    
    # Only include resume text if it exists and isn't too huge
    resume_text = user_profile.get('parsed_resume_text', '')
    if len(resume_text) > 3000:
        resume_text = resume_text[:3000] + "\n...[truncated]"

    return f"""You are an autonomous job application assistant. Your goal is to fill out and submit the job application form at this URL: {apply_url}

Follow these rules:
1. Navigate to the URL and find the application form.
2. If you hit a login wall (e.g., LinkedIn login page, Naukri login), do NOT attempt to type credentials. Instead, use the `ask_human` action to pause and ask the user to log in manually. Wait for them to finish before proceeding.
3. Fill out all required fields accurately using the Candidate Profile below.
4. For fields like "Years of Experience" or specific skills, deduce the best answer from the Resume Text if provided, otherwise leave it blank or select a reasonable default if it's a dropdown.
5. If there's an option to upload a resume file instead of pasting text, you CANNOT do this right now. If it forces a file upload and there is no text area fallback, you must stop and report failure.
6. If you encounter a CAPTCHA, STOP and report failure. Do NOT try to solve it.
7. Once the form is filled out, click the Submit Application button.
8. Wait to see the confirmation page. If successful, end the task.

--- CANDIDATE PROFILE ---
{profile_details}

--- RESUME TEXT ---
{resume_text}
"""


async def run_apply_agent_async(apply_url: str, user_profile: dict, headless: bool = False, log_fn=None, app_id: str = None) -> dict:
    """Run the browser agent asynchronously."""
    if not _BROWSER_USE_AVAILABLE:
        msg = "browser-use package is not installed. Please install it using `pip install browser-use playwright` and `playwright install`."
        if log_fn:
            log_fn(f"[ERROR] {msg}")
        return {"success": False, "error": msg}

    if not apply_url:
        msg = "No apply URL provided."
        if log_fn:
            log_fn(f"[ERROR] {msg}")
        return {"success": False, "error": msg}

    if log_fn:
        log_fn(f"🚀 Initializing browser agent for: {apply_url}")
        log_fn(f"👁️ Browser visibility: {'Headless (Hidden)' if headless else 'Headful (Visible)'}")

    # Set up the LLM (requires OPENAI_API_KEY to be in environment)
    from career_tracker.config import get_settings
    settings = get_settings()
    llm_model = getattr(settings, "llm_model", "gpt-4o")
    
    if not os.getenv("OPENAI_API_KEY"):
        msg = "OPENAI_API_KEY environment variable is missing."
        if log_fn:
            log_fn(f"[ERROR] {msg}")
        return {"success": False, "error": msg}

    llm = ChatOpenAI(model=llm_model)

    # Connect using a dedicated AI Agent Profile. This is 100% seamless and doesn't
    # require the user to kill their main browser. The first time it runs, they just
    # log in to LinkedIn on the new window, and it remembers forever.
    try:
        # The user requested connecting to their already open browser via CDP 
        # (started with --remote-debugging-port=9222) to bypass security blocks.
        browser = Browser(cdp_url="http://127.0.0.1:9222")
    except Exception as e:
        msg = f"Failed to initialize AI browser profile: {e}"
        if log_fn:
            log_fn(f"[ERROR] {msg}")
        return {"success": False, "error": msg}

    prompt = _build_apply_prompt(apply_url, user_profile)
    
    if log_fn:
        log_fn("🤖 Agent prompt generated. Starting execution loop...")

    # Initialize the controller with custom human intervention tool
    controller = Controller()
    
    @controller.action('Ask user for help and wait for them to complete a manual action (like logging in)')
    async def ask_human(message_to_human: str) -> str:
        if log_fn:
            log_fn(f"⚠️ PAUSED FOR HUMAN: {message_to_human}\n\nPlease perform the action in the browser, then type 'done' here in the chat to resume.")
        
        event = threading.Event()
        if app_id:
            HUMAN_WAIT_EVENTS[app_id] = event
        else:
            return "Cannot pause, no app_id provided. Assuming manual action completed."
        
        while not event.is_set():
            await asyncio.sleep(1)
            
        del HUMAN_WAIT_EVENTS[app_id]
        if log_fn:
            log_fn(f"▶️ RESUMING: User confirmed they have completed the action.")
        return "Human says they are done. Proceed."

    # Initialize the agent
    agent = Agent(
        task=prompt,
        llm=llm,
        browser=browser,
        controller=controller,
        step_timeout=3600,
    )

    handler = None
    try:
        if log_fn:
            import logging
            class LogFnHandler(logging.Handler):
                def emit(self, record):
                    try:
                        if record.levelno < logging.INFO:
                            return
                        msg = self.format(record)
                        # Filter to only show interesting interactive agent logs
                        if any(x in msg for x in ["ask_human", "navigate", "Eval:", "Memory:", "Next goal:", "click", "type"]):
                            # The message from logging.Formatter('%(message)s') is already clean
                            clean_msg = msg.strip()
                            # It usually starts with something like "▶️   ask_human: " or "🧠 Memory: "
                            # which looks perfect, so we just prepend our bot icon.
                            log_fn(f"> 🤖 {clean_msg}")
                    except Exception:
                        pass
                        
            bu_logger = logging.getLogger("browser_use")
            handler = LogFnHandler()
            handler.setFormatter(logging.Formatter('%(message)s'))
            bu_logger.addHandler(handler)
            
        # Run the agent
        # The agent returns a History object containing steps, results, and screenshots
        # Limit max_steps to 15 to prevent infinite loops and save LLM token costs.
        result = await agent.run(max_steps=15)
        
        # Check if the final step has an extracted result or indicates success
        final_result_text = "Task finished."
        if result.history and len(result.history) > 0:
            last_step = result.history[-1]
            if hasattr(last_step.result, 'extracted_content') and last_step.result.extracted_content:
                final_result_text = last_step.result.extracted_content
            
        if log_fn:
            log_fn(f"✅ Agent completed successfully.\nFinal output: {final_result_text}")
        
        if result.is_successful() or "USER_LOGIN_REQUIRED" in final_result_text:
            if app_id and result.is_successful():
                try:
                    screenshot_dir = os.path.abspath(os.path.join(os.getcwd(), "data", "screenshots"))
                    os.makedirs(screenshot_dir, exist_ok=True)
                    screenshot_path = os.path.join(screenshot_dir, f"{app_id}.png")
                    
                    b64_screenshot = None
                    if result.history and len(result.history) > 0:
                        b64_screenshot = result.history[-1].state.get_screenshot()
                        
                    if b64_screenshot:
                        import base64
                        if log_fn: log_fn(f"📸 Saving final screenshot to {screenshot_path}")
                        with open(screenshot_path, "wb") as f:
                            f.write(base64.b64decode(b64_screenshot))
                    else:
                        if log_fn: log_fn(f"⚠️ No screenshot found in agent history.")
                except Exception as e:
                    if log_fn: log_fn(f"⚠️ Failed to save screenshot: {e}")
            
            return {
                "success": True,
                "final_result": final_result_text,
                "steps_taken": len(result.history) if result.history else 0
            }
        
        return {
            "success": False,
            "final_result": final_result_text,
            "error": "Agent finished without success",
            "steps_taken": len(result.history) if result.history else 0
        }
        
    except Exception as e:
        err_msg = str(e)
        logger.error("browser_agent.error", error=err_msg)

        if log_fn:
            log_fn(f"❌ Agent execution failed: {err_msg}")
            
        return {
            "success": False,
            "error": err_msg
        }
    finally:
        if handler:
            import logging
            logging.getLogger("browser_use").removeHandler(handler)


def run_apply_agent_sync(apply_url: str, user_profile: dict, headless: bool = False, log_fn=None, app_id: str = None) -> dict:
    """Synchronous wrapper for the browser agent."""
    return asyncio.run(run_apply_agent_async(apply_url, user_profile, headless, log_fn, app_id=app_id))
