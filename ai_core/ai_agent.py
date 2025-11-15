# AI_automation_framework/ai_core/ai_agent.py
import os
import re
import random
import textwrap
import inspect
import allure
from allure_commons.types import AttachmentType
from playwright.sync_api import expect
from ai_core.ai_self_heal import try_with_healing, heal_locator
from ai_core.ai_logger import log_info, log_error

# ----------------------------
# Sanitizers & Helpers
# ----------------------------
ASSERTION_REPLACEMENTS = {
    # wrong -> (replacement_func) where replacement_func receives (match_obj) and returns new text
    r"to_have_count_greater_than\s*\(\s*(\d+)\s*\)": lambda m: f"to_have_count({max(1, int(m.group(1)))})",
    r"to_have_more_than\s*\(\s*(\d+)\s*\)": lambda m: f"to_have_count({max(1, int(m.group(1)))})",
    r"to_be_non_empty\s*\(\s*\)": lambda m: "to_have_count(1)",
    r"to_exist\s*\(\s*\)": lambda m: "to_be_visible()",
}

# Allowed assertion names (used for prompt and a final check)
ALLOWED_ASSERTIONS = [
    "to_be_visible",
    "to_have_count",
    "to_have_text",
    "to_contain_text",
    "to_have_url",
    "to_have_title",
    "to_be_hidden",
]

def remove_async_tokens(code: str) -> str:
    """Strip accidental 'await'/'async' tokens produced by LLM output."""
    code = re.sub(r"\bawait\s+", "", code)
    code = re.sub(r"\basync\s+", "", code)
    return code

def sanitize_assertions(code: str) -> str:
    """Fix common hallucinated assertion method names to valid Playwright ones."""
    for pattern, repl in ASSERTION_REPLACEMENTS.items():
        code = re.sub(pattern, repl, code)
    # Final safety: if any unknown 'to_' method is present, try to map to to_be_visible or remove
    def _check_unknown(match):
        name = match.group(1)
        if name not in ALLOWED_ASSERTIONS:
            # fallback to to_be_visible or remove parentheses if already has args
            return "to_be_visible"
        return name
    code = re.sub(r"\.([a-zA-Z_0-9]+)\s*\(", lambda m: f".{_check_unknown(m)}(", code)
    return code

def fix_try_with_healing_signature(code: str) -> str:
    """
    Auto-correct common argument-order mistakes for try_with_healing produced by LLM.
    - Ensure calls look like: try_with_healing(model, page, page.click, "selector", ...)
    - If the call starts with try_with_healing(page, page.click, ...), swap to model,page
    - If the call is try_with_healing(page.click, "selector"), add model and page
    """
    # Pattern 1: try_with_healing(page, page.click, ...)
    code = re.sub(
        r"try_with_healing\s*\(\s*page\s*,\s*(page\.[A-Za-z_0-9]+)",
        r"try_with_healing(model, page, \1",
        code
    )

    # Pattern 2: try_with_healing(page.click, "selector", ...)
    code = re.sub(
        r"try_with_healing\s*\(\s*(page\.[A-Za-z_0-9]+)\s*,",
        r"try_with_healing(model, page, \1,",
        code
    )

    # Pattern 3: try_with_healing\(page, "http..."\) -> navigation form -> fix to model,page, page.goto
    code = re.sub(
        r"try_with_healing\s*\(\s*page\s*,\s*([\"']https?://[^\"']+[\"'])\s*\)",
        r"try_with_healing(model, page, page.goto, \1)",
        code
    )

    return code

def validate_final_code(code: str) -> str:
    """
    Final sanitization pipeline:
    - remove async/await
    - fix try_with_healing signatures
    - sanitize assertions
    """
    code = remove_async_tokens(code)
    code = fix_try_with_healing_signature(code)
    code = sanitize_assertions(code)

    # ---------------------------------------------------
    # Fix hallucinations: page.to_be_visible("selector")
    # ---------------------------------------------------
    code = re.sub(
        r"page\.to_be_visible\(\s*([\"'][^\"']+[\"'])\s*\)",
        r"expect(page.locator(\1)).to_be_visible()",
        code
    )

    # ---------------------------------------------------
    # Fix hallucinations: page.to_have_count("selector")
    # ---------------------------------------------------
    code = re.sub(
        r"page\.to_have_count\(\s*([\"'][^\"']+[\"'])\s*\)",
        r"expect(page.locator(\1)).to_have_count(1)",
        code
    )

    # ---------------------------------------------------
    # Remove invalid assignments:
    #   var = expect(...).to_be_visible()
    # ---------------------------------------------------
    code = re.sub(
        r"^[A-Za-z_][A-Za-z0-9_]*\s*=\s*expect\([^\)]+\)\.[^\n]+",
        lambda m: m.group(0).split("=", 1)[1].strip(),
        code,
        flags=re.MULTILINE
    )

    # ---------------------------------------------------
    # Convert any pattern:
    #   var = page.locator("x")
    #   expect(var).to_be_visible()
    # (These are OK — do not modify)
    # ---------------------------------------------------
    return code

# ----------------------------
# DOM Fallback resolver
# ----------------------------
def fallback_locator_list(page, locator_str, model=None):
    """
    Given a Playwright page and a locator string, attempt multiple fallback strategies
    to return a list of text contents. Uses heal_locator(model...) only as last resort.
    Returns list (possibly empty).
    """
    log_info(f"[Fallback] Trying locator: {locator_str}")

    try:
        locator = page.locator(locator_str)
        items = locator.all_text_contents()
        if items:
            log_info(f"[Fallback] Found {len(items)} items using exact locator.")
            return items
    except Exception as e:
        log_info(f"[Fallback] exact locator call failed: {e}")

    # Strategy 1: remove :has(...) pseudo selectors (Playwright pseudo)
    cleaned = re.sub(r":has\([^\)]*\)", "", locator_str)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    if cleaned and cleaned != locator_str:
        try:
            items = page.locator(cleaned).all_text_contents()
            if items:
                log_info(f"[Fallback] Found {len(items)} items using cleaned locator: {cleaned}")
                return items
        except Exception:
            pass

    # Strategy 2: simplify CSS by removing classes to tag-only queries
    simplified = re.sub(r"\.[A-Za-z0-9_-]+", "", cleaned or locator_str)
    simplified = re.sub(r"\s{2,}", " ", simplified).strip()
    if simplified and simplified != locator_str:
        try:
            items = page.locator(simplified).all_text_contents()
            if items:
                log_info(f"[Fallback] Found {len(items)} items using simplified locator: {simplified}")
                return items
        except Exception:
            pass

    # Strategy 3: search generic product text nodes - common patterns
    common_patterns = [
        "div.productinfo p",
        "div.product-information p",
        "div.product p",
        "div.item p",
        "p"
    ]
    for pat in common_patterns:
        try:
            items = page.locator(pat).all_text_contents()
            if items:
                log_info(f"[Fallback] Found {len(items)} items using pattern: {pat}")
                return items
        except Exception:
            pass

    # Strategy 4: Ask the LLM to suggest a better locator using the real page HTML (if model provided)
    if model is not None:
        try:
            html = page.content()
            suggested = heal_locator(page, locator_str, "bulk-list", html, model)
            if suggested:
                try:
                    items = page.locator(suggested).all_text_contents()
                    if items:
                        log_info(f"[Fallback] Found {len(items)} items using AI-suggested locator.")
                        return items
                except Exception:
                    log_info("[Fallback] AI suggested locator failed to query.")
        except Exception as e:
            log_info(f"[Fallback] AI heal attempt failed: {e}")

    log_info("[Fallback] No items found with fallback strategies.")
    return []

# ----------------------------
# AIAgent (sync)
# ----------------------------
class AIAgent:
    def __init__(self, task_description: str, page, model):
        self.task = task_description.strip()
        self.page = page
        self.model = model

    def _build_prompt(self, step_text: str) -> str:
        """
        Strongly-guided prompt to force synchronous Playwright output and specific wrappers.
        The prompt enforces:
          - use of try_with_healing(model, page, page.<action>, "<locator>", ...)
          - only allowed expect() assertions
          - synchronous Playwright (no await/async)
        """
        base_url = os.environ.get("BASE_URL")
        prompt = f"""
You are an expert Playwright Python automation engineer in a self-healing framework.
Convert this single test step into valid, **synchronous** Playwright Python code that uses the 'page' object.
Important rules:
- Use only Playwright Python sync API (from playwright.sync_api).
- DO NOT emit 'async' or 'await'.
- For element actions use the wrapper: try_with_healing(model, page, page.<action>, "<locator>", [args...])
  Example: try_with_healing(model, page, page.click, "button#submit")
- For navigation use: try_with_healing(model, page, page.goto, "https://...") or expect(page).to_have_url("...")
- Allowed assertions (only these):
  expect(locator).to_be_visible()
  expect(locator).to_have_count(n)
  expect(locator).to_have_text([...])
  expect(locator).to_contain_text("text")
  expect(page).to_have_url("url")
  expect(page).to_have_title("title")
- Below is invalid assertion
    expect(page.to_be_visible("input[placeholder='Search Product']")).to_be_visible()
- Valid assertion is below
    expect(page.locator("input[placeholder='Search Product']")).to_be_visible()
- DO NOT invent new assertion method names.
- If you need to get text contents from many elements, use page.locator("<selector>").all_text_contents()
- Return ONLY executable Python code (no markdown, no explanation, no comments).
Step: "{step_text}"
Note: If the step references the site root, assume base url is {base_url}
"""
        return prompt

    def _translate_to_playwright(self, step_text: str) -> str:
        prompt = self._build_prompt(step_text)
        try:
            response = self.model.generate_content(prompt)
            raw = getattr(response, "text", "") or str(response)
        except Exception as e:
            log_error(f"[AI] LLM call failed: {e}")
            raw = ""

        code = raw.strip().replace("```python", "").replace("```", "").strip()
        if not code:
            # fallback minimal safe action
            code = f'try_with_healing(model, page, page.goto, "{os.environ.get("BASE_URL", "https://example.com")}")'

        # final sanitization pass
        code = validate_final_code(code)
        # auto-fix signature ordering mistakes
        code = fix_try_with_healing_signature(code)
        return code

    def _wrap_and_execute(self, code_block: str, step_description: str = "AI Step"):
        """
        Execute the generated code safely by injecting a controlled globals dict.
        Adds helpers: page, expect, try_with_healing, model, fallback_locator_list, random.
        """
        exec_globals = {
            "page": self.page,
            "expect": expect,
            "try_with_healing": try_with_healing,
            "model": self.model,
            "fallback_locator_list": lambda locator: fallback_locator_list(self.page, locator, self.model),
            "random": random,
            # builtin safe helpers
            "__name__": "__ai_step__",
        }

        # Wrap the code into a function to keep locals clean and use allure.step
        wrapper = "def _run_step():\n"
        for line in code_block.splitlines():
            wrapper += "    " + line + "\n"

        try:
            with allure.step(step_description):
                exec(wrapper, exec_globals)
                exec_globals["_run_step"]()
                try:
                    screenshot = self.page.screenshot()
                    allure.attach(screenshot, name="screenshot", attachment_type=AttachmentType.PNG)
                except Exception:
                    # non-fatal: continue
                    pass
        except Exception as e:
            try:
                allure.attach(self.page.screenshot(), name="failure", attachment_type=AttachmentType.PNG)
            except Exception:
                pass
            log_error(f"[AIAgent] Execution failed: {e}")
            raise

    def run(self):
        log_info("🤖 [AI] Reading task and converting to Playwright actions...")
        steps = [s.strip() for s in re.split(r'\d+\.', self.task) if s.strip()]
        for i, step in enumerate(steps, 1):
            desc = (step[:80] + "...") if len(step) > 80 else step
            log_info(f"🧩 Step {i}: {step}")
            code = self._translate_to_playwright(step)
            log_info(f"[AI] → Playwright command (step {i}):\n{code}")
            # Detect common pattern where LLM directly collects names then random.choice([]). Replace with fallback wrapper
            if ".all_text_contents()" in code and "random.choice" in code:
                # Ensure the code uses the fallback_locator_list helper to avoid empty sequence
                code = re.sub(r"([A-Za-z0-9_.\[\]\"' >:-]+)\.all_text_contents\(\)", r"fallback_locator_list(r'\1')", code)
                # Re-sanitize after regex edits
                code = validate_final_code(code)
            self._wrap_and_execute(code, f"AI Step {i}: {desc}")
