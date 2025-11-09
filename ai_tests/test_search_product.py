import asyncio
import os

from ai_core.ai_browser import get_browser
from ai_core.ai_agent import AIAgent
from ai_core.ai_logger import log_info

async def main():
    playwright, browser, context, page, video_dir = await get_browser(headless=True)
    log_info("🔹 Starting AI-driven Search Product Test")

    task = f"""
    1. Open {os.environ.get("BASE_URL")}
    2. Click 'Products' link in header
    3. Verify there is a search box with label 'Search Product'
    4. Type 'T-shirt' in the search input
    5. Click the search button
    6. Verify the searched products section is visible
    """

    agent = AIAgent(task, page)

    try:
        await agent.run()
        log_info("✅ Test completed successfully.")
    except Exception as e:
        log_info(f"❌ Test failed: {e}")
    finally:
        await asyncio.sleep(5)
        await context.close()
        await browser.close()
        await playwright.stop()
        log_info(f"🎥 Video saved in: {video_dir}")

if __name__ == "__main__":
    asyncio.run(main())
