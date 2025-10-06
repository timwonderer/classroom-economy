import pyotp
from playwright.sync_api import sync_playwright, expect

def run_verification(playwright):
    # --- Test Setup ---
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    base_url = "http://127.0.0.1:8000"
    admin_username = "testadmin"
    admin_totp_secret = "JBSWY3DPEHPK3PXP"

    try:
        # --- 1. Admin Login ---
        print("Navigating to admin login page...")
        page.goto(f"{base_url}/admin/login")

        # Fill in credentials
        page.get_by_label("Username").fill(admin_username)
        totp = pyotp.TOTP(admin_totp_secret)
        page.get_by_label("6-digit Authenticator Code").fill(totp.now())

        # Click login and wait for the navigation to the dashboard to complete
        page.get_by_role("button", name="Log In").click()
        page.wait_for_url(f"{base_url}/admin", timeout=15000)
        print("Login submitted and redirected to dashboard.")

        # Now that navigation is complete, verify the heading is visible
        expect(page.get_by_role("heading", name="Dashboard", level=2)).to_be_visible()
        print("Login successful. On admin dashboard.")

        # --- 2. Verify Store Management Page ---
        print("Navigating to store management page...")
        # Use get_by_role for robust selection
        page.get_by_role("link", name="🏪 Store").click()

        # Verify navigation to the correct page
        expect(page.get_by_role("heading", name="Store Management", level=2)).to_be_visible()
        print("On store management page.")

        # Take screenshot of the main store page
        screenshot_path_main = "jules-scratch/verification/admin_store_page.png"
        page.screenshot(path=screenshot_path_main)
        print(f"Screenshot of admin store page saved to: {screenshot_path_main}")

        # --- 3. Verify Edit Item Page ---
        print("Navigating to edit item page...")
        # Find the 'Edit' button for our specific test item
        # We can locate the table row containing "Test Item" and then find the link within it
        row = page.get_by_role("row", name="Test Item")
        row.get_by_role("link", name="Edit").click()

        # Verify navigation to the edit page
        expect(page.get_by_role("heading", name="Edit: Test Item")).to_be_visible()
        print("On edit item page.")

        # Take screenshot of the edit page
        screenshot_path_edit = "jules-scratch/verification/admin_edit_item_page.png"
        page.screenshot(path=screenshot_path_edit)
        print(f"Screenshot of edit item page saved to: {screenshot_path_edit}")

    except Exception as e:
        print(f"An error occurred during verification: {e}")
        # Save a screenshot on error for debugging
        page.screenshot(path="jules-scratch/verification/error_screenshot.png")
    finally:
        # --- Teardown ---
        context.close()
        browser.close()
        print("Verification script finished.")

with sync_playwright() as playwright:
    run_verification(playwright)