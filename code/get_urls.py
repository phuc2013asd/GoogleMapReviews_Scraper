import asyncio
import asyncio
import os
from playwright.async_api import async_playwright
from typing import List

PROFILE_DIR = "chrome_profile"
TARGET_PLACES = 0


async def search_google_maps(page, query: str, location: str = "Việt Nam"):

    print(f"\n🔍 Searching: {query}")

    search_url = (
        f"https://www.google.com/maps/search/"
        f"{query.replace(' ', '+')}+{location.replace(' ', '+')}"
        f"?hl=vi"
    )

    await page.goto(search_url, wait_until="networkidle")

    await page.wait_for_timeout(3000)

    scroll_box = page.locator('div[role="feed"]')

    prev_count = 0

    while True:

        place_urls = await page.evaluate("""
            () => {
                const links = Array.from(
                    document.querySelectorAll('a[href*="/maps/place/"]')
                );

                return [...new Set(
                    links.map(a => a.href.split("?")[0])
                )];
            }
        """)

        current_count = len(place_urls)

        print(f"📍 {current_count} places")

        if current_count == prev_count:
            break

        if TARGET_PLACES > 0 and current_count >= TARGET_PLACES:
            break

        prev_count = current_count

        await scroll_box.evaluate(
            "(el) => el.scrollTo(0, el.scrollHeight)"
        )

        await page.wait_for_timeout(1500)

    return place_urls


async def search_and_save_urls(
    queries: List[str],
    output_file="urls.txt"
):

    existing_urls = set()

    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            existing_urls = {
                line.strip()
                for line in f
                if line.strip()
            }

    print(f"📂 Existing URLs: {len(existing_urls)}")

    async with async_playwright() as p:

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

        new_urls = set()

        for i, query in enumerate(queries, 1):

            try:

                print(f"\n[{i}/{len(queries)}]")

                urls = await search_google_maps(page, query)

                for url in urls:

                    clean_url = url.split("?")[0]

                    if clean_url not in existing_urls:
                        new_urls.add(clean_url)

            except Exception as e:
                print(f"❌ {e}")

        await browser.close()

    print(f"\n🆕 New URLs: {len(new_urls)}")

    if new_urls:

        with open(output_file, "a", encoding="utf-8") as f:

            for url in sorted(new_urls):
                f.write(url + "\n")

    print(f"✅ Saved")

    return list(new_urls)


if __name__ == "__main__":
    # Search Google Maps for restaurants nearby and save URLs
    queries = ["quán ăn", "nhà hàng", "ăn uống", "đồ ăn", "quán ăn ngon", "địa điểm ăn uống", "cơm", "cơm tấm", "cơm gà", "cơm niêu", "cơm văn phòng", "quán cơm", "phở", "bún bò", "bún riêu", "bún đậu", "hủ tiếu", "mì quảng", "bánh canh", "gà rán", "pizza", "hamburger", "đồ ăn nhanh", "lẩu", "nướng", "buffet", "bbq", "quán nướng", "hải sản", "ốc", "quán ốc", "ăn vặt", "trà sữa", "chè", "bánh tráng", "xiên que", "cafe", "quán cafe", "cà phê", "coffee", "bánh mì", "bánh xèo", "nem nướng", "gỏi cuốn", "sushi", "ramen", "tokbokki", "hotpot", "korean bbq", "quán ăn đêm", "ăn khuya", "quán nhậu"]
    
    urls = asyncio.run(search_and_save_urls(
        queries=queries,
        output_file="urls.txt"
    ))
    print(f"\n✨ Total Google Maps URLs ready for scraper: {len(urls)}")
