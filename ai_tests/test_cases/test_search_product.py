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

def test_search_product_flow(setup):
    """
    Synchronous pytest test that uses the AIAgent to either:
      - generate ai_tests/src/search_product_flow.py (first run), or
      - import and reuse existing source file (subsequent runs).
    """
    log_info("🔹 Starting AI-driven Search Product Test (test wrapper)")

    page = setup
    task = f"""  
    2. Click 'Products' link in header and wait for the page to load
    3. Verify user is navigated to All Products page successfully by checking that the url matches {os.environ.get("BASE_URL")}products
    4. Verify there is a search input box with place holder 'Search Product'
    5. Verify that the number of products populated in the page equals 34, you can get the count by checking the number of 'View Product' anchor tags in the page
    6. Get all product names from <p> tags that are above the ‘Add to cart’ anchor tags, randomly select one, and then enter it in the Search Product field.
    7. Click the search button next to 'Search Product' input field
    8. Verify that user is navigated to 'Searched Products' page
    9. Fetch the text from 'Search Product' input field and verify that the products under the 'Searched Products' are matching with the fetched text
    """

    # test name decides the filename in ai_tests/src/
    test_name = "search_product_flow"

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
