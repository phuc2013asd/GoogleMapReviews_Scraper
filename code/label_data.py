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

INPUT_FILE = "output/preprocessed_filtered_reviews_sorted.csv"
OUTPUT_DIR = "output_labeled"

CHATGPT_URL = "https://chat.openai.com/chat"

START_AT_INDEX = 0

BATCH_SIZE = 20
POST_GENERATION_DELAY = 2
SLEEP_BETWEEN_BATCH = 2
REFRESH_AFTER_BATCH = 5

MAX_RETRY = 3

CHECKPOINT_FILE = os.path.join(OUTPUT_DIR, "checkpoint.txt")

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


# ======================
# CHECKPOINT
# ======================

def load_checkpoint():
    if not os.path.exists(CHECKPOINT_FILE):
        return START_AT_INDEX
    with open(CHECKPOINT_FILE, "r") as f:
        return int(f.read().strip())


def save_checkpoint(index):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(CHECKPOINT_FILE, "w") as f:
        f.write(str(index))


# ======================
# CSV HELPERS
# ======================

def load_existing_texts(path):
    if not os.path.exists(path):
        return set()

    df = pd.read_csv(path)
    if "text" not in df.columns:
        return set()

    return set(df["text"].astype(str))


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
            last_node = nodes.nth(count - 1)
            text = await last_node.inner_text()
            if text.strip():
                return text.strip()

    raise RuntimeError("No reply found")


# ======================
# JSON PARSER
# ======================

def extract_json(text):
    text = text.strip()
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

def build_prompt(texts, batch_size):
    json_input = json.dumps(texts, ensure_ascii=False, indent=2)

    return f"""
Bạn là chuyên gia Aspect-Based Sentiment Analysis (ABSA) cho review nhà hàng/quán ăn.

NHIỆM VỤ:
Gán sentiment cho 4 aspect:
- food: đồ ăn, thức uống, khẩu vị, topping, chất lượng món
- service: nhân viên, phục vụ, tốc độ, shipper, hỗ trợ
- place: không gian, vệ sinh, bàn ghế, môi trường
- price: giá, khuyến mãi, độ đáng tiền

LABEL:
- 0 = none → không nhắc aspect
- 1 = negative → chê
- 2 = positive → khen
- 3 = neutral → có nhắc nhưng mơ hồ / trung tính / cân bằng

QUY TẮC:
1. KHÔNG SUY DIỄN: không nhắc → 0
2. none (0) vs neutral (3):
   - 0: không đề cập
   - 3: có đề cập nhưng không rõ cảm xúc
3. CHỈ GÁN POS/NEG KHI CẢM XÚC RÕ
4. KHÔNG LAN TRUYỀN sentiment giữa aspects
5. CÂU CHUNG CHUNG → tất cả aspect = 0
6. MIXED sentiment → neutral (3)

INPUT:
- Batch gồm {BATCH_SIZE} review

OUTPUT:
- Chỉ trả về DUY NHẤT JSON:
results:
[
  {{"food": 0, "service": 0, "place": 0, "price": 0}},
  ...
]

RÀNG BUỘC BẮT BUỘC:
- results MUST có đúng {BATCH_SIZE} phần tử
- results[i] tương ứng input[i]
- KHÔNG được thiếu hoặc thừa bất kỳ object nào
- Nếu thiếu thông tin → aspect = 0 (không được bỏ qua)

KHÔNG giải thích
KHÔNG text ngoài JSON

DỮ LIỆU:
{json_input}
"""

# ======================
# GENERATION WITH RETRY
# ======================

async def generate_labels_batch(page, texts, batch_size):

    for attempt in range(MAX_RETRY):

        print(f"\nBatch attempt {attempt + 1}/{MAX_RETRY}")

        input_box = await find_input_box(page)
        prompt = build_prompt(texts, batch_size)

        await input_box.click()

        try:
            await input_box.fill(prompt)
        except:
            await input_box.type(prompt, delay=5)

        await input_box.press("Enter")

        await wait_for_generation(page)

        reply = await get_last_reply(page)
        print("RAW:", reply[:300])

        try:
            data = extract_json(reply)
        except Exception as e:
            print("JSON parse fail:", e)
            continue

        if "results" not in data:
            print("Missing results key")
            continue

        results = data["results"]

        if len(results) != len(texts):
            print(f"Mismatch: got {len(results)} expected {len(texts)}")
            continue

        return results

    raise RuntimeError("Batch failed after retries")


# ======================
# SAVE
# ======================

def save_batch(rows, labels, out_path, existing_texts):

    for row, lab in zip(rows, labels):

        new_row = row.to_dict()

        new_row["food"] = lab["food"]
        new_row["service"] = lab["service"]
        new_row["place"] = lab["place"]
        new_row["price"] = lab["price"]

        df_out = pd.DataFrame([new_row])

        df_out.to_csv(
            out_path,
            mode="a",
            header=not os.path.exists(out_path),
            index=False
        )

        existing_texts.add(new_row["text"])


# ======================
# MAIN PIPELINE
# ======================

async def run(input_csv=None, headless=False):

    csv_path = input_csv or INPUT_FILE
    df = pd.read_csv(csv_path)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(OUTPUT_DIR, f"labeled_{ts}.csv")

    existing_texts = load_existing_texts(out_path)

    start_index = load_checkpoint()
    print("Resume from index:", start_index)

    df = df.iloc[start_index:]

    global_index = start_index

    async with async_playwright() as p:

        browser = await p.chromium.launch_persistent_context(
            user_data_dir="chrome_profile",
            headless=headless,
            locale="vi-VN",
            args=["--disable-blink-features=AutomationControlled"],
        )

        page = await browser.new_page()
        await page.goto(CHATGPT_URL)

        batch_rows, batch_texts = [], []
        batch_counter = 0

        for _, row in df.iterrows():

            text = str(row.get("text", "")).strip()

            if not text:
                global_index += 1
                continue

            if text in existing_texts:
                global_index += 1
                continue

            batch_rows.append(row)
            batch_texts.append(text)

            if len(batch_rows) < BATCH_SIZE:
                global_index += 1
                continue

            print("\nProcessing batch...")

            labels = await generate_labels_batch(page, batch_texts, len(batch_texts))

            save_batch(batch_rows, labels, out_path, existing_texts)

            # ✅ SAVE CHECKPOINT
            save_checkpoint(global_index + len(batch_rows))

            batch_rows, batch_texts = [], []
            batch_counter += 1

            if batch_counter % REFRESH_AFTER_BATCH == 0:
                await page.goto(CHATGPT_URL)

            await asyncio.sleep(SLEEP_BETWEEN_BATCH)

            global_index += 1

        if batch_rows:
            labels = await generate_labels_batch(page, batch_texts, len(batch_texts))
            save_batch(batch_rows, labels, out_path, existing_texts)
            save_checkpoint(global_index + len(batch_rows))

        await browser.close()

    print("DONE")


# ======================
# CLI
# ======================

if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", "-i")
    parser.add_argument("--headless", action="store_true")

    args = parser.parse_args()

    asyncio.run(run(args.input, args.headless))