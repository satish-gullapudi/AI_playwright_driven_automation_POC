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
    2. Verify there is a search input box with place holder 'Search Product'
    3. Verify user is navigated to All Products page successfully by checking that the url matches {os.environ.get("BASE_URL")}
    4. Verify that the number of products populated in the page equals 34, you can get the count by checking the number of 'View Product' anchor tags in the page
    5. Get all product names from <p> tags that are above the ‘Add to cart’ anchor tags, randomly select one, and enter it in the Search Product field.
    6. Click the search button
    7. Verify that user is navigated to Searched Products page
    8. Check that search results displayed in the page are matching with the product name that we entered in the 'Search Product' input field 
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
