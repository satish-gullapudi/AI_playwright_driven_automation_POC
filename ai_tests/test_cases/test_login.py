import os
import importlib.util
from ai_core.ai_agent import AIAgent
from ai_core.ai_model import GEMINI_MODEL
from ai_core.ai_logger import log_info, log_error

def _import_module_from_path(module_name: str, path: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_login_flow(setup):
    """
    Synchronous pytest test that uses the AIAgent to either:
      - generate ai_tests/src/search_product_flow.py (first run), or
      - import and reuse existing source file (subsequent runs).
    """
    log_info("🔹 Starting AI-driven Search Product Test (test wrapper)")

    page = setup
    task = f"""
    1. Click Signup/Login navigation link in header
    2. Enter 'satishpaktolus22@gmail.com' in the Email Address input field
    3. Enter 'pass@123' in the Password input field
    4. Click Login button
    5. Wait for 10 seconds
    6. Check if there is Logout navigation link in the header 
    """

    # test name decides the filename in ai_tests/src/
    test_name = "login_flow"

    agent = AIAgent(task, page, GEMINI_MODEL)

    try:
        # 1) Generate file if missing (only first run will call the model)
        file_path, created = agent.generate_source_if_missing(test_name)
        if created:
            log_info(f"AI created source file at {file_path}")

        # 2) Import the generated (or existing) module
        module = _import_module_from_path(test_name, file_path)

        # 3) Run the module's run() function
        # Pass GEMINI_MODEL so the generated code (if it uses healing) can access the same model via parameter
        module.run(page, GEMINI_MODEL)

        log_info("✅ Test completed successfully.")
    except Exception as e:
        log_error(f"❌ Test failed: {e}")
        raise
