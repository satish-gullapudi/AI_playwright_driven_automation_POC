import os
import random
from playwright.sync_api import expect
from ai_core.ai_self_heal import try_with_healing, heal_locator
def run(page, model):
    try_with_healing(model, page, page.click, "a[href='/login']")
    try_with_healing(model, page, page.fill, "input[data-qa='login-email']", "satishpaktolus22@gmail.com")
    try_with_healing(model, page, page.fill, "input[data-qa='login-password']", "pass@123")
    try_with_healing(model, page, page.click, "button[data-qa='login-button']")
    page.wait_for_timeout(10000)
    expect(page.locator("a[href='/logout']")).to_be_visible()
