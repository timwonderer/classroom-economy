import pytest
from playwright.sync_api import Page, expect
import sys
import os
from dotenv import load_dotenv

# Add project root to path and load .env
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
load_dotenv()

from app import app, db, Student, Admin, HallPassLog, TapEvent
from werkzeug.security import generate_password_hash
from hash_utils import get_random_salt, hash_username
import pyotp

def setup_test_data():
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    db.init_app(app)
    with app.app_context():
        db.drop_all()
        db.create_all()

        # Create student
        student_salt = get_random_salt()
        student = Student(
            first_name="John",
            last_initial="D",
            block="A",
            salt=student_salt,
            username_hash=hash_username("johndoe", student_salt),
            pin_hash=generate_password_hash("1234"),
            passphrase_hash=generate_password_hash("password123"),
            hall_passes=3,
            has_completed_setup=True
        )
        db.session.add(student)

        # Create admin
        admin = Admin(
            username="teacher",
            totp_secret=pyotp.random_base32()
        )
        db.session.add(admin)
        db.session.commit()
        return student, admin

def test_hall_pass_flow(page: Page):
    student, admin = setup_test_data()

    # --- Student Flow ---
    page.goto("http://127.0.0.1:8080/student/login")
    page.get_by_label("Username").fill("johndoe")
    page.get_by_label("PIN").fill("1234")
    page.get_by_role("button", name="Login").click()

    # Verify dashboard and hall pass balance
    expect(page.get_by_role("heading", name="Good morning, John D.!"))
    expect(page.locator("#hall-pass-balance")).to_have_text("3")
    page.screenshot(path="jules-scratch/verification/1_student_dashboard_initial.png")

    # Request a hall pass
    page.get_by_role("button", name="Tap Out for Block A").click()
    expect(page.get_by_role("heading", name="Request Hall Pass")).to_be_visible()
    page.get_by_label("Reason for leaving:").select_option("Restroom")
    page.get_by_label("Enter your PIN to confirm:").fill("1234")
    page.get_by_role("button", name="Request Pass").click()

    # Verify toast message
    expect(page.get_by_text("Hall pass request submitted!")).to_be_visible()
    page.screenshot(path="jules-scratch/verification/2_student_dashboard_after_request.png")

    # --- Admin Flow ---
    page.goto("http://127.0.0.1:8080/admin/login")
    page.get_by_label("Username").fill("teacher")
    totp = pyotp.TOTP(admin.totp_secret)
    page.get_by_label("TOTP Code").fill(totp.now())
    page.get_by_role("button", name="Log In").click()

    # Navigate to Hall Pass page and verify request
    page.get_by_role("link", name="Hall Pass").click()
    expect(page.get_by_role("heading", name="Hall Pass Management")).to_be_visible()
    expect(page.get_by_text("John D. - Restroom")).to_be_visible()
    page.screenshot(path="jules-scratch/verification/3_admin_hall_pass_pending.png")

    # Approve request
    page.get_by_role("button", name="Approve").click()
    expect(page.get_by_text("John D. - Restroom")).to_be_visible()
    expect(page.locator(".card-header", has_text="Approved Queue")).to_be_visible()
    page.screenshot(path="jules-scratch/verification/4_admin_hall_pass_approved.png")

    # Mark as left
    page.get_by_role("button", name="Left Class").click()
    expect(page.get_by_text("John D. - Restroom")).to_be_visible()
    expect(page.locator(".card-header", has_text="Out of Classroom")).to_be_visible()
    page.screenshot(path="jules-scratch/verification/5_admin_hall_pass_left.png")

    # Mark as returned
    page.get_by_role("button", name="Returned").click()
    expect(page.get_by_text("John D. - Restroom")).not_to_be_visible()
    page.screenshot(path="jules-scratch/verification/6_admin_hall_pass_returned.png")

    # Verify student detail page
    page.goto(f"http://127.0.0.1:8080/admin/students/{student.id}")
    expect(page.get_by_text("Current Hall Passes: 2")).to_be_visible()

    # Update hall passes
    page.get_by_label("Set New Balance:").fill("5")
    page.get_by_role("button", name="Update").click()
    expect(page.get_by_text("Current Hall Passes: 5")).to_be_visible()
    expect(page.get_by_text("Successfully updated John D.'s hall pass balance to 5.")).to_be_visible()
    page.screenshot(path="jules-scratch/verification/7_admin_student_detail.png")

if __name__ == '__main__':
    # This is a bit of a hack to run playwright script without pytest runner
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        test_hall_pass_flow(page)
        browser.close()