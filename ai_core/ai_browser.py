# AI_automation_framework/ai_core/ai_browser.py
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

video_dir = os.path.join(Path.cwd(), "ai_reports", "VideoReports")
os.makedirs(video_dir, exist_ok=True)

def get_browser(headless: bool = True, record_video: bool = False):
    """
    Returns (playwright, browser, context, page, video_dir).
    Use context.close() and browser.close() in teardown.
    """
    pw = sync_playwright().start()
    chromium = pw.chromium
    browser = chromium.launch(headless=headless)
    context_opts = {}
    if record_video:
        context_opts["record_video_dir"] = video_dir
        context_opts["record_video_size"] = {"width": 1280, "height": 720}

    context = browser.new_context(**context_opts)
    page = context.new_page()
    return pw, browser, context, page, video_dir
