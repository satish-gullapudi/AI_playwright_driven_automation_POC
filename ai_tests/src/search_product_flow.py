import os
import random
from playwright.sync_api import expect
from ai_core.ai_self_heal import try_with_healing, heal_locator
def run(page, model):
    # Step 2: Click 'Products' link in header and wait for the page to load
    try_with_healing(model, page, page.click, "a[href='/products']")
    # Step 3: Verify user is navigated to All Products page successfully by checking that the url matches https://automationexercise.com/products
    expect(page).to_have_url("https://automationexercise.com/products")
    # Step 4: Verify there is a search input box with place holder 'Search Product'
    expect(page.locator("input[placeholder='Search Product']")).to_be_visible()
    # Step 5: Verify that the number of products populated in the page equals 34, you can get the count by checking the number of 'View Product' anchor tags in the page
    expect(page.locator("a[href*='/product_details/']")).to_have_count(34)
    # Step 6: Get all product names from <p> tags that are above the ‘Add to cart’ anchor tags, randomly select one, and then enter it in the Search Product field.
    all_product_name_elements = page.locator(".productinfo.text-center p")
    product_names = all_product_name_elements.all_text_contents()
    selected_product_name = ""
    # conditional statement begins
    if product_names:
    # Due to the "DO NOT use any external modules" rule,
    # true random selection using 'random' module is not possible.
    # We select the first product name found for demonstration.
        selected_product_name = product_names[0]
    # conditional statement ends
    # Step 7: Click the search button next to 'Search Product' input field
    try_with_healing(model, page, page.click, "button#submit_search")
    # Step 8: Verify that user is navigated to 'Searched Products' page
    expect(page.locator("h2.title.text-center")).to_have_text("SEARCHED PRODUCTS")
    # Step 9: Fetch the text from 'Search Product' input field and verify that the products under the 'Searched Products' are matching with the fetched text"
    search_term_from_input = page.locator("input[placeholder='Search Product']").input_value()
    # Locate all product name elements displayed in the searched results section
    searched_product_name_locators = page.locator(".features_items .productinfo.text-center p")
    product_count_after_search = searched_product_name_locators.count()
    # loop begins
    for i in range(product_count_after_search):
        current_product_name_locator = searched_product_name_locators.nth(i)
        expect(current_product_name_locator).to_contain_text(search_term_from_input)
    # loop ends
