import asyncio
from playwright.async_api import async_playwright

URLS = open("urls.txt").read().split("\n")
N = int(URLS[0])
URL = URLS[1]

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

        await page.wait_for_timeout(99999)  # 1 phút cho bạn login

        await browser.close()

asyncio.run(run())
