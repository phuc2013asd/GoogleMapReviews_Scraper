import asyncio
import csv
import os
from datetime import datetime
from matplotlib import lines
from playwright.async_api import async_playwright

# =========================
# CONFIG
# =========================
 
URLS = open("urls.txt", encoding="utf-8").read().splitlines()
N = int(URLS[0])
URLS = URLS[1:]
UNSCRAPED_URLS = URLS[N:]
PROFILE_DIR = "chrome_profile"
OUTPUT_DIR = "output"

MAX_REVIEWS = 0        # 0 = lấy hết
SCROLL_DELAY = 1000    # ms

os.makedirs(OUTPUT_DIR, exist_ok=True)
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_FILE = os.path.join(
    OUTPUT_DIR, f"google_maps_reviews_{TIMESTAMP}.csv"
)

FIELDS = ["place_name", "user", "rating", "time", "text"]


def force_vietnamese(url: str) -> str:
    if "hl=" in url:
        return url
    return url + ("&hl=vi" if "?" in url else "?hl=vi")


async def run(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            locale="vi-VN",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--lang=vi-VN", "--start-maximized"
            ]
        )

        page = await browser.new_page()

        # =========================
        # FORCE VI LANGUAGE
        # =========================
        url = force_vietnamese(url)
        await page.goto(url, timeout=60000)

        # =========================
        # PLACE NAME
        # =========================
        await page.wait_for_selector("h1.DUwDvf", timeout=60000)
        place_name = await page.locator("h1.DUwDvf").inner_text()

        # =========================
        # OPEN REVIEW PANEL
        # =========================
        review_btn = page.locator(
            "button:has-text('Đánh giá'), button:has-text('Reviews')"
        ).first
        await review_btn.click()
        await page.wait_for_timeout(3000)

        # =========================
        # SCROLL REVIEWS
        # =========================
        scroll_box = page.locator("div.m6QErb.DxyBCb.kA9KIf.dS8AEf")
        prev_count = 0
    
        while True:
            review_blocks = page.locator("div.jftiEf")
            current_count = await review_blocks.count()

            if current_count == prev_count:
                print(f"🛑 {place_name}: hết review")
                break

            if MAX_REVIEWS > 0 and current_count >= MAX_REVIEWS:
                print(f"✅ {place_name}: đủ {MAX_REVIEWS} review")
                break

            prev_count = current_count
            await scroll_box.evaluate(
                "(el) => el.scrollTo(0, el.scrollHeight)"
            )   
            await page.wait_for_timeout(SCROLL_DELAY)
            
        # =========================
        # EXPAND ALL "XEM THÊM / MORE"
        # =========================
        print("🔄 Expanding all reviews...")

        while True:
            more_buttons = scroll_box.locator(
                "button[aria-expanded='false'][jsaction*='review.expandReview'], "
                "a.MtCSLb[role='button']:has-text('Xem thêm'), "
                "a.MtCSLb[role='button']:has-text('More')"
            )

            count = await more_buttons.count()
            if count == 0:
                print("✅ No more expand buttons")
                break

            print(f"🔘 Expanding {count} buttons")

            for _ in range(count):
                try:
                    btn = more_buttons.first
                    await btn.scroll_into_view_if_needed()
                    await page.wait_for_timeout(300)
                    await btn.click(timeout=1000)
                    await page.wait_for_timeout(300)
                except:
                    pass

        # =========================
        # READ REVIEWS
        # =========================
        review_blocks = page.locator("div.jftiEf")
        total = await review_blocks.count()
        limit = min(total, MAX_REVIEWS) if MAX_REVIEWS > 0 else total

        rows = []

        for i in range(limit):
            block = review_blocks.nth(i)

            user = await block.locator("div.d4r55").inner_text()
            rating = await block.locator("span.kvMYJc").get_attribute("aria-label")
            time = await block.locator("span.rsqaWe").inner_text()

            text = ""
            if await block.locator("span.wiI7pd").count() > 0:
                text = await block.locator("span.wiI7pd").inner_text()

            rows.append({
                "place_name": place_name,
                "user": user,
                "rating": rating,
                "time": time,
                "text": text,
            })

        # =========================
        # SAVE CSV
        # =========================
        with open(OUTPUT_FILE, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            if f.tell() == 0:
                writer.writeheader()
            writer.writerows(rows)

        print(f"✅ Saved {len(rows)} reviews | {place_name}")
        await browser.close()


async def main():
    count = 0
    for url in UNSCRAPED_URLS:
        if url.strip():
            await run(url)
            with open("urls.txt", "w", encoding="utf-8") as f:
                count = count + 1
                lines = [str(N+count)] + URLS
                f.write("\n".join(lines))
            
asyncio.run(main())
