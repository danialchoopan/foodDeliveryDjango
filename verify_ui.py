import asyncio
from playwright.async_api import async_playwright
import os
import subprocess
import time

async def verify_danialfood():
    # Start the server
    server = subprocess.Popen(["python", "manage.py", "runserver", "8001"])
    time.sleep(5) # Wait for server to start

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await context.new_page()

        try:
            # 1. Home Page
            print("Visiting Home Page...")
            await page.goto("http://127.0.0.1:8001/")
            await page.screenshot(path="danialfood_home.png")
            print("Home page screenshot saved.")

            # 2. Click a Restaurant (using res-card)
            print("Clicking a restaurant...")
            await page.click("a.res-card")
            await page.wait_for_load_state("networkidle")
            await page.screenshot(path="danialfood_restaurant_detail.png")
            print("Restaurant detail screenshot saved.")

            # 3. Login Page
            print("Visiting Login Page...")
            await page.goto("http://127.0.0.1:8001/login/")
            await page.screenshot(path="danialfood_login.png")
            print("Login page screenshot saved.")

            # 4. Dashboard (Admin) - need to login first
            # Since I seeded data, I can try to login
            print("Logging in as admin...")
            await page.fill('input[name="username"]', 'admin')
            await page.fill('input[name="password"]', 'admin123')
            await page.click('button[type="submit"]')
            await page.wait_for_load_state("networkidle")
            await page.screenshot(path="danialfood_admin_dashboard.png")
            print("Admin dashboard screenshot saved.")

        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            await browser.close()
            server.terminate()

if __name__ == "__main__":
    asyncio.run(verify_danialfood())
