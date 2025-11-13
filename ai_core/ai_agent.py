import os
import re
import asyncio
import allure
from allure_commons.types import AttachmentType
from playwright.async_api import expect

from ai_core.ai_model import GEMINI_MODEL
from ai_core.ai_self_heal import try_with_healing

class AIAgent:
    def __init__(self, task_description, page):
        self.task = task_description.strip()
        self.page = page
        self.model = GEMINI_MODEL

    async def run(self):
        print("\n🤖 [AI] Reading task and converting to Playwright actions...")
        steps = [s.strip() for s in re.split(r'\d+\.', self.task) if s.strip()]
        for i, step in enumerate(steps, 1):
            print(f"\n🧩 Step {i}: {step}")
            command = await self._translate_to_playwright(step)
            print(f"[AI] → Playwright command:\n{command}")
            try:
                await self._execute_playwright(command)
                # await self.page.screenshot(path=f"ai_reports/VideoReports/step_{i}.png")
                # await asyncio.sleep(2)  # stability delay
            except Exception as e:
                print(f"❌ Step {i} failed: {e}")
                break

    async def _translate_to_playwright(self, step_text: str):
        """
        Converts a natural language step into valid Playwright Python async code.
        Enforces strict syntax rules — no JS or Selenium code, only async Playwright Python.
        """
        prompt = f"""
    You are an expert Playwright **Python** automation engineer working in an **AI-driven self-healing framework**.

    🎯 Your task:
    Convert the following natural language test step into **valid Playwright Python async code**, using the provided helper functions and rules.

    ---

    ### 🔒 STRICT RULES:
    - ✅ Use **Playwright Python async syntax only** (from playwright.async_api)
    - ✅ Always use the given 'page' object
    - ✅ Wrap every Playwright action (click, fill, goto, wait_for_selector, etc.) using:
        await try_with_healing(page, page.<action>, "<locator>", [optional args])
    - ✅ For validation steps, use Playwright's built-in `expect()` assertions:
        await expect(page.locator("<selector>")).to_be_visible() 
    - ✅ Always include `await` before async calls
    - ✅ Always use snake_case methods (e.g., `wait_for_selector`, not `waitForSelector`)
    - ✅ Always use double quotes for strings
    - ✅ Do NOT use JavaScript syntax, Selenium code (`driver.*`), or markdown
    - ✅ Do NOT include comments, explanations, or markdown formatting
    - ✅ Output must be **only executable code**, not text description

    ---

    ### 🧩 Examples:

    **Step:** Open https://automationexercise.com  
    **Output:**
    await try_with_healing(page, page.goto, "https://automationexercise.com")

    **Step:** Click on Products link  
    **Output:**
    await try_with_healing(page, page.click, "a[href='/products']")

    **Step:** Verify All Products page is visible  
    **Output:**
    await expect(page.locator("h1:has-text('All Products')")).to_be_visible()

    **Step:** Type "T-shirt" in the search box  
    **Output:**
    await try_with_healing(page, page.fill, "input[placeholder='Search Product']", "T-shirt")

    ---

    Now, convert this step faithfully to Playwright Python async code:
    Step: "{step_text}"
    Only return the code (no markdown, no extra text).
    """
        try:
            response = self.model.generate_content(prompt)
            text = response.text or ""
        except Exception as e:
            print(f"[AI] ⚠️ LLM call failed: {e}")
            text = ""

        # 🧹 Clean up code (strip markdown if any sneaks in)
        code = text.strip().replace("```python", "").replace("```", "").strip()

        # ✅ Safety fallback (if empty response)
        if not code:
            base_url = os.environ.get("BASE_URL", "https://example.com")
            code = f'await try_with_healing(page, page.goto, "{base_url}")'

        return code

    async def _execute_playwright(self, code_block, step_description="AI Step"):
        exec_globals = {"page": self.page,
                        "asyncio": asyncio,
                        "try_with_healing": try_with_healing,
                        "expect":expect,}
        try:
            # Wrap the AI step in an Allure step
            with allure.step(step_description):
                exec(f"async def _run_step():\n    {code_block.replace(chr(10), chr(10) + '    ')}", exec_globals)
                await exec_globals["_run_step"]()
                # Attach screenshot after step execution
                screenshot = await self.page.screenshot()
                allure.attach(screenshot, name="screenshot", attachment_type=AttachmentType.PNG)
        except Exception as e:
            allure.attach(await self.page.screenshot(), name="failure", attachment_type=AttachmentType.PNG)
            allure.attach(str(e), name="error_log", attachment_type=AttachmentType.TEXT)
            raise
