import asyncio
import json
import os
import re
import time
from datetime import datetime

import pandas as pd
from playwright.async_api import async_playwright


# ======================
# CONFIG
# ======================

INPUT_CSV = "low_frequency_classes.csv"
OUTPUT_DIR = "augmented_output"

CHATGPT_URL = "https://chat.openai.com/"

BATCH_SIZE = 2
AUG_PER_SAMPLE = 10

RELOAD_EVERY = 5

POST_GENERATION_DELAY = 2
WAIT_ICON = 'svg use[href*="#bbf3a9"]'

INPUT_SELECTORS = [
    "div[contenteditable='true']",
    "textarea",
    "div[role='textbox']",
]

REPLY_SELECTORS = [
    "div.markdown",
    "div.prose",
    "article",
]

PROGRESS_FILE = "augmentation_progress.json"


# ======================
# PROGRESS TRACKING
# ======================

def load_progress():

    if not os.path.exists(PROGRESS_FILE):
        return set()

    with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    return set(data.get("done_indexes", []))


def save_progress(done_indexes):

    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"done_indexes": list(done_indexes)},
            f,
            ensure_ascii=False,
            indent=2
        )


# ======================
# CHATGPT HELPERS
# ======================

async def find_input_box(page):

    for sel in INPUT_SELECTORS:
        try:
            await page.wait_for_selector(sel, timeout=5000)
            box = page.locator(sel).first

            if await box.is_visible():
                return box
        except:
            pass

    raise RuntimeError("ChatGPT input box not found")


async def wait_for_generation(page, timeout=120):

    start = time.time()

    while True:

        generating = await page.locator(WAIT_ICON).count() > 0

        if not generating:
            await asyncio.sleep(POST_GENERATION_DELAY)
            return

        if time.time() - start > timeout:
            raise TimeoutError("Generation timeout")

        await asyncio.sleep(0.5)


async def get_last_reply(page):

    for sel in REPLY_SELECTORS:

        nodes = page.locator(sel)
        count = await nodes.count()

        if count > 0:
            last = nodes.nth(count - 1)
            text = await last.inner_text()

            if text.strip():
                return text.strip()

    raise RuntimeError("Reply not captured")



# ======================
# JSON EXTRACTION
# ======================

def extract_json(text):

    text = re.sub(r"```json", "", text)
    text = re.sub(r"```", "", text)

    try:
        return json.loads(text)
    except:
        pass

    match = re.search(r"\{[\s\S]*\}", text)

    if match:
        return json.loads(match.group())

    raise ValueError("JSON extraction failed")


# ======================
# PROMPT
# ======================

def build_augmentation_prompt(texts):

    json_input = json.dumps(texts, ensure_ascii=False, indent=2)

    return f"""
Bạn là chuyên gia viết lại câu tiếng Việt cho dữ liệu review quán ăn.

Nhiệm vụ:
Với mỗi câu trong Input, hãy viết lại thành {AUG_PER_SAMPLE} câu khác nhau nhưng GIỮ NGUYÊN ý nghĩa.

Quy tắc:
- Không thay đổi cảm xúc của câu gốc
- Không thêm thông tin mới
- Không thay đổi bối cảnh review quán ăn
- Viết tự nhiên như người Việt
- Có thể thay đổi cấu trúc câu, từ đồng nghĩa, cách diễn đạt
- Mỗi câu rewrite phải khác nhau rõ ràng

Input:
{json_input}

Yêu cầu output:
- Chỉ trả về JSON
- Không thêm giải thích
- Không thêm markdown
- Không thêm text ngoài JSON

JSON format:

{{
  "results": [
    ["rewrite1","rewrite2","rewrite3","rewrite4","rewrite5","rewrite6","rewrite7","rewrite8","rewrite9","rewrite10"]
  ]
}}

Lưu ý:
- Mỗi câu input phải có đúng {AUG_PER_SAMPLE} câu rewrite.
"""


# ======================
# GENERATE AUGMENTATION
# ======================

async def generate_batch(page, texts):

    input_box = await find_input_box(page)

    prompt = build_augmentation_prompt(texts)

    await input_box.click()

    try:
        await input_box.fill(prompt)
    except:
        await input_box.type(prompt, delay=5)

    await page.keyboard.press("Enter")

    await wait_for_generation(page)

    reply = await get_last_reply(page)

    data = extract_json(reply)

    if "results" not in data:
        raise RuntimeError("Invalid JSON returned")

    return data["results"]


# ======================
# SAVE RESULTS
# ======================

def append_to_csv(original_rows, aug_results, output_file):

    rows = []

    for row, aug_list in zip(original_rows, aug_results):

        for aug in aug_list:

            rows.append({
                "source_index": row["index"],
                "original": row["text"],
                "augmented": aug,
                "food": row.get("food"),
                "service": row.get("service"),
                "place": row.get("place"),
                "cost": row.get("cost"),
            })

    df = pd.DataFrame(rows)

    file_exists = os.path.isfile(output_file)

    df.to_csv(
        output_file,
        mode="a",
        header=not file_exists,
        index=False
    )


# ======================
# MAIN PIPELINE
# ======================

async def run():

    df = pd.read_csv(INPUT_CSV)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_file = os.path.join(
        OUTPUT_DIR,
        f"reviews_augmented_{timestamp}.csv"
    )

    done_indexes = load_progress()

    async with async_playwright() as p:

        browser = await p.chromium.launch_persistent_context(
            user_data_dir="chrome_profile",
            headless=False
        )

        page = await browser.new_page()

        await page.goto(CHATGPT_URL)

        print("Waiting for ChatGPT page...")

        await asyncio.sleep(10)

        total = len(df)

        batch_count = 0

        for start in range(0, total, BATCH_SIZE):

            batch_df = df.iloc[start:start+BATCH_SIZE]

            batch_indexes = batch_df.index.tolist()

            # skip if already processed
            if all(i in done_indexes for i in batch_indexes):
                continue

            texts = batch_df["text"].astype(str).tolist()

            rows = batch_df.reset_index().to_dict("records")

            print(f"Processing batch {start} → {start+len(texts)}")

            try:

                aug = await generate_batch(page, texts)

                append_to_csv(rows, aug, output_file)

                print("Saved batch")

                for i in batch_indexes:
                    done_indexes.add(i)

                save_progress(done_indexes)

                batch_count += 1

                if batch_count % RELOAD_EVERY == 0:
                    await page.goto(CHATGPT_URL)

            except Exception as e:

                print("Batch failed:", e)

                await page.goto(CHATGPT_URL)

                continue

        await browser.close()

    print("Finished")
    print("Output:", output_file)


# ======================
# RUN
# ======================

if __name__ == "__main__":
    asyncio.run(run())