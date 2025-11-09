import os
from pathlib import Path
from playwright.async_api import async_playwright

video_dir = os.path.join(Path.cwd(), "ai_reports", "VideoReports")
os.makedirs(video_dir, exist_ok=True)

async def get_browser(headless=False):
    playwright = await async_playwright().start()
    chromium = playwright.chromium
    browser = await chromium.launch(headless=headless)
    context = await browser.new_context(
        record_video_dir=video_dir,
        record_video_size={'width': 1920, 'height': 1080}
    )
    page = await context.new_page()
    return playwright, browser, context, page, video_dir
