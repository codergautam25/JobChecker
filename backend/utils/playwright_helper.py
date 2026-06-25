import os
import random
import asyncio
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

PLAYWRIGHT_USER_DATA_DIR = os.getenv("PLAYWRIGHT_USER_DATA_DIR", "./.playwright_session")
PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() == "true"

async def get_browser_context(playwright, headless=None):
    """
    Creates and returns a persistent browser context to retain login cookies and sessions.
    Also injects standard desktop user agents and dimensions to avoid detection.
    If the session directory is locked by another running Chrome instance, it automatically
    clones the profile to a temporary directory to bypass the Chromium process lock.
    """
    if headless is None:
        headless = PLAYWRIGHT_HEADLESS

    # Ensure session directory exists
    os.makedirs(PLAYWRIGHT_USER_DATA_DIR, exist_ok=True)
    
    user_agent_str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    args_list = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-setuid-sandbox"
    ]
    
    try:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=PLAYWRIGHT_USER_DATA_DIR,
            headless=headless,
            channel="chrome" if not headless else None, # Use real chrome when headful
            viewport={"width": 1280, "height": 800},
            user_agent=user_agent_str,
            args=args_list
        )
    except Exception as e:
        err_msg = str(e)
        if "existing browser session" in err_msg or "already in use" in err_msg or "lock" in err_msg.lower():
            print("[Playwright Helper] Active Chromium session detected. Creating temporary profile copy...")
            temp_dir = os.path.abspath("./.playwright_session_temp")
            import shutil
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                shutil.copytree(
                    PLAYWRIGHT_USER_DATA_DIR, 
                    temp_dir, 
                    symlinks=False, 
                    ignore=shutil.ignore_patterns('SingletonLock', 'SingletonSocket', 'SingletonCookie')
                )
                # Remove locks in the copied profile
                for lock_name in ['SingletonLock', 'SingletonSocket', 'SingletonCookie']:
                    lock_path = os.path.join(temp_dir, lock_name)
                    if os.path.exists(lock_path):
                        try:
                            os.remove(lock_path)
                        except Exception:
                            pass
            except Exception as copy_err:
                print(f"[Playwright Helper] Session copy warning: {copy_err}")
                
            # Launch using the temporary directory copy
            context = await playwright.chromium.launch_persistent_context(
                user_data_dir=temp_dir,
                headless=headless,
                channel="chrome" if not headless else None,
                viewport={"width": 1280, "height": 800},
                user_agent=user_agent_str,
                args=args_list
            )
        else:
            raise e
    
    # Add steering stealth settings (e.g. navigator.webdriver override)
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
    """)
    
    return context

async def human_delay(min_sec=1.5, max_sec=4.0):
    """Introduces randomized human-like delay to bypass firewall bot checks."""
    delay = random.uniform(min_sec, max_sec)
    await asyncio.sleep(delay)

async def human_scroll(page):
    """Simulates a human scrolling down a page incrementally."""
    total_height = await page.evaluate("document.body.scrollHeight")
    current_scroll = 0
    while current_scroll < total_height:
        scroll_step = random.randint(150, 450)
        current_scroll += scroll_step
        await page.evaluate(f"window.scrollTo(0, {current_scroll})")
        await human_delay(0.5, 1.2)
        # Update total height in case lazy loading changed it
        total_height = await page.evaluate("document.body.scrollHeight")

async def setup_login_session():
    """Helper command line function to allow user to manually log in once."""
    print("Launching headful browser. Please log in to LinkedIn / target portals manually...")
    async with async_playwright() as p:
        context = await get_browser_context(p, headless=False)
        page = await context.new_page()
        await page.goto("https://www.linkedin.com/login")
        
        # Keep open until user closes or presses Enter in console
        import sys
        is_interactive = False
        try:
            is_interactive = sys.stdin.isatty()
        except Exception:
            pass

        if is_interactive:
            print("Press Enter in the terminal here once you have logged in and solved all captchas...")
            try:
                await asyncio.get_event_loop().run_in_executor(None, input)
            except (EOFError, Exception):
                is_interactive = False

        if not is_interactive:
            print("[Playwright Helper] Stdin is not interactive. Keeping browser open. Close the browser window to finish...")
            while len(context.pages) > 0:
                await asyncio.sleep(1.0)
                
        await context.close()
        print("Session saved successfully.")

if __name__ == "__main__":
    # Test script to initialize session
    asyncio.run(setup_login_session())
