from playwright.sync_api import Page, expect, sync_playwright
import time

def verify_danialfood(page: Page):
    # 1. Home Page
    page.goto("http://localhost:8001")
    page.wait_for_load_state("networkidle")
    page.screenshot(path="danialfood_home.png")
    print("Home page screenshot saved.")

    # 2. Login Page
    page.goto("http://localhost:8001/login/")
    page.wait_for_load_state("networkidle")
    page.screenshot(path="danialfood_login.png")
    print("Login page screenshot saved.")

    # 3. Perform Login
    page.locator('input[name="username"]').fill("customer1")
    page.locator('input[name="password"]').fill("customer123")
    page.get_by_role("button", name="ورود").click()
    page.wait_for_load_state("networkidle")

    # 4. Customer Dashboard
    page.screenshot(path="danialfood_customer_dashboard.png")
    print("Customer dashboard screenshot saved.")

    # 5. Restaurant Detail (Check if it works now)
    # Find a restaurant link or go directly
    page.goto("http://localhost:8001/restaurant/4/") # From seed data
    page.wait_for_load_state("networkidle")
    page.screenshot(path="danialfood_restaurant_detail.png")
    print("Restaurant detail screenshot saved.")

    # 6. Admin Dashboard
    # Logout first or just login as admin
    page.goto("http://localhost:8001/logout/")
    page.goto("http://localhost:8001/login/")
    page.locator('input[name="username"]').fill("admin")
    page.locator('input[name="password"]').fill("admin123")
    page.get_by_role("button", name="ورود").click()
    page.goto("http://localhost:8001/dashboard/admin/")
    page.wait_for_load_state("networkidle")
    page.screenshot(path="danialfood_admin_dashboard.png")
    print("Admin dashboard screenshot saved.")

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            verify_danialfood(page)
        except Exception as e:
            print(f"Error: {e}")
            page.screenshot(path="danialfood_error.png")
        finally:
            browser.close()
