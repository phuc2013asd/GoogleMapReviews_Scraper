from playwright.sync_api import sync_playwright
import time

URL = open("url.txt").read()

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,   # đổi True khi chạy ổn
        args=["--disable-blink-features=AutomationControlled"]
    )

    context = browser.new_context(
        locale="vi-VN",
        viewport={"width": 1280, "height": 800}
    )

    page = context.new_page()
    page.goto(URL, timeout=60000)
    page.wait_for_timeout(5000)

    def safe_text(selector):
        try:
            return page.locator(selector).first.inner_text()
        except:
            return None

    data = {}

    # =========================
    # READ DATA
    # =========================
    data["name"] = safe_text("h1.DUwDvf")

    data["rating"] = safe_text("span.F7nice span")
    data["review_count"] = safe_text("span.F7nice span:nth-child(2)")

    data["address"] = safe_text("button[data-item-id='address'] div.Io6YTe")
    data["phone"] = safe_text("button[data-item-id*='phone'] div.Io6YTe")
    data["website"] = safe_text("a[data-item-id='authority'] div.Io6YTe")

    # Opening hours (expanded)
    try:
        page.locator("button[jsaction*='pane.hours']").click()
        page.wait_for_timeout(2000)
        data["hours"] = page.locator("div[role='dialog']").inner_text()
    except:
        data["hours"] = None

    # =========================
    # OUTPUT
    # =========================
    print("\n===== GOOGLE MAPS DATA =====")
    for k, v in data.items():
        print(f"{k}: {v}")

    browser.close()
