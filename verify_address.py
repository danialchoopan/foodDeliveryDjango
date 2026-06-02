from playwright.sync_api import sync_playwright, expect
import os
import time

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

        # Add a new address
        page.click("summary:has-text('➕ افزودن آدرس جدید')")
        page.fill('input[name="title"]', 'تست آدرس جدید')
        page.select_option('select[name="city"]', 'اصفهان')
        page.fill('textarea[name="address_text"]', 'اصفهان، خیابان تستی، پلاک ۴')
        page.click('button:has-text("ذخیره آدرس")')

        expect(page.get_by_text("آدرس با موفقیت اضافه شد.")).to_be_visible()
        expect(page.get_by_text("تست آدرس جدید")).to_be_visible()

        # Check home page filtering
        page.goto("http://localhost:8000/")
        # By default it should show restaurants in the active address city (Tehran/Shiraz from seed)
        # We just added Isfahan, let's make it active
        page.goto("http://localhost:8000/dashboard/customer/")
        # Find the "فعال‌سازی" button for our new address
        page.click("div.card:has-text('تست آدرس جدید') a:has-text('فعال‌سازی')")

        page.goto("http://localhost:8000/")
        expect(page.get_by_text("ارسال به: تست آدرس جدید (اصفهان)")).to_be_visible()
        # Should only show Isfahan restaurants
        expect(page.get_by_text("کباب دانیال")).to_be_visible()

        # Take a screenshot
        page.screenshot(path="address_verification.png")

        browser.close()

if __name__ == "__main__":
    # Start server in background
    import subprocess
    server = subprocess.Popen(["python", "manage.py", "runserver", "8000"])
    time.sleep(5) # Wait for server to start
    try:
        verify_address_features()
        print("Verification successful!")
    finally:
        server.terminate()
