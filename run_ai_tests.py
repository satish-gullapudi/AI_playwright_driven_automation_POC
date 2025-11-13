import asyncio
from AI_automation_framework.ai_core.ai_runner import run_all_tests
import subprocess

if __name__ == "__main__":
    asyncio.run(run_all_tests())

# # After all tests are executed
# subprocess.run(["allure", "generate", "allure-results", "-o", "AI_automation_framework/ai_reports/AllureReport", "--clean"])
