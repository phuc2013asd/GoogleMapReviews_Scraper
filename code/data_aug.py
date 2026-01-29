import asyncio
import glob
import json
import os
import time
from datetime import datetime

import pandas as pd
from playwright.async_api import async_playwright


DEFAULT_OUTPUT_DIR = "output"
WAIT_ICON = 'svg use[href*="#bbf3a9"]'  # icon đang generate


# ------------------------
# CSV helper
# ------------------------
def find_latest_csv(input_path: str = None):
    if input_path and os.path.exists(input_path):
        return input_path

    files = glob.glob(
        os.path.join(
            os.path.dirname(__file__),
            DEFAULT_OUTPUT_DIR,
            "google_maps_reviews_*.csv",
        )
    )
    if not files:
        raise FileNotFoundError("No matching CSV files in output directory")

    return max(files, key=os.path.getmtime)


# ------------------------
# ChatGPT helpers
# ------------------------
async def get_last_reply_text(page):
    selectors = [
        "p[data-start]",
        "div.markdown p",
        "div[class*='prose'] p",
        "article p",
    ]

    for sel in selectors:
        try:
            elems = page.locator(sel)
            if await elems.count() > 0:
                text = await elems.last.text_content()
                if text and text.strip():
                    return text.strip()
        except:
            pass

    return ""


async def wait_for_chatgpt_done(page, timeout=120_000):
    """
    CHỈ CHECK 1 ĐIỀU KIỆN:
    - WAIT_ICON còn -> đang generate
    - WAIT_ICON mất -> DONE
    """
    start = time.time()

    while True:
        waiting = await page.locator(WAIT_ICON).count() > 0

        if not waiting:
            return

        if (time.time() - start) * 1000 > timeout:
            raise TimeoutError("Timeout waiting for ChatGPT generation")

        await asyncio.sleep(0.25)


# ------------------------
# Core logic
# ------------------------
async def generate_variants(
    page,
    text: str,
    n: int = 3,
    retries: int = 2,
):
    prompt = (
        "Bạn là một trợ lý tạo dữ liệu. "
        f"Hãy tạo {n} bản paraphrase ngắn, tự nhiên, khác nhau "
        "bằng tiếng Việt của đoạn review sau, "
        "GIỮ NGUYÊN cảm xúc và ý chính, KHÔNG THÊM NỘI DUNG MỚI.\n\n"
        "QUAN TRỌNG:\n"
        "- Chỉ trả về DUY NHẤT JSON array\n"
        "- Format chính xác:\n"
        "[\"paraphrase 1\", \"paraphrase 2\", \"paraphrase 3\"]\n\n"
        "REVIEW:\n"
        + text
    )

    # tìm input box
    input_box = None
    for sel in ["div[contenteditable='true']", "textarea", "div[role='textbox']"]:
        try:
            await page.wait_for_selector(sel, timeout=5_000)
            loc = page.locator(sel).first
            if await loc.is_visible():
                input_box = loc
                break
        except:
            continue

    if not input_box:
        raise RuntimeError("ChatGPT input box not found")

    for attempt in range(retries + 1):
        await input_box.click()
        await asyncio.sleep(0.2)

        try:
            await input_box.fill(prompt)
        except:
            await input_box.type(prompt, delay=4)

        await asyncio.sleep(0.2)
        await input_box.press("Enter")

        # chờ ChatGPT xong (WAIT icon only)
        await wait_for_chatgpt_done(page)

        reply = await get_last_reply_text(page)
        if not reply:
            continue

        try:
            parsed = json.loads(reply)
            if isinstance(parsed, list):
                result = [s.strip() for s in parsed if isinstance(s, str)]
                if len(result) == n:
                    return result
        except:
            pass

        # retry – ép format mạnh hơn
        prompt = (
            f"CHỈ TRẢ JSON ARRAY, KHÔNG GIẢI THÍCH.\n"
            f"Paraphrase {n} câu sau:\n{text}"
        )
        await asyncio.sleep(1)

    # fallback
    return [text] * n


# ------------------------
# Pipeline
# ------------------------
async def run(input_csv=None, variants_per_row=3, headless=False):
    csv_path = find_latest_csv(input_csv)
    print(f"Reading input CSV: {csv_path}")

    df = pd.read_csv(csv_path)

    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir="chrome_profile",
            headless=headless,
            locale="vi-VN",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ],
        )

        page = await browser.new_page()
        await page.goto("https://chat.openai.com/chat", timeout=30_000)

        outputs = []

        for idx, row in df.iterrows():
            original = str(row.get("text", "")).strip()
            if not original:
                continue

            try:
                variants = await generate_variants(
                    page,
                    original,
                    n=variants_per_row,
                )
            except Exception as e:
                print(f"[WARN] Row {idx} failed: {e}")
                continue

            for v in variants:
                out_row = row.to_dict()
                out_row["text"] = v
                outputs.append(out_row)

            # chống rate-limit
            await asyncio.sleep(1.2)

        await browser.close()

    if not outputs:
        print("No augmented outputs produced.")
        return

    out_df = pd.DataFrame(outputs)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(
        os.path.dirname(__file__),
        DEFAULT_OUTPUT_DIR,
        f"google_maps_reviews_augmented_{ts}.csv",
    )
    out_df.to_csv(out_path, index=False)
    print(f"Saved augmented CSV to: {out_path}")


# ------------------------
# CLI
# ------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Augment Google Maps reviews via ChatGPT (WAIT icon only)"
    )
    parser.add_argument("--input", "-i", help="Input CSV path (optional)")
    parser.add_argument("--n", "-n", type=int, default=5, help="Variants per review")
    parser.add_argument("--headless", action="store_true", help="Run browser headless")
    args = parser.parse_args()

    asyncio.run(
        run(
            input_csv=args.input,
            variants_per_row=args.n,
            headless=args.headless,
        )
    )
