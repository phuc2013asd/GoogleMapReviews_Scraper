import asyncio
import os
from playwright.async_api import async_playwright
from typing import List


PROFILE_DIR = "chrome_profile"
TARGET_PLACES = 0  # 0 = lấy hết



async def search_google_maps(query: str, location: str = "Việt Nam") -> List[str]:
    """
    Search Google Maps for a query and extract place URLs by scrolling.
    
    Args:
        query: Search query (e.g., "quán ăn gần đây", "restaurants")
        location: Location to search in (default: Vietnam)
        
    Returns:
        List of Google Maps place URLs from search results
    """
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
        
        try:
            # Open Google Maps
            print(f"🔍 Searching Google Maps for: '{query}'")
            search_url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}+{location.replace(' ', '+')}"
            await page.goto(search_url, wait_until="networkidle", timeout=60000)
            
            # Wait for results to load
            await page.wait_for_timeout(3000)
            
            # Keep scrolling until reaching target or no new results appear
            scroll_box = page.locator('div[role="feed"]')
            prev_count = 0
            
            while True:
                # Extract current URLs
                place_urls = await page.evaluate("""
                    () => {
                        const links = Array.from(document.querySelectorAll('a[href*="/maps/place/"]'));
                        return links.map(a => a.href).filter((url, idx, arr) => arr.indexOf(url) === idx);
                    }
                """)
                
                current_count = len(place_urls)
                print(f"  Found {current_count} places so far...")
                
                # If no new places found, stop scrolling
                if current_count == prev_count:
                    print(f"  No new places found, stopping scroll")
                    break
                
                # Stop if reached target
                if TARGET_PLACES > 0 and current_count >= TARGET_PLACES:
                    print(f"  Reached target of {TARGET_PLACES} places")
                    break
                
                prev_count = current_count
                
                await scroll_box.evaluate(
                    "(el) => el.scrollTo(0, el.scrollHeight)"
                )
                await page.wait_for_timeout(1500)
            
            # Final extraction
            place_urls = await page.evaluate("""
                () => {
                    const links = Array.from(document.querySelectorAll('a[href*="/maps/place/"]'));
                    return links.map(a => a.href).filter((url, idx, arr) => arr.indexOf(url) === idx);
                }
            """)
            
            print(f"✅ Found {len(place_urls)} total places for '{query}'")
            return place_urls
            
        finally:
            await browser.close()


async def search_and_save_urls(queries: List[str], output_file: str = "../urls.txt") -> List[str]:
    """
    Search multiple queries on Google Maps and save URLs to file.
    
    Args:
        queries: List of search queries
        output_file: File to save extracted URLs
        
    Returns:
        List of all extracted URLs
    """
    all_urls = []
    
    for i, query in enumerate(queries, 1):
        try:
            print(f"\n[{i}/{len(queries)}] Processing query: {query}")
            urls = await search_google_maps(query)
            all_urls.extend(urls)
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    # Remove duplicates
    all_urls = list(set(all_urls))
    
    print(f"\n📍 Total unique URLs found: {len(all_urls)}")
    
    # Save to file
    with open(output_file, 'w', encoding='utf-8') as f:
        for url in all_urls:
            f.write(url + '\n')
    
    print(f"✅ Saved to {output_file}")
    return all_urls


if __name__ == "__main__":
    # Search Google Maps for restaurants nearby and save URLs
    queries = [
        "quán ăn",
    ]
    
    urls = asyncio.run(search_and_save_urls(
        queries=queries,
        output_file="urls.txt"
    ))
    print(f"\n✨ Total Google Maps URLs ready for scraper: {len(urls)}")
