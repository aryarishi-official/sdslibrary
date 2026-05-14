import re

def normalize_text(text: str) -> str:
    if not text:
        return ""

    text = text.lower().strip()

    text = re.sub(r"[^a-z0-9\s]", " ", text)

    text = re.sub(r"\s+", " ", text)

    return text