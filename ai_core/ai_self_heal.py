from datetime import datetime
import inspect
import asyncio
import os
import json
from playwright.async_api import Error as PlaywrightError
from ai_core.ai_model import GEMINI_MODEL

# 🔧 Retry configuration
MAX_HEAL_RETRIES = 2          # number of retries for healed locator
HEAL_RETRY_DELAY = 1.5        # seconds between retries

CACHE_FILE = os.path.join("ai_reports", "self_heal_cache.json")

SELF_HEAL_LOG = os.path.join("ai_reports", "logs", "self_heal_log.txt")
os.makedirs(os.path.dirname(SELF_HEAL_LOG), exist_ok=True)

# -------------------------
# 🔹 Cache Helpers
# -------------------------
def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_cache(cache_data):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, indent=4)

def log_healing_event(old_locator, new_locator, action, status):
    """
    Log every healing attempt with timestamp, locator info, and result.
    """
    os.makedirs(os.path.dirname(SELF_HEAL_LOG), exist_ok=True)
    with open(SELF_HEAL_LOG, "a", encoding="utf-8") as log:
        log.write(
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            f"Action: {action} | "
            f"Old: {old_locator} | "
            f"New: {new_locator} | "
            f"Status: {status}\n"
        )

# -------------------------
# 🔹 Healing Core
# -------------------------
async def heal_locator(page, failed_locator, action, context_html):
    """
    Ask Gemini to suggest an alternative selector when an element isn't found.
    """
    prompt = f"""
    You are an expert Playwright automation engineer.
    The following locator failed during a test:
    - Action: {action}
    - Locator: "{failed_locator}"

    Below is the relevant HTML snippet of the page:
    {context_html[:3000]}

    Suggest a single best alternative selector for the same element.
    Return only the selector (no markdown, no code fences, no comments).
    """

    try:
        response = GEMINI_MODEL.generate_content(prompt)
        new_locator = response.text.strip().replace("```", "").strip()
        print(f"[Self-Heal] 🤖 Suggested new locator → {new_locator}")
        return new_locator
    except Exception as e:
        print(f"[Self-Heal] ❌ AI healing failed: {e}")
        return None

# -------------------------
# 🔹 Healing Wrapper
# -------------------------
async def try_with_healing(page, action_func, locator, *args, retries=1, **kwargs):
    """
    Wraps Playwright actions with self-healing retry logic.
    Handles both async and sync functions (like get_by_label).
    Supports positional + keyword args (including AI dicts/lists).
    """
    cache = load_cache()

    # 🔍 Fix for AI-generated [{"state": "visible"}] style arguments
    if args and isinstance(args[0], (dict, list)):
        maybe_kwargs = args[0]
        if isinstance(maybe_kwargs, list) and maybe_kwargs and isinstance(maybe_kwargs[0], dict):
            maybe_kwargs = maybe_kwargs[0]
        if isinstance(maybe_kwargs, dict):
            kwargs.update(maybe_kwargs)
            args = args[1:]  # remove that dict from positional args
            print(f"[Self-Heal] 🧠 Converted AI-style arguments into keyword args: {kwargs}")

    # ♻️ Use cached locator if available
    if locator in cache:
        healed_locator = cache[locator]
        print(f"[Self-Heal] ♻️ Using cached healed locator: {healed_locator}")
        log_healing_event(locator, healed_locator, action_func.__name__, "CACHE_USED")
        locator = healed_locator

    for attempt in range(retries + 1):
        try:
            # 🧩 Detect whether action_func is async or sync
            if inspect.iscoroutinefunction(action_func):
                result = await action_func(locator, *args, **kwargs)
            else:
                result = action_func(locator, *args, **kwargs)

            return result

        except PlaywrightError as e:
            print(f"[Self-Heal] ⚠️ Locator failed: {locator}")
            context_html = await page.content()

            # Ask Gemini for alternative locator
            new_locator = await heal_locator(page, locator, action_func.__name__, context_html)
            if not new_locator or new_locator == locator:
                log_healing_event(locator, "-", action_func.__name__, "FAILED_NO_SUGGESTION")
                print("[Self-Heal] ❌ No valid alternative found. Test will fail.")
                raise

            # Save to cache
            cache[locator] = new_locator
            save_cache(cache)
            log_healing_event(locator, new_locator, action_func.__name__, "HEALED_AND_RETRIED")
            print(f"[Self-Heal] ✅ Cached new locator: {locator} → {new_locator}")

            # 🔁 Retry loop for healed locator
            for heal_try in range(1, MAX_HEAL_RETRIES + 1):
                try:
                    print(f"[Self-Heal] 🔁 Retrying healed locator (Attempt {heal_try}/{MAX_HEAL_RETRIES})")
                    if inspect.iscoroutinefunction(action_func):
                        return await action_func(new_locator, *args, **kwargs)
                    else:
                        return action_func(new_locator, *args, **kwargs)
                except PlaywrightError:
                    print(f"[Self-Heal] ⏳ Retrying in {HEAL_RETRY_DELAY}s...")
                    await asyncio.sleep(HEAL_RETRY_DELAY)

            log_healing_event(locator, new_locator, action_func.__name__, "HEAL_FAILED_AFTER_RETRIES")
            print(f"[Self-Heal] ❌ Healed locator still failed after {MAX_HEAL_RETRIES} retries.")
            raise
