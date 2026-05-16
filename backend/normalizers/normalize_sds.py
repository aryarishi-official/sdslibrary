from typing import Dict, Any
import re
from utils.text_utils import normalize_text

def get_section(raw_sds, section_num):
    sections = raw_sds.get("sections", [])

    return next(
        (
            s for s in sections
            if s.get("section_number") == str(section_num)
        ),
        {}
    )

def find_subsection(section, possible_titles):
    subsections = section.get("subsections", [])

    for wanted in possible_titles:
        wanted = wanted.lower()

        for sub in subsections:
            title = sub.get("title", "").lower()

            if wanted in title:
                content = sub.get("content", "").strip()

                if content:
                    return content

    return ""

FIELD_MAP = {
    "product_name": [
        "ghs product identifier",
        "product name",
        "srm name",
        "product identifier",
        "trade name",
        "chemical name",
    ],

    "recommended_use": [
    "recommended use",
    "recommended uses",
    "product use",
    "product use",
    "identified uses",
    "intended use",
    "use of substance",
    "recommended use of the chemical",
    ],

    "supplier": [
        "supplier",
        "supplier's details",
        "company information",
        "manufacturer",
    ],

    "signal_word": [
        "signal word",
    ],

    "revision_date": [
    "date of revision",
    "revision date",
    "date of issue/date of revision",
    "date of issue",
    ],

    "hazard_statements": [
        "hazard statements",
        "hazard statement(s)",
    ],

    "cas_number": [
    "cas number",
    "cas no",
    "cas-no",
    "cas #",
    "cas number(s)",
    ],

    "physical_state": [
        "physical state",
        "product type",
        "appearance",
    ],

    "color": [
        "color",
    ],

    "odor": [
        "odor",
        "odour",
    ],

    "un_number": [
    "un-no",
    "un no",
    "un number",
    "un-number",
    "un#",
],

    "flash_point": [
        "flash point",
    ],

    "storage_conditions": [
        "conditions for safe storage",
        "storage",
    ],

    "chemical_formula": [
        "chemical formula",
        "molecular formula",
    ]
}

FIELD_SECTIONS = {
    "product_name": [1],
    "supplier": [1],
    "recommended_use": [1],
    "revision_date": [1, 16],

    "signal_word": [2],
    "hazard_statements": [2],
    
    "cas_number": [3],

    "physical_state": [9, 1],
    "color": [9],
    "odor": [9],
    "flash_point": [9],
    "storage_conditions": [7],

    "chemical_formula": [1, 9],
}

def resolve_field(raw_sds, field_name):
    section_numbers = FIELD_SECTIONS.get(field_name, [])
    synonyms = FIELD_MAP.get(field_name, [])

    for sec_num in section_numbers:

        section = get_section(raw_sds, sec_num)

        if not section:
            continue

        value = find_subsection(section, synonyms)

        if value:
            return value

    return ""

def resolve_product_name(raw_sds):

    # First try normal synonym lookup
    value = resolve_field(raw_sds, "product_name")

    # Reject garbage values
    bad_values = [
        "not applicable",
        "other means of identification",
    ]

    lower = value.lower()

    if any(bad in lower for bad in bad_values):

        sec1 = get_section(raw_sds, 1)

        for sub in sec1.get("subsections", []):

            content = sub.get("content", "")

            # NIST SRM format
            if "srm name:" in content.lower():
                parts = content.split(":", 1)

                if len(parts) > 1:
                    return parts[1].strip()

    return value

def extract_date(value: str) -> str:
    if not value:
        return ""

    import re

    match = re.search(
        r"\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b",
        value
    )

    if match:
        return match.group(0)

    return value

CAS_REGEX = re.compile(r"\b\d{2,7}-\d{2}-\d\b")


def resolve_cas_number(raw_sds):
    """
    Resolve CAS number robustly from subsection titles/content.
    """

    sections = raw_sds.get("sections", [])

    for sec in sections:

        # CAS mostly exists in Section 1 or 3
        if str(sec.get("section_number")) not in ["1", "3"]:
            continue

        for sub in sec.get("subsections", []):

            title = normalize_text(sub.get("title", ""))
            content = sub.get("content", "")

            combined = f"{title}\n{content}"

            match = CAS_REGEX.search(combined)

            if match:
                return match.group(0)

    return ""

def normalize_sds(raw_sds):

    normalized = {
        "product_name": resolve_product_name(raw_sds),
        
        "recommended_use": resolve_field(raw_sds, "recommended_use"),

        "supplier": resolve_field(raw_sds, "supplier"),

        "signal_word": resolve_field(raw_sds, "signal_word"),

        "revision_date": extract_date(
            resolve_field(raw_sds, "revision_date")
        ),

        "un_number": resolve_field(raw_sds, "un_number"),

        "cas_number": resolve_cas_number(raw_sds),

        "hazard_statements": resolve_field(raw_sds, "hazard_statements"),

        "physical_state": resolve_field(raw_sds, "physical_state"),

        "color": resolve_field(raw_sds, "color"),

        "odor": resolve_field(raw_sds, "odor"),

        "flash_point": resolve_field(raw_sds, "flash_point"),

        "storage_conditions": resolve_field(raw_sds, "storage_conditions"),

        "chemical_formula": resolve_field(raw_sds, "chemical_formula"),
    }

    return normalized