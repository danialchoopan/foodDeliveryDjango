from playwright.sync_api import sync_playwright, expect
import os
import time
import subprocess

def verify_address_features():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Login as customer
        page.goto("http://localhost:8000/login/")
        page.fill('input[name="username"]', 'customer1')
        page.fill('input[name="password"]', 'customer123')
        page.click('button[type="submit"]')

        # Check dashboard for addresses
        page.goto("http://localhost:8000/dashboard/customer/")
        expect(page.get_by_text("📍 مدیریت آدرس‌ها")).to_be_visible()

        # Add a new address with a unique title to avoid strict mode violations
        unique_title = f"آدرس تست {int(time.time())}"
        page.click("summary:has-text('➕ افزودن آدرس جدید')")
        page.fill('input[name="title"]', unique_title)
        page.select_option('select[name="city"]', 'اصفهان')
        page.fill('textarea[name="address_text"]', 'اصفهان، خیابان تستی، پلاک ۴')
        page.click('button:has-text("ذخیره آدرس")')

        expect(page.get_by_text("آدرس با موفقیت اضافه شد.")).to_be_visible()
        expect(page.get_by_text(unique_title).first).to_be_visible()

        # Activate the new address
        # We search for the specific card containing our unique title
        card = page.locator(f"div.card:has-text('{unique_title}')")
        card.locator("a:has-text('فعال‌سازی')").click()

        expect(page.get_by_text(f"آدرس فعال به {unique_title} تغییر یافت.")).to_be_visible()

        # Check home page filtering
        page.goto("http://localhost:8000/")
        expect(page.get_by_text(f"ارسال به: {unique_title} (اصفهان)")).to_be_visible()

        # Since we set Isfahan and coordinates are 35.6, 51.3 (from add_address form hidden fields)
        # and "کباب دانیال" in Isfahan also has 35.7, 51.3 in seed data.
        # The 0.1 range should match.
        expect(page.get_by_text("کباب دانیال")).to_be_visible()

        # Take a screenshot
        page.screenshot(path="address_verification_final.png")

        browser.close()

if __name__ == "__main__":
    # Ensure no other server is running
    subprocess.run("kill $(lsof -t -i :8000) 2>/dev/null || true", shell=True)
    # Start server
    server = subprocess.Popen(["python", "manage.py", "runserver", "0.0.0.0:8000"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(5)
    try:
        verify_address_features()
        print("Verification successful!")
    finally:
        server.terminate()
