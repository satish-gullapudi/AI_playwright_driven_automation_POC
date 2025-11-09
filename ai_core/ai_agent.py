import os
import re
import asyncio
from ai_core.ai_model import GEMINI_MODEL

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
                await self.page.screenshot(path=f"ai_reports/VideoReports/step_{i}.png")
                await asyncio.sleep(2)  # stability delay
            except Exception as e:
                print(f"❌ Step {i} failed: {e}")
                break

    async def _translate_to_playwright(self, step_text):
        prompt = f"""
        You are an expert Playwright test engineer.
        Convert the following instruction into executable Playwright async Python code using 'page':
        Step: "{step_text}"

        Use commands like:
        - await page.goto(url)
        - await page.click(selector)
        - await page.fill(selector, text)
        - await page.locator("text=...").is_visible()
        Only output valid Python statements — no explanations or markdown.
        """
        try:
            response = self.model.generate_content(prompt)
            text = response.text or ""
        except Exception as e:
            print(f"[AI] ⚠️ LLM call failed: {e}")
            text = ""

        code = text.strip().split("```python")[-1].replace("```", "").strip()
        return code or f"await page.goto('{os.environ.get("BASE_URL")}')"

    async def _execute_playwright(self, code_block):
        exec_globals = {"page": self.page, "asyncio": asyncio}
        try:
            exec(f"async def _run_step():\n    {code_block.replace(chr(10), chr(10)+'    ')}", exec_globals)
            await exec_globals["_run_step"]()
        except Exception as e:
            print(f"⚠️ Error executing AI command: {e}")
            raise
