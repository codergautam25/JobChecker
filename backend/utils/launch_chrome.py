import os
import asyncio
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

PLAYWRIGHT_USER_DATA_DIR = os.getenv("PLAYWRIGHT_USER_DATA_DIR", "./.playwright_session")
EXTENSION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "linkedin_intel_ext"))

async def launch_browser_with_extension():
    print(f"Loading Chrome Extension from: {EXTENSION_PATH}")
    print(f"Using persistent session profile at: {PLAYWRIGHT_USER_DATA_DIR}")
    
    async with async_playwright() as p:
        # Launch Chromium with the extension loaded and user profiles persisted
        context = await p.chromium.launch_persistent_context(
            user_data_dir=PLAYWRIGHT_USER_DATA_DIR,
            headless=False,
            channel="chrome", # Run real Google Chrome on macOS
            viewport={"width": 1280, "height": 800},
            args=[
                f"--disable-extensions-except={EXTENSION_PATH}",
                f"--load-extension={EXTENSION_PATH}",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        
        # Override navigator.webdriver
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        page = await context.new_page()
        
        # Check if we have active profile, then open LinkedIn
        print("Navigating to LinkedIn feed...")
        await page.goto("https://www.linkedin.com/feed/")
        
        # Open Next.js in a second tab
        page2 = await context.new_page()
        print("Navigating to Next.js Dashboard...")
        await page2.goto("http://localhost:3000")
        
        print("\n" + "="*50)
        print("Both tabs opened successfully in Google Chrome!")
        print("Tab 1: LinkedIn (with the scraper extension loaded)")
        print("Tab 2: Next.js Agent Dashboard")
        print("Please review and test the scraper feed. Press Enter in this terminal window when done to close the browser.")
        print("="*50 + "\n")
        
        # Keep process alive until user presses Enter in terminal
        await asyncio.get_event_loop().run_in_executor(None, input)
        await context.close()

if __name__ == "__main__":
    asyncio.run(launch_browser_with_extension())
