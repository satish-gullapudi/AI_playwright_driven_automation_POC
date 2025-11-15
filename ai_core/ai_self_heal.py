import os
import json
import time
from datetime import datetime
from playwright.sync_api import Error as PlaywrightError
from ai_core.ai_logger import log_info, log_error

# Config
MAX_HEAL_RETRIES = 2
HEAL_RETRY_DELAY = 1.5
CACHE_FILE = os.path.join("ai_reports", "self_heal_cache.json")
SELF_HEAL_LOG = os.path.join("ai_reports", "logs", "self_heal_log.txt")
os.makedirs(os.path.dirname(SELF_HEAL_LOG), exist_ok=True)

# -------------------------
# Cache helpers
# -------------------------
def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache_data):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, indent=2)

def log_healing_event(old_locator, new_locator, action, status):
    os.makedirs(os.path.dirname(SELF_HEAL_LOG), exist_ok=True)
    with open(SELF_HEAL_LOG, "a", encoding="utf-8") as log:
        log.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Action: {action} | Old: {old_locator} | New: {new_locator} | Status: {status}\n")

# -------------------------
# Healing core
# -------------------------
def heal_locator(page, failed_locator, action, context_html, model):
    """
    Ask the LLM synchronously to propose an alternative selector.
    Returns new_locator (string) or None.
    """
    try:
        prompt = f"""
            You are an expert Playwright automation engineer.
            A locator failed during automation:
            - Action: {action}
            - Locator: "{failed_locator}"
            Below is a snippet of the page HTML (truncated):
            {context_html[:4000]}
            
            Suggest one best CSS or XPath selector (only the selector string in plain text). Do NOT include markdown or code fences.
            """
        resp = model.generate_content(prompt)
        new_locator = getattr(resp, "text", "") or str(resp)
        new_locator = new_locator.strip().replace("```", "").strip()
        if not new_locator:
            return None
        log_info(f"[Self-Heal] AI suggested locator: {new_locator}")
        return new_locator
    except Exception as e:
        log_error(f"[Self-Heal] heal_locator failed: {e}")
        return None

# -------------------------
# Universal try_with_healing wrapper
# -------------------------
def try_with_healing(model, page, action_func, *args, retries: int = 1, **kwargs):
    """
    Universal wrapper for Playwright actions:
    - Supports navigation-style actions (page.goto(url))
    - Supports locator-based actions (page.click(selector))
    - Performs self-healing when locator-based actions fail
    - Accepts both bound methods (page.click) and callables
    - Defensive checks and limited auto-correction for misplaced args
    """
    # Defensive auto-correction: if args look swapped (model was passed as page), attempt quick fix
    if hasattr(model, "locator") and (not hasattr(page, "locator")):
        # model looks like a Page and page looks like a Model -> swap
        log_info("[Self-Heal] Detected swapped 'model' and 'page' arguments. Auto-correcting.")
        model, page = page, model

    # Validate action_func
    if not callable(action_func):
        raise ValueError(f"action_func={action_func!r} is not callable. Correct usage: try_with_healing(model, page, page.click, locator)")

    # No args => call directly (e.g., page.reload())
    if len(args) == 0:
        try:
            return action_func(**kwargs) if kwargs else action_func()
        except Exception as e:
            log_error(f"[Self-Heal] Action failed with no-arg call: {e}")
            raise

    first = args[0]

    # If first arg is a URL => treat as navigation
    if isinstance(first, str) and (first.startswith("http://") or first.startswith("https://")):
        try:
            return action_func(first, *args[1:], **kwargs)
        except Exception as e:
            log_error(f"[Self-Heal] Navigation action failed: {e}")
            raise

    # At this point we assume it's locator-based
    locator = first
    remaining = args[1:]

    cache = load_cache()
    if isinstance(locator, str) and locator in cache:
        healed = cache[locator]
        log_info(f"[Self-Heal] Using cached healed locator: {healed}")
        locator = healed

    attempt = 0
    while attempt <= retries:
        attempt += 1
        try:
            # call action_func with locator as first arg
            return action_func(locator, *remaining, **kwargs)
        except PlaywrightError as e:
            log_info(f"[Self-Heal] Locator action failed (attempt {attempt}/{retries+1}): {locator} | err: {e}")
            # try to heal
            try:
                html = page.content()
            except Exception as ex:
                html = ""
                log_info(f"[Self-Heal] Could not get page.html for healing: {ex}")

            new_locator = heal_locator(page, locator, getattr(action_func, "__name__", "action"), html, model)
            if not new_locator or new_locator == locator:
                log_healing_event(locator, "-", getattr(action_func, "__name__", "action"), "FAILED_NO_SUGGESTION")
                log_error("[Self-Heal] No alternative found; re-raising original error.")
                raise

            # cache and retry healed locator
            cache[locator] = new_locator
            save_cache(cache)
            log_healing_event(locator, new_locator, getattr(action_func, "__name__", "action"), "HEALED_AND_RETRIED")
            log_info(f"[Self-Heal] Retrying with healed locator: {new_locator}")

            # attempt healed retries
            heal_try = 0
            while heal_try < MAX_HEAL_RETRIES:
                try:
                    return action_func(new_locator, *remaining, **kwargs)
                except PlaywrightError as e2:
                    heal_try += 1
                    log_info(f"[Self-Heal] Healed attempt {heal_try}/{MAX_HEAL_RETRIES} failed; sleeping {HEAL_RETRY_DELAY}s")
                    time.sleep(HEAL_RETRY_DELAY)

            log_healing_event(locator, new_locator, getattr(action_func, "__name__", "action"), "HEAL_FAILED_AFTER_RETRIES")
            log_error("[Self-Heal] Healed locator failed after retries; raising.")
            raise

    # If we exit loop unexpectedly
    raise PlaywrightError(f"Action failed for locator {locator} after {retries} retries.")
