import os
from ai_core.ai_agent import AIAgent
from ai_core.ai_model import GEMINI_MODEL
from ai_core.ai_logger import log_info, log_error

def test_search_product_flow(setup):
    """
    Synchronous pytest test that uses the AIAgent to run steps.
    """
    log_info("🔹 Starting AI-driven Search Product Test")
    page = setup
    task = f""" 
    1. Open website {os.environ.get("BASE_URL")} 
    2. Click 'Products' link in header and wait for the page to load
    3. Verify user is navigated to All Products page successfully by checking that the url matches {os.environ.get("BASE_URL")}products
    4. Verify there is a search input box with place holder 'Search Product'
    5. Verify that the number of products populated in the page equals 34, you can get the count by checking the number of 'View Product' anchor tags in the page
    6. Get all product names from <p> tags that are above the ‘Add to cart’ anchor tags, randomly select one, and then enter it in the Search Product field.
    7. Click the search button next to 'Search Product' input field
    8. Verify that user is navigated to 'Searched Products' page
    9. Fetch the text from 'Search Product' input field and verify that the products under the 'Searched Products' are matching with the fetched text
    """

    agent = AIAgent(task, page, GEMINI_MODEL)

    try:
        agent.run()
        log_info("✅ Test completed successfully.")
    except Exception as e:
        log_error(f"❌ Test failed: {e}")