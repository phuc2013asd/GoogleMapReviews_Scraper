import pandas as pd
import random
import re

# ======================
# CONFIG
# ======================

INPUT_FILE = "reviews_labeled.csv"
OUTPUT_FILE = "reviews_augmented.csv"

LABEL_COLS = ["food", "service", "place", "cost"]

TARGET_PER_CLASS = 120
AUG_PROB = 0.35


# ======================
# SYNONYM DICTIONARY
# ======================

SYNONYMS = {

    "ngon": ["rất ngon", "khá ngon", "ngon lắm", "ngon tuyệt"],
    "giá": ["mức giá", "giá tiền", "giá cả"],
    "nhân viên": ["staff", "bạn phục vụ", "các bạn phục vụ"],
    "không gian": ["quán", "không gian quán"],
    "phục vụ": ["dịch vụ", "cách phục vụ"],
    "đông": ["khá đông", "đông khách"],
    "chậm": ["hơi chậm", "khá chậm"],
    "nhanh": ["rất nhanh", "khá nhanh"],
}


# ======================
# TEXT PARAPHRASE
# ======================

def synonym_replace(text):

    words = text.split()

    new_words = []

    for w in words:

        key = w.lower()

        if key in SYNONYMS and random.random() < AUG_PROB:

            new_words.append(random.choice(SYNONYMS[key]))

        else:
            new_words.append(w)

    return " ".join(new_words)


def random_word_drop(text):

    words = text.split()

    if len(words) < 6:
        return text

    new_words = []

    for w in words:

        if random.random() < 0.08:
            continue

        new_words.append(w)

    return " ".join(new_words)


def random_swap(text):

    words = text.split()

    if len(words) < 6:
        return text

    i = random.randint(0, len(words)-2)

    words[i], words[i+1] = words[i+1], words[i]

    return " ".join(words)


def paraphrase_text(text):

    text = synonym_replace(text)

    if random.random() < 0.4:
        text = random_word_drop(text)

    if random.random() < 0.3:
        text = random_swap(text)

    text = re.sub(r"\s+", " ", text).strip()

    return text


# ======================
# AUGMENTATION
# ======================

def augment_group(group, needed):

    rows = []

    for i in range(needed):

        sample = group.sample(1).iloc[0]

        new_row = sample.copy()

        new_row["text"] = paraphrase_text(sample["text"])

        rows.append(new_row)

    return pd.DataFrame(rows)


# ======================
# MAIN AUGMENTATION
# ======================

def augment_dataset(df):

    groups = df.groupby(LABEL_COLS)

    augmented_data = []

    print("\nLabel distribution:")

    for label, group in groups:

        count = len(group)

        print(label, ":", count)

        if count >= TARGET_PER_CLASS:
            continue

        needed = TARGET_PER_CLASS - count

        print("augment:", needed)

        aug = augment_group(group, needed)

        augmented_data.append(aug)

    if len(augmented_data) > 0:

        aug_df = pd.concat(augmented_data)

        df = pd.concat([df, aug_df], ignore_index=True)

    return df


# ======================
# WORD COUNT UPDATE
# ======================

def update_word_count(df):

    df["word_count"] = df["text"].apply(lambda x: len(str(x).split()))

    return df


# ======================
# MAIN
# ======================

def main():

    df = pd.read_csv(INPUT_FILE)

    print("Original dataset:", len(df))

    df = augment_dataset(df)

    df = update_word_count(df)

    print("Augmented dataset:", len(df))

    df.to_csv(OUTPUT_FILE, index=False)

    print("Saved:", OUTPUT_FILE)


# ======================
# RUN
# ======================

if __name__ == "__main__":

    main()