import asyncio
import os
from playwright.async_api import async_playwright
from typing import List


PROFILE_DIR = "chrome_profile"
TARGET_PLACES = 100


async def get_urls_from_page(url: str) -> List[str]:
    """
    Extract all URLs from a given webpage using async_playwright.
    
    Args:
        url: The webpage URL to extract links from
        
    Returns:
        List of absolute URLs found on the page
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            locale="vi-VN",
            viewport={"width": 1280, "height": 800},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--lang=vi-VN"
            ]
        )
        page = await browser.new_page()
        
        try:
            # Navigate to the URL
            await page.goto(url, wait_until="networkidle")
            
            # Get all href attributes from links
            links = await page.evaluate("""
                () => {
                    return Array.from(document.querySelectorAll('a[href]'))
                        .map(a => a.href)
                        .filter(href => href && href.trim());
                }
            """)
            
            return links
            
        finally:
            await browser.close()


async def get_urls_from_urls_file(filename: str = "../urls.txt") -> List[str]:
    """
    Read URLs from a file and extract all links from each page.
    
    Args:
        filename: Path to file containing URLs (one per line)
        
    Returns:
        List of all URLs found across all pages
    """
    all_urls = []
    
    try:
        with open(filename, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"File {filename} not found")
        return all_urls
    
    print(f"Found {len(urls)} URLs to process")
    
    for i, url in enumerate(urls, 1):
        try:
            print(f"[{i}/{len(urls)}] Processing: {url}")
            page_urls = await get_urls_from_page(url)
            all_urls.extend(page_urls)
            print(f"  Found {len(page_urls)} links")
        except Exception as e:
            print(f"  Error processing {url}: {e}")
    
    return all_urls


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
            viewport={"width": 1280, "height": 800},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--lang=vi-VN"
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
            scroll_box = page.locator("div.m6QErb.DxyBCb.kA9KIf.dS8AEf.XiKgde.ecceSd.QjC7t")
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
                if current_count >= TARGET_PLACES:
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
        "quán ăn gần đây",
    ]
    
    urls = asyncio.run(search_and_save_urls(
        queries=queries,
        output_file="urls.txt"  # Save directly to urls.txt for scraper
    ))
    print(f"\n✨ Total Google Maps URLs ready for scraper: {len(urls)}")
