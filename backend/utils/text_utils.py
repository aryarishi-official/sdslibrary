import re

def remove_footer_noise(text: str) -> str:
    lines = text.splitlines()
    cleaned = []

    for line in lines:
        line = line.strip()

        skip = False

        for pattern in FOOTER_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                skip = True
                break

        if not skip:
            cleaned.append(line)

    return "\n".join(cleaned)

def normalize_text(text: str) -> str:
    if not text:
        return ""

    text = text.lower().strip()

    text = re.sub(r"[^a-z0-9\s]", " ", text)

    text = re.sub(r"\s+", " ", text)

    return text

FOOTER_PATTERNS = [
    r"Date of issue/Date of revision\s*:.*?\d+/\d+",
    r"Date of previous issue\s*:.*",
    r"Version\s*:\s*[\d\.]+",
    r"\d+/\d+$",
    r"SAFETY DATA SHEET",
]


