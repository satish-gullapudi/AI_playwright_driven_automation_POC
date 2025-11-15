import os
from pathlib import Path
import pytest

from playwright.sync_api import sync_playwright

from ai_core.ai_logger import log_info

@pytest.fixture
def setup(request):
    """
    Provides a single Playwright page per test. Teardown closes context and browser.
    Use BASE_URL and HEADLESS env vars.
    """
    root_dir = Path(__file__).resolve().parent.parent
    video_dir = os.path.join(root_dir, "ai_reports", "VideoReports")
    os.makedirs(video_dir, exist_ok=True)

    pw = sync_playwright().start()
    chromium = pw.chromium
    browser = chromium.launch(headless=False)

    context_opts= {"record_video_dir": video_dir,
                   "record_video_size": {"width": 1280, "height": 720}}

    context = browser.new_context(**context_opts)
    page = context.new_page()
    # page.goto(os.environ.get("BASE_URL"))
    yield page
    try:
        context.close()
        browser.close()
        pw.stop()
        log_info("Browser closed")
    except Exception as e:
        log_info(f"Error closing browser: {e}")
    finally:
        log_info(f"🎥 Video saved in: {video_dir}")
