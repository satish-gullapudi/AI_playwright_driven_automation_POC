import os
import re
import random
import traceback
import importlib.util
from typing import Tuple

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
    """Fix common hallucinated assertion method names to valid Playwright ones.
    Only touch method names that start with 'to_' to avoid rewriting arbitrary methods.
    """
    for pattern, repl in ASSERTION_REPLACEMENTS.items():
        code = re.sub(pattern, repl, code)

    # Only transform methods that look like assertion calls (start with 'to_')
    def _check_unknown(match):
        name = match.group(1)
        if name not in ALLOWED_ASSERTIONS:
            # fallback only if it's an assertion-like name (starts with to_)
            if name.startswith("to_"):
                return "to_be_visible"
            # otherwise leave it unchanged
            return name
        return name

    code = re.sub(r"\.(to_[a-zA-Z_0-9]+)\s*\(", lambda m: f".{_check_unknown(m)}(", code)
    code = re.sub(
        r"expect\(page\.locator\((.+?)\)\)\.to_be_visible\((.+?)\)",
        r"expect(page.locator(\1)).to_be_visible()",
        code)
    code = re.sub(
        r"to_be_visible\(['\"]placeholder['\"],\s*['\"](.+?)['\"]\)",
        r"to_have_attribute(\"placeholder\", \"\1\")",
        code)
    code = re.sub(
        r"expect\((.+?)\)\.to_have_count\(lambda.+?\)",
        r"assert \1.count() > 0",
        code)
    return code

def fix_try_with_healing_signature(code: str) -> str:
    """
    Conservative fixes for common argument-order mistakes for try_with_healing.
    Only apply a couple of safe, specific transformations to avoid double-fixing.
    """
    # If someone wrote: try_with_healing(page, page.click, ...)
    code = re.sub(
        r"try_with_healing\s*\(\s*page\s*,\s*(page\.[A-Za-z_0-9]+)",
        r"try_with_healing(model, page, \1",
        code
    )

    # If someone wrote: try_with_healing(page.click, "selector", ...)
    # (i.e. first arg is a bound method) -> insert model,page only if model is missing
    code = re.sub(
        r"try_with_healing\s*\(\s*(page\.[A-Za-z_0-9]+)\s*,",
        r"try_with_healing(model, page, \1,",
        code
    )

    # Avoid making changes in strings / comments by being conservative.
    return code

def validate_final_code(code: str) -> str:
    """
    Final sanitization pipeline:
    - remove async/await
    - fix try_with_healing signatures (conservative)
    - sanitize assertions
    - reliably convert page.to_be_visible("sel") forms to expect(page.locator(...)).to_be_visible()
    """
    code = remove_async_tokens(code)
    code = fix_try_with_healing_signature(code)
    code = sanitize_assertions(code)

    # Robustly convert page.to_be_visible("selector") and page.to_have_count('sel') etc.
    # This regex matches both single and double quoted strings and tolerates whitespace.
    code = re.sub(
        r"page\.\s*(to_be_visible|to_have_count|to_have_text)\s*\(\s*([\"'])(.+?)\2\s*\)",
        lambda m: (
            "expect(page.locator(%s)).%s()" % (repr(m.group(2) + m.group(3) + m.group(2)), "to_be_visible")
            if m.group(1) == "to_be_visible"
            else ("expect(page.locator(%s)).to_have_count(1)" % repr(m.group(2) + m.group(3) + m.group(2)))
        ),
        code,
        flags=re.DOTALL,
    )

    # Remove invalid assignments like: var = expect(...).to_be_visible()
    code = re.sub(
        r"^[A-Za-z_][A-Za-z0-9_]*\s*=\s*expect\([^\)]+\)\.[^\n]+",
        lambda m: m.group(0).split("=", 1)[1].strip(),
        code,
        flags=re.MULTILINE
    )

    # REMOVE ANY IMPORT STATEMENTS — hallucinated imports break execution in the agent runtime
    code = re.sub(r"^\s*(import|from)\s+[^\n]+", "", code, flags=re.MULTILINE)

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
- Must and should, add comments as below mentioned in case of conditional statements like 'if-else' or 'if-elif' blocks:
    - # conditional statement begins
    - # conditional statement ends
- Must and should, add comments as below mentioned in case of looping statements like 'for' loop:
    - # loop begins
    - # loop ends
- Below is invalid assertion
    expect(page.to_be_visible("input[placeholder='Search Product']")).to_be_visible()
- Valid assertion is below
    expect(page.locator("input[placeholder='Search Product']")).to_be_visible()
- Make sure to quote the attributes value in locator to be single quotes, not double quotes:
    Invalid format - try_with_healing(model, page, page.click, "a[href="/products"]")
    Valid format - try_with_healing(model, page, page.click, "a[href='/products']")
- DO NOT invent new assertion method names.
- If you need to get text contents from many elements, use page.locator("<selector>").all_text_contents()
- Return ONLY executable Python code (no markdown, no explanation, no comments).
- DO NOT write any import statements.
- DO NOT use any external modules.
- DO NOT invent modules like 'playwright_healing_wrapper'.

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

        if "import " in code_block or "from " in code_block:
            log_error("[AIAgent] Illegal import detected in LLM output. Removing it.")
            code_block = re.sub(r"^\s*(import|from)\s+[^\n]+", "", code_block, flags=re.MULTILINE)

        # Wrap the code into a function to keep locals clean and use allure.step
        wrapper = "def _run_step():\n"
        for line in code_block.splitlines():
            wrapper += "    " + line + "\n"

        try:
            with allure.step(step_description):
                exec(wrapper, exec_globals)
                try:
                    exec_globals["_run_step"]()
                except Exception as e_exec:
                    tb = traceback.format_exc()
                    log_error(f"[AIAgent] Execution failed in AI-generated step: {e_exec}\n{tb}")
                    # attach screenshot if possible
                    try:
                        allure.attach(self.page.screenshot(), name="failure", attachment_type=AttachmentType.PNG)
                    except Exception:
                        pass
                    raise
                try:
                    screenshot = self.page.screenshot()
                    allure.attach(screenshot, name="screenshot", attachment_type=AttachmentType.PNG)
                except Exception:
                    pass
        except Exception as e:
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
                # Attempt to extract a page.locator("...").all_text_contents() pattern and replace it
                m = re.search(r'page\.locator\(\s*([\'"])(.+?)\1\s*\)\.all_text_contents\(\)', code)
                if m:
                    selector = m.group(2)
                    code = re.sub(r'page\.locator\(\s*([\'"])(.+?)\1\s*\)\.all_text_contents\(\)',
                                  f"fallback_locator_list({repr(selector)})",
                                  code)
                # re-sanitize after changes
                code = validate_final_code(code)
            self._wrap_and_execute(code, f"AI Step {i}: {desc}")

    # ----------------------------
    # New: Generate a source file in ai_tests/src if missing
    # ----------------------------
    def generate_source_if_missing(self, test_name: str) -> Tuple[str, bool]:
        """
        If ai_tests/src/<test_name>.py doesn't exist, ask the AI model to convert
        the entire `self.task` into a runnable function and save it there.

        Returns (file_path, created_bool).
        """
        # compute src folder: project_root/ai_tests/src
        project_root = os.path.dirname(os.path.dirname(__file__))  # parent of ai_core/
        src_dir = os.path.join(project_root, "ai_tests", "src")
        os.makedirs(src_dir, exist_ok=True)

        safe_name = re.sub(r"[^A-Za-z0-9_]", "_", test_name)
        file_path = os.path.join(src_dir, f"{safe_name}.py")

        if os.path.exists(file_path):
            log_info(f"⚡ Source code already exists: {file_path}. Skipping AI generation.")
            return file_path, False
        else:
            log_info(f"🤖 Generating new automation code for {test_name} at {file_path} ...")
            print(f"🤖 Generating new automation code for {test_name} at {file_path} ...")

            # Craft a conservative prompt: ask for function body only (no imports)
            # prompt = f"""
            #     You are an expert Playwright Python automation engineer that writes self-healing Playwright tests.
            #     Convert the following test case (steps) into Python code suitable for this project's sync Playwright wrappers.
            #     - ONLY return the function body lines (no imports, no markdown).
            #     - The resulting file will be wrapped into: def run(page, model): <body>
            #     - Use only try_with_healing(model, page, page.<action>, "<locator>", [args...]) for actions.
            #     - Use expect(page.locator("...")).to_be_visible() / to_have_count(n) etc for assertions (allowed ones).
            #     - If you need to get lists of text use page.locator("...").all_text_contents()
            #     - Do NOT include 'async' or 'await'.
            #     - Do NOT include import statements.
            #     - In case of conditional statements like 'if-else' or 'if-elif' blocks, leave comments before starting and ending the statement as below:
            #         - # conditional statement begins
            #         - # conditional statement ends
            #     - In case of looping statements like 'for' loop, leave comments before starting and ending the loop as below:
            #         - # loop begins
            #         - # loop ends
            #     Here are the test steps to convert:
            #     {self.task}
            #     """
            prompt = self._build_prompt(self.task)
            try:
                response = self.model.generate_content(prompt)
                # print(response)
                raw = getattr(response, "text", "") or str(response)
            except Exception as e:
                log_error(f"[AI] LLM call failed while generating source file: {e}")
                raw = ""

            code_body = raw.strip().replace("```python", "").replace("```", "").strip()
            if not code_body:
                # safe fallback minimal flow
                code_body = f'try_with_healing(model, page, page.goto, os.environ.get("BASE_URL", "https://example.com"))\n'

                # Sanitize and finalize
            code_body = validate_final_code(code_body)
            code_body = fix_try_with_healing_signature(code_body)

            # === BUILD FINAL GENERATED FILE CONTENT ===
            final_file_content ='import os'
            final_file_content += '\nimport random'
            final_file_content += '\nfrom playwright.sync_api import expect'
            final_file_content += '\nfrom ai_core.ai_self_heal import try_with_healing, heal_locator'
            final_file_content += '\ndef run(page, model):\n'

            # ---- CRITICAL NORMALIZATION FIX ----
            clean_lines = []
            for raw in code_body.splitlines():

                # Remove ALL leading indentation
                stripped = raw.lstrip()

                # Skip blank lines
                if not stripped:
                    continue

                # Fix cases where AI outputs "page.fill(..., [value])"
                stripped = stripped.replace("[selected_product_name]", "selected_product_name")

                # Fix AI hallucination: arguments must not be lists
                stripped = stripped.replace("[", "").replace("]", "") \
                    if "page.fill" in stripped and "selected_product_name" in stripped else stripped

                # Fix invalid expect(...).to_have_count(lambda...)
                stripped = re.sub(
                    r"expect\((.+?)\)\.to_have_count\(lambda.+?\)",
                    r"assert \1.count() > 0",
                    stripped
                )

                # Ensure loops are correct
                if stripped.startswith("for ") and stripped.endswith(":"):
                    clean_lines.append(stripped)
                    continue

                clean_lines.append(stripped)

            # ---- APPLY CORRECT INDENTATION ----
            print(clean_lines)
            for line in clean_lines:
                # if statement lines indentation
                if 'conditional statement begins' in line:
                    start = clean_lines.index(line)
                    end = clean_lines.index("# conditional statement ends")
                    conditional_lines = clean_lines[start:end + 1]
                    for line_ in conditional_lines:
                        if line_.startswith("#") or \
                                (line_.startswith("if ") and line_.endswith(":")) or \
                                (line_.startswith("else") and line_.endswith(":")):
                            final_file_content += "    " + line_ + "\n"
                        else:
                            final_file_content += "        " + line_ + "\n"
                        clean_lines.remove(line_)

                # for loop lines indentation
                elif 'loop begins' in line:
                    start = clean_lines.index(line)
                    end = clean_lines.index("# loop ends")
                    loop_lines = clean_lines[start:end + 1]
                    for line_ in loop_lines:
                        if line_.startswith("#") or (line_.startswith("for ") and line_.endswith(":")):
                            final_file_content += "    " + line_ + "\n"
                        else:
                            final_file_content += "        " + line_ + "\n"
                        clean_lines.remove(line_)
                else:
                    # Regular line
                    final_file_content += "    " + line + "\n"

            # ---- SAVE FILE ----
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(final_file_content)
            return file_path, True
