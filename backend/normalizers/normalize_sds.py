from typing import Dict, Any
import re

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
                return sub.get("content", "")

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

    "supplier": [
        "supplier",
        "supplier's details",
        "company information",
        "manufacturer",
    ],

    "signal_word": [
        "signal word",
    ],

    "hazard_statements": [
        "hazard statements",
        "hazard statement(s)",
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

    "signal_word": [2],
    "hazard_statements": [2],

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

def normalize_sds(raw_sds):

    normalized = {
        "product_name": resolve_product_name(raw_sds),

        "supplier": resolve_field(raw_sds, "supplier"),

        "signal_word": resolve_field(raw_sds, "signal_word"),

        "hazard_statements": resolve_field(raw_sds, "hazard_statements"),

        "physical_state": resolve_field(raw_sds, "physical_state"),

        "color": resolve_field(raw_sds, "color"),

        "odor": resolve_field(raw_sds, "odor"),

        "flash_point": resolve_field(raw_sds, "flash_point"),

        "storage_conditions": resolve_field(raw_sds, "storage_conditions"),

        "chemical_formula": resolve_field(raw_sds, "chemical_formula"),
    }

    return normalized