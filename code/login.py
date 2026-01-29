import asyncio
from playwright.async_api import async_playwright

URL = open("urls.txt").read().split("\n")[0]

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir="chrome_profile",
            headless=False,
            locale="vi-VN",
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"]
        )

        page = await browser.new_page()
        await page.goto(URL, timeout=60000)

        print("👉 Nếu Google yêu cầu đăng nhập, hãy đăng nhập thủ công")
        print("👉 Sau khi vào được Google Maps, đóng trình duyệt")

        await page.wait_for_timeout(60000)  # 1 phút cho bạn login

        await browser.close()

asyncio.run(run())
