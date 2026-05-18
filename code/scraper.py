import asyncio
import csv
import os
from datetime import datetime
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

MAX_REVIEWS = 0
SCROLL_DELAY = 1000

os.makedirs(OUTPUT_DIR, exist_ok=True)

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

OUTPUT_FILE = os.path.join(
    OUTPUT_DIR,
    f"google_maps_reviews_{TIMESTAMP}.csv"
)

FIELDS = ["place_name", "user", "rating", "time", "text"]


def force_vietnamese(url: str):
    if "hl=" in url:
        return url
    return url + ("&hl=vi" if "?" in url else "?hl=vi")


async def run(page, url):

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

    print(f"\n📍 {place_name}")

    # =========================
    # OPEN REVIEW PANEL
    # =========================
    review_btn = page.locator(
    "button[role='tab'][aria-label*='Bài đánh giá'], "
    "button[role='tab'][aria-label*='Reviews']"
    ).first

    if await review_btn.count() > 0:
        await review_btn.click()
        await page.wait_for_timeout(3000)
    else:
        print("⚠️ Không có nút đánh giá, bỏ qua")
        return

    # =========================
    # SORT BY LOWEST RATING
    # =========================

    # mở dropdown sort
    sort_btn = page.locator(
        "button[aria-label*='Phù hợp nhất'], "
        "button[aria-label*='Most relevant']"
    ).first

    await sort_btn.click()

    await page.wait_for_timeout(1500)

    # chọn "Xếp hạng thấp nhất"
    lowest_btn = page.locator(
        "div[role='menuitemradio']:has-text('Xếp hạng thấp nhất'), "
        "div[role='menuitemradio']:has-text('Lowest rating')"
    ).first

    await lowest_btn.click()

    await page.wait_for_timeout(2000)
    # =========================
    # SCROLL REVIEWS
    # DỪNG KHI GẶP REVIEW 5 SAO
    # HOẶC REVIEW RỖNG
    # =========================

    scroll_box = page.locator(
        "div.m6QErb.DxyBCb.kA9KIf.dS8AEf"
    ).first

    previous_count = 0
    same_count_times = 0
    max_same_count = 3

    stop_on_5_star = False
    stop_on_empty = False

    while True:

        review_blocks = page.locator("div.jftiEf")
        current_count = await review_blocks.count()

        print(f"📦 {current_count} reviews")

        # =========================
        # CHECK LAST LOADED REVIEWS
        # =========================

        start_idx = max(previous_count - 5, 0)

        for i in range(start_idx, current_count):

            block = review_blocks.nth(i)

            try:
                rating_text = await block.locator(
                    "span.kvMYJc"
                ).get_attribute("aria-label")

                # ví dụ:
                # "5 sao"
                # "5 stars"

                if rating_text and ("5" in rating_text):
                    print("🛑 Gặp review 5 sao -> dừng scroll")
                    stop_on_5_star = True
                    break

            except:
                pass

            # =========================
            # CHECK EMPTY REVIEW
            # =========================

            try:
                text = ""

                if await block.locator("span.wiI7pd").count() > 0:
                    text = await block.locator(
                        "span.wiI7pd"
                    ).inner_text()

                clean_text = text.strip()

                # review rỗng / quá ngắn
                if len(clean_text) < 5:
                    print("🛑 Gặp review rỗng -> dừng scroll")
                    stop_on_empty = True
                    break

            except:
                pass

        if stop_on_5_star:
            break

        if stop_on_empty:
            break

        # đủ số lượng cần
        if MAX_REVIEWS > 0 and current_count >= MAX_REVIEWS:
            print(f"✅ {place_name}: đủ {MAX_REVIEWS} review")
            break

        # không load thêm review mới
        if current_count == previous_count:
            same_count_times += 1
        else:
            same_count_times = 0

        # thử nhiều lần vẫn không tăng
        if same_count_times >= max_same_count:
            print(f"🛑 {place_name}: hết review")
            break

        previous_count = current_count

        # scroll xuống cuối
        await scroll_box.evaluate("""
            el => {
                el.scrollTop = el.scrollHeight;
            }
        """)

        await page.wait_for_timeout(SCROLL_DELAY)
        
    # =========================
    # CLICK ALL TRANSLATE BUTTONS
    # =========================

    print("🌐 Translating reviews...")

    while True:

        buttons = page.locator(
            "button:has-text('Xem bản dịch'), "
            "button:has-text('See translation')"
        )

        count = await buttons.count()

        if count == 0:
            break

        print(f"🔘 Remaining translate buttons: {count}")

        try:
            btn = buttons.first

            await btn.scroll_into_view_if_needed()

            await btn.click(timeout=2000, force=True)

            await page.wait_for_timeout(200)

        except Exception as e:
            print("⚠️ Translate error:", e)
            break
    # =========================
    # READ REVIEWS
    # =========================
    review_blocks = page.locator("div.jftiEf")

    total = await review_blocks.count()

    limit = min(total, MAX_REVIEWS) if MAX_REVIEWS > 0 else total

    rows = []

    for i in range(limit):

        block = review_blocks.nth(i)

        try:
            user = await block.locator("div.d4r55").inner_text()
        except:
            user = ""

        try:
            rating = await block.locator(
                "span.kvMYJc"
            ).get_attribute("aria-label")
        except:
            rating = ""

        try:
            time = await block.locator("span.rsqaWe").inner_text()
        except:
            time = ""

        text = ""

        try:
            if await block.locator("span.wiI7pd").count() > 0:
                text = await block.locator(
                    "span.wiI7pd"
                ).inner_text()
        except:
            pass

        clean_text = text.strip()

        # bỏ review rỗng / quá ngắn
        if len(clean_text) < 5:
            continue

        rows.append({
            "place_name": place_name,
            "user": user,
            "rating": rating,
            "time": time,
            "text": clean_text,
        })

    # =========================
    # SAVE CSV
    # =========================
    with open(
        OUTPUT_FILE,
        "a",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        writer = csv.DictWriter(f, fieldnames=FIELDS)

        if f.tell() == 0:
            writer.writeheader()

        writer.writerows(rows)

    print(f"✅ Saved {len(rows)} reviews")


async def main():

    async with async_playwright() as p:

        # =========================
        # OPEN CHROMIUM ONLY ONCE
        # =========================
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            locale="vi-VN",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--lang=vi-VN",
                "--start-maximized"
            ]
        )

        page = await browser.new_page()

        count = 0

        for url in UNSCRAPED_URLS:

            if not url.strip():
                continue

            try:
                await run(page, url)

                count += 1

                with open("urls.txt", "w", encoding="utf-8") as f:
                    lines = [str(N + count)] + URLS
                    f.write("\n".join(lines))

            except Exception as e:
                print(f"❌ ERROR: {url}")
                print(e)

        await browser.close()


asyncio.run(main())