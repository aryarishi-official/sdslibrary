"""
SDS Extractor  v2.0
===================
Extracts key fields from Safety Data Sheet PDFs across multiple publisher
formats (Airgas, ThermoFisher/Fisher Scientific, NIST, and generics).

Design philosophy
-----------------
The previous extractor relied on layout-aware span positioning to find
field values.  That approach is fragile: slight differences in font,
column placement, or page geometry cause the label/value column split to
misfire, pulling footer text (version numbers, page counts) into content
fields.

This version uses a two-layer strategy:

  Layer 1 – REGEX on plain text (primary, high-confidence)
      pdftotext -layout is called once per file.  The output preserves
      horizontal spacing so multi-column footer lines appear as a single
      long line.  Tight, field-specific regular expressions are applied
      directly to this text.  Because each pattern is anchored to its
      label ("Revision Date", "CAS No", etc.), it cannot accidentally
      capture an adjacent column's value.

  Layer 2 – pdfplumber structured text (fallback / enrichment)
      For fields that the regex layer misses (or for richer section
      content), pdfplumber provides page-by-page plain text that is used
      to extract section bodies, hazard codes, exposure limits, etc.

This means the critical identity fields (product name, CAS number,
revision date, version) are extracted with simple, auditable regex and
are NOT affected by layout detection at all.

Supported formats
-----------------
  • Airgas (Air Liquide)  – footer: "Date of issue/Date of revision : …"
  • ThermoFisher / Fisher Scientific – header: "Revision Date DD-Mon-YYYY"
  • NIST Standard Reference Materials – "Date of Issue: DD Month YYYY"
  • Generic GHS SDS – falls back to broad date/version patterns

Output
------
Returns a dict (and optionally writes JSON + HTML) with:
  meta          – product_name, cas_numbers, revision_date, version,
                  previous_revision_date, sds_number, supplier,
                  signal_word, format_detected
  hazards       – ghs_h_codes, ghs_p_codes, signal_word,
                  hazard_classifications, pictograms (inferred from H-codes)
  composition   – list of {name, cas, concentration}
  physical      – flash_point, boiling_point, melting_point,
                  autoignition_temp, vapor_pressure, density,
                  flammability_limits, solubility
  exposure      – osha_pel, acgih_tlv, niosh_rel (where present)
  transport     – un_number, proper_shipping_name, hazard_class,
                  packing_group
  sections_raw  – dict of section_number → plain text body
"""

from __future__ import annotations

import re
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
#  UTILITY: extract full plain text via pdftotext (layout mode)
# ─────────────────────────────────────────────────────────────────────────────

def _pdftotext_layout(pdf_path: str) -> str:
    """
    Run pdftotext -layout on the given PDF and return the full text.
    Layout mode keeps multi-column footer lines on ONE line, which
    makes it easy to parse "Date of revision : X  Version : Y" without
    confusing the two values.
    Falls back to pdfplumber if pdftotext is not available.
    """
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", "-enc", "UTF-8", pdf_path, "-"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: pdfplumber
    try:
        import pdfplumber
        parts = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text() or ""
                parts.append(t)
        return "\n".join(parts)
    except Exception:
        pass

    return ""


def _pdftotext_plain(pdf_path: str) -> str:
    """
    Run pdftotext (no layout) — cleaner for running section-body regexes
    that span lines.
    """
    try:
        result = subprocess.run(
            ["pdftotext", "-enc", "UTF-8", pdf_path, "-"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return ""


# ─────────────────────────────────────────────────────────────────────────────
#  FORMAT DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def detect_format(text: str) -> str:
    """
    Identify the SDS publisher format from the full text.
    Returns one of: 'airgas', 'thermofisher', 'nist', 'generic'
    """
    if re.search(r'Airgas\s+USA|Air\s+Liquide', text, re.I):
        return 'airgas'
    if re.search(r'Thermo\s*Fisher|Fisher\s*Scientific', text, re.I):
        return 'thermofisher'
    if re.search(r'National\s+Institute\s+of\s+Standards|NIST\b', text, re.I):
        return 'nist'
    return 'generic'


# ─────────────────────────────────────────────────────────────────────────────
#  METADATA EXTRACTION  (Layer 1 – regex on layout text)
# ─────────────────────────────────────────────────────────────────────────────

# Date patterns: M/D/YYYY  |  DD-Mon-YYYY  |  DD Month YYYY  |  Month DD, YYYY
_DATE_RE = (
    r'(?:'
    r'\d{1,2}/\d{1,2}/\d{4}'           # 5/6/2025
    r'|'
    r'\d{1,2}-[A-Za-z]{3}-\d{4}'       # 18-Dec-2025
    r'|'
    r'\d{1,2}\s+[A-Za-z]+\s+\d{4}'    # 31 July 2015
    r'|'
    r'[A-Za-z]+\s+\d{1,2},?\s+\d{4}'  # May 21, 2009
    r')'
)

# CAS number pattern
_CAS_RE = r'\b\d{2,7}-\d{2}-\d\b'


def _first(pattern: str, text: str, flags: int = re.I) -> Optional[str]:
    """Return first captured group (or full match if no group) or None."""
    m = re.search(pattern, text, flags)
    if not m:
        return None
    return (m.group(1) if m.lastindex else m.group(0)).strip()


def _extract_meta_airgas(text_layout: str, text_plain: str) -> dict:
    """
    Extract metadata for Airgas-format SDS.

    Footer pattern (single line in layout mode):
      Date of issue/Date of revision   : 5/6/2025   Date of previous issue  : 10/2/2023  Version  : 4.04  1/13
    """
    meta: dict = {}

    # ── Revision date: from footer (layout text preserves it on one line) ──
    # We extract the FIRST date after "Date of issue/Date of revision"
    # and stop before "Date of previous issue"
    m = re.search(
        r'Date of issue/Date of revision\s*:\s*(' + _DATE_RE + r')',
        text_layout, re.I
    )
    if m:
        meta['revision_date'] = m.group(1).strip()

    # ── Previous revision date ──
    m = re.search(
        r'Date of previous issue\s*:\s*(' + _DATE_RE + r')',
        text_layout, re.I
    )
    if m:
        meta['previous_revision_date'] = m.group(1).strip()

    # ── Version ──
    # In layout mode the footer line is: ...Version   : 4.04    1/13
    # We anchor to "Version" then take the next token that looks like X.XX
    # and is NOT a page count (N/M pattern)
    m = re.search(
        r'\bVersion\s*:\s*([\d]+\.[\d]+)',
        text_layout, re.I
    )
    if m:
        meta['version'] = m.group(1).strip()

    # ── SDS number ──
    m = re.search(r'SDS\s*#\s*:\s*(\S+)', text_plain, re.I)
    if m:
        meta['sds_number'] = m.group(1).strip()

    # ── Product name: from Section 1, GHS product identifier ──
    m = re.search(
        r'GHS product identifier\s*:\s*(.+?)(?:\n|Chemical name)',
        text_plain, re.I | re.S
    )
    if m:
        meta['product_name'] = m.group(1).strip().split('\n')[0].strip()

    # ── Chemical name (more reliable for single-substance SDSs) ──
    m = re.search(r'Chemical name\s*:\s*(.+?)(?:\n|Other means)', text_plain, re.I)
    if m:
        meta['chemical_name'] = m.group(1).strip()

    # ── Supplier ──
    meta['supplier'] = 'Airgas USA, LLC'

    return meta


def _extract_meta_thermofisher(text_layout: str, text_plain: str) -> dict:
    """
    Extract metadata for ThermoFisher/Fisher Scientific SDS.

    Header line (layout mode, single line):
      Creation Date 28-Apr-2009   Revision Date 18-Dec-2025   Revision Number 11
    """
    meta: dict = {}

    # ── Revision date ──
    m = re.search(r'Revision\s+Date\s+(' + _DATE_RE + r')', text_layout, re.I)
    if m:
        meta['revision_date'] = m.group(1).strip()

    # ── Creation date (= original issue date) ──
    m = re.search(r'Creation\s+Date\s+(' + _DATE_RE + r')', text_layout, re.I)
    if m:
        meta['creation_date'] = m.group(1).strip()

    # ── Revision number (version) ──
    m = re.search(r'Revision\s+Number\s+(\d+)', text_layout, re.I)
    if m:
        meta['version'] = m.group(1).strip()

    # ── Product name ──
    # Use re.S so the pattern crosses newlines — on some pdftotext versions/OS
    # the value appears on the next line rather than the same line.
    m = re.search(r'Product\s+Name[\s:]+(.+?)(?:\n\n|Cat\s*No|CAS\s*No)', text_plain, re.I | re.S)
    if m:
        meta['product_name'] = m.group(1).strip().split('\n')[0].strip()
    # Fallback: try layout text (value is always inline there)
    if not meta.get('product_name'):
        m = re.search(r'Product\s+Name\s+(.+?)(?:\n|Cat)', text_layout, re.I)
        if m:
            meta['product_name'] = m.group(1).strip().split('\n')[0].strip()

    # ── CAS number (single substance, from identification section) ──
    m = re.search(r'CAS\s+No\.?\s+(' + _CAS_RE + r')', text_plain, re.I)
    if m:
        meta['cas_number_primary'] = m.group(1).strip()

    # ── Catalogue numbers ──
    m = re.search(r'Cat\s+No\s*\.?\s*:\s*(.+?)(?:\n\n|\nCAS)', text_plain, re.I | re.S)
    if m:
        meta['catalogue_numbers'] = re.sub(r'\s+', ' ', m.group(1)).strip()

    # ── Supplier ──
    meta['supplier'] = 'Thermo Fisher Scientific / Fisher Scientific'

    return meta


def _extract_meta_nist(text_layout: str, text_plain: str) -> dict:
    """
    Extract metadata for NIST SRM SDS.
    """
    meta: dict = {}

    # ── Issue date ──
    m = re.search(r'(?:Date\s+of\s+Issue|Issue\s+Date)\s*:\s*(' + _DATE_RE + r')', text_plain, re.I)
    if m:
        meta['revision_date'] = m.group(1).strip()

    # ── SRM number ──
    m = re.search(r'SRM\s+Number\s*:\s*(\S+)', text_plain, re.I)
    if m:
        meta['srm_number'] = m.group(1).strip()

    # ── Product name (SRM Name) ──
    m = re.search(r'SRM\s+Name\s*:\s*(.+?)(?:\n|Other)', text_plain, re.I)
    if m:
        meta['product_name'] = m.group(1).strip()

    meta['supplier'] = 'NIST – National Institute of Standards and Technology'
    return meta


def _extract_meta_generic(text_layout: str, text_plain: str) -> dict:
    """
    Generic fallback metadata extraction.
    """
    meta: dict = {}

    # Try common date-of-revision patterns
    for pat in [
        r'(?:Revision|Revised|Issue)\s+Date\s*:?\s*(' + _DATE_RE + r')',
        r'Date\s+(?:of\s+)?(?:Revision|Issue)\s*:?\s*(' + _DATE_RE + r')',
    ]:
        m = re.search(pat, text_layout, re.I)
        if m:
            meta['revision_date'] = m.group(1).strip()
            break

    # Version
    m = re.search(r'\bVersion\s*:?\s*([\d]+(?:\.[\d]+)?)\b', text_plain, re.I)
    if m:
        meta['version'] = m.group(1).strip()

    # Product name from GHS identifier
    m = re.search(r'GHS product identifier\s*:\s*(.+?)(?:\n|Chemical)', text_plain, re.I)
    if m:
        meta['product_name'] = m.group(1).strip().split('\n')[0]

    return meta


# ─────────────────────────────────────────────────────────────────────────────
#  CAS NUMBER EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def extract_cas_numbers(text: str) -> list[dict]:
    """
    Extract all CAS numbers with their associated ingredient names.
    Strategy: scan the composition/ingredients section for rows of the form:
        <ingredient name>    <CAS number>    <% or concentration>
    Also picks up standalone CAS numbers from toxicological sections.

    Returns list of {name, cas, concentration} dicts, deduplicated.
    """
    results: list[dict] = []
    seen_cas: set[str] = set()

    # ── Strategy 1: composition table rows ──────────────────────────────────
    # After "Section 3" or "Composition/information on ingredients"
    sec3_match = re.search(
        r'(?:Section\s+3|Composition.{0,50}Ingredients?)(.+?)(?:Section\s+4|\Z)',
        text, re.I | re.S
    )
    if sec3_match:
        sec3_text = sec3_match.group(1)
        # Match: <name>  <CAS>  <optional %>
        # Name must be on same line as CAS number (no embedded newlines)
        for m in re.finditer(
            r'([A-Za-z][^\n]{2,60}?)\s+(' + _CAS_RE + r')\s*([\d\.\-><%]*)',
            sec3_text
        ):
            name = m.group(1).strip()
            cas  = m.group(2).strip()
            conc = m.group(3).strip() or None
            # Filter noise: very short names, or names that are labels/headers
            if len(name) < 3 or re.match(r'(?:CAS|Component|Ingredient|Chemical|criteria|Skin|not met)', name, re.I):
                continue
            # Remove any trailing noise (header words that bled in)
            name = re.split(r'\s{2,}|\bCAS\b|\bComponent\b|\bIngredient\b', name)[0].strip()
            if not name or len(name) < 2:
                continue
            if cas not in seen_cas:
                seen_cas.add(cas)
                results.append({'name': name, 'cas': cas, 'concentration': conc})

    # ── Strategy 1b: Airgas-style line-separated table (name\nCAS\nconc) ──
    # In Airgas plain text, ingredient tables appear as:
    #   Ammonia     (line)
    #   7664-41-7   (line)
    #   100         (line)
    # Scan the sec3 text for CAS numbers and look at preceding/following lines.
    if not results and sec3_match:
        sec3_lines = sec3_match.group(1).split('\n')
        for i, line in enumerate(sec3_lines):
            cas_m = re.search(_CAS_RE, line.strip())
            if not cas_m:
                continue
            cas = cas_m.group(0)
            if cas in seen_cas:
                continue
            # Name: look up to 5 lines back for a chemical name
            # Airgas format: name -> concentration -> CAS (3 lines, blank-separated)
            name = 'Unknown'
            for j in range(i - 1, max(i - 6, -1), -1):
                prev = sec3_lines[j].strip()
                if not prev:
                    continue  # skip blank lines
                if re.match(r'^(\d|%|CAS|Ingredient|Component|Substance|Any concentration|Occupational|There are no)', prev, re.I):
                    continue  # skip numeric/header lines
                if 2 < len(prev) < 80 and re.match(r'[A-Za-z]', prev):
                    name = prev
                    break
            # Concentration: look 1-2 lines forward
            conc = None
            for j in range(i + 1, min(i + 3, len(sec3_lines))):
                nxt = sec3_lines[j].strip()
                if re.match(r'^[\d\.]+\s*(%|$)', nxt):
                    conc = nxt
                    break
            seen_cas.add(cas)
            results.append({'name': name, 'cas': cas, 'concentration': conc})

    # ── Strategy 2: any CAS number anywhere if sec3 found none ─────────────
    if not results:
        for m in re.finditer(_CAS_RE, text):
            cas = m.group(0)
            if cas not in seen_cas:
                seen_cas.add(cas)
                # Try to grab the word(s) before the CAS as a name
                prefix = text[max(0, m.start()-80):m.start()]
                name_m = re.search(r'([A-Za-z][\w\s,\(\)-]{2,40})\s*$', prefix)
                name = name_m.group(1).strip() if name_m else 'Unknown'
                results.append({'name': name, 'cas': cas, 'concentration': None})

    return results


# ─────────────────────────────────────────────────────────────────────────────
#  HAZARD CODE EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

# H-code → GHS pictogram mapping (UN GHS Rev 9)
_HCODE_TO_GHS: dict[str, list[str]] = {
    'H200': ['GHS01'], 'H201': ['GHS01'], 'H202': ['GHS01'],
    'H203': ['GHS01'], 'H204': ['GHS01'], 'H205': ['GHS01'],
    'H220': ['GHS02'], 'H221': ['GHS02'], 'H222': ['GHS02'],
    'H223': ['GHS02'], 'H224': ['GHS02'], 'H225': ['GHS02'],
    'H226': ['GHS02'], 'H228': ['GHS02'], 'H229': ['GHS02'],
    'H230': ['GHS02'], 'H231': ['GHS02'],
    'H240': ['GHS01'], 'H241': ['GHS01', 'GHS02'],
    'H242': ['GHS02'],
    'H250': ['GHS02'], 'H251': ['GHS02'], 'H252': ['GHS02'],
    'H260': ['GHS02'], 'H261': ['GHS02'],
    'H270': ['GHS03'], 'H271': ['GHS01', 'GHS03'], 'H272': ['GHS03'],
    'H280': ['GHS04'], 'H281': ['GHS04'],
    'H290': ['GHS05'],
    'H300': ['GHS06'], 'H301': ['GHS06'], 'H304': ['GHS08'],
    'H310': ['GHS06'], 'H311': ['GHS06'],
    'H314': ['GHS05'], 'H315': ['GHS07'],
    'H317': ['GHS07'], 'H318': ['GHS05'], 'H319': ['GHS07'],
    'H320': ['GHS07'],
    'H330': ['GHS06'], 'H331': ['GHS06'], 'H332': ['GHS07'],
    'H334': ['GHS08'], 'H335': ['GHS07'],
    'H336': ['GHS07'],
    'H340': ['GHS08'], 'H341': ['GHS08'],
    'H350': ['GHS08'], 'H351': ['GHS08'],
    'H360': ['GHS08'], 'H361': ['GHS08'],
    'H370': ['GHS08'], 'H371': ['GHS08'],
    'H372': ['GHS08'], 'H373': ['GHS08'],
    'H400': ['GHS09'], 'H401': ['GHS09'], 'H402': ['GHS09'],
    'H410': ['GHS09'], 'H411': ['GHS09'],
    'H420': ['GHS07'],
}

_GHS_NAMES = {
    'GHS01': 'Exploding Bomb (Explosive)',
    'GHS02': 'Flame (Flammable)',
    'GHS03': 'Flame Over Circle (Oxidizing)',
    'GHS04': 'Gas Cylinder (Compressed Gas)',
    'GHS05': 'Corrosion (Corrosive)',
    'GHS06': 'Skull and Crossbones (Acute Toxicity)',
    'GHS07': 'Exclamation Mark (Irritant / Harmful)',
    'GHS08': 'Health Hazard (Serious Health Hazard)',
    'GHS09': 'Environmental (Aquatic Toxicity)',
}


def extract_hazards(text: str) -> dict:
    """
    Extract GHS H-codes, P-codes, signal word, classifications, and infer pictograms.
    """
    # H-codes
    h_codes = sorted(set(re.findall(r'\bH[2-4]\d{2}[a-zA-Z]?\b', text)))

    # P-codes
    p_codes = sorted(set(re.findall(r'\bP[1-5]\d{2}(?:\+P[1-5]\d{2})*\b', text)))

    # Signal word
    signal_word = None
    m = re.search(r'\bSignal\s+[Ww]ord\s*:?\s*(Danger|Warning)', text, re.I)
    if m:
        signal_word = m.group(1).capitalize()

    # Classification strings (e.g. "FLAMMABLE GASES - Category 2")
    classifications = re.findall(
        r'[A-Z][A-Z\s\(\)/]+ - (?:Category|Liquefied gas|Compressed gas)[^\n]*',
        text
    )
    classifications = [c.strip() for c in classifications if len(c.strip()) > 5][:20]

    # Infer pictograms from H-codes
    ghs_codes: set[str] = set()
    for h in h_codes:
        for g in _HCODE_TO_GHS.get(h.upper(), []):
            ghs_codes.add(g)
    pictograms = [
        {'ghs_code': g, 'description': _GHS_NAMES.get(g, ''), 'inferred_from': 'h_codes'}
        for g in sorted(ghs_codes)
    ]

    return {
        'signal_word': signal_word,
        'h_codes': h_codes,
        'p_codes': p_codes,
        'classifications': classifications,
        'pictograms': pictograms,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  PHYSICAL/CHEMICAL PROPERTIES
# ─────────────────────────────────────────────────────────────────────────────

def _extract_property(label_pattern: str, text: str) -> Optional[str]:
    """
    Generic extractor: find <label>  :  <value> or <label>  <value>
    in the text.  Returns the first match, stripped.
    """
    m = re.search(
        label_pattern + r'[\s:]*([^\n]{1,80})',
        text, re.I
    )
    if m:
        val = m.group(1).strip()
        # Remove trailing noise (page numbers, long repeated content)
        val = re.split(r'\s{3,}|\bDate\b|\bSection\b|\bPage\b', val)[0].strip()
        return val if val else None
    return None


def extract_physical_properties(text: str) -> dict:
    """
    Extract key physical/chemical properties.
    """
    props: dict = {}

    # Flash point — skip for gases that say "does not sustain combustion"
    fp_m = re.search(
        r'Flash\s+[Pp]oint(?:/[Rr]ange)?\s*[:\s]*(-?\d[\d\s\.\-°CFftoand]*(?:°[CF])?)',
        text, re.I
    )
    if fp_m:
        ctx = text[max(0, fp_m.start()-10):fp_m.end()+100]
        if 'not sustain' not in ctx.lower() and 'not applicable' not in ctx.lower():
            props['flash_point'] = fp_m.group(1).strip()

    # Autoignition temperature
    m = re.search(
        r'Auto(?:ignition|-ignition)\s+[Tt]emperature\s*[:\s]*(-?\d[\d\s\.°CFf]*)',
        text, re.I
    )
    if m:
        props['autoignition_temperature'] = m.group(1).strip()

    # Boiling point
    m = re.search(
        r'[Bb]oiling\s+[Pp]oint(?:/[Rr]ange)?\s*[:\s]*(-?\d[\d\s\.\-°CFf]*)',
        text, re.I
    )
    if m:
        props['boiling_point'] = m.group(1).strip()

    # Melting / freezing point
    m = re.search(
        r'[Mm]elting\s+[Pp]oint(?:/[Ff]reezing\s+[Pp]oint)?\s*[:\s]*(-?\d[\d\s\.\-°CFf]*)',
        text, re.I
    )
    if m:
        props['melting_point'] = m.group(1).strip()

    # Vapor pressure
    m = re.search(
        r'[Vv]apor\s+[Pp]ressure\s*[:\s]*(-?\d[\d\s\.a-zA-Z@°()/]*)',
        text, re.I
    )
    if m:
        props['vapor_pressure'] = m.group(1).strip()

    # Density / specific gravity
    m = re.search(
        r'[Dd]ensity\s*/\s*[Ss]pecific\s+[Gg]ravity\s*[:\s]*([\d\.]+)',
        text, re.I
    )
    if not m:
        m = re.search(r'[Ss]pecific\s+[Gg]ravity\s*[:\s]*([\d\.]+)', text, re.I)
    if m:
        props['density'] = m.group(1).strip()

    # Flammability limits
    lower_m = re.search(r'[Ll]ower(?:\s+[Ee]xplosive)?\s+[Ll]imit\s*[:\s]*([\d\.]+)\s*(?:vol\s*%|%)', text)
    upper_m = re.search(r'[Uu]pper(?:\s+[Ee]xplosive)?\s+[Ll]imit\s*[:\s]*([\d\.]+)\s*(?:vol\s*%|%)', text)
    if lower_m:
        props['flammability_limit_lower'] = lower_m.group(1) + ' vol%'
    if upper_m:
        props['flammability_limit_upper'] = upper_m.group(1) + ' vol%'

    # Solubility
    m = re.search(r'[Ww]ater\s+[Ss]olubility\s*[:\s]*([^\n]{1,60})', text)
    if not m:
        m = re.search(r'[Ss]olubility\s+in\s+water\s*[:\s]*([^\n]{1,60})', text)
    if m:
        props['water_solubility'] = m.group(1).strip()

    # Molecular weight
    m = re.search(r'[Mm]olecular\s+[Ww]eight\s*[:\s]*([\d\.]+\s*g/mol[e]?)', text)
    if m:
        props['molecular_weight'] = m.group(1).strip()

    # pH
    m = re.search(r'\bpH\s*[:\s]*([\d\.]+)\b', text)
    if m:
        props['pH'] = m.group(1).strip()

    return props


# ─────────────────────────────────────────────────────────────────────────────
#  EXPOSURE LIMITS
# ─────────────────────────────────────────────────────────────────────────────

def extract_exposure_limits(text: str) -> dict:
    """
    Extract occupational exposure limits for the primary substance.
    Handles OSHA PEL, ACGIH TLV, NIOSH REL patterns.
    """
    limits: dict = {}

    # OSHA PEL
    m = re.search(
        r'OSHA\s+(?:PEL|P\.E\.L\.)\s*[:\s]*(?:TWA[:\s]*)?([\d\.]+\s*(?:ppm|mg/m[³3]))',
        text, re.I
    )
    if m:
        limits['osha_pel_twa'] = m.group(1).strip()

    # ACGIH TLV TWA
    m = re.search(
        r'ACGIH\s+(?:TLV|T\.L\.V\.)\s*[:\s]*(?:TWA[:\s]*)?([\d\.]+\s*(?:ppm|mg/m[³3]))',
        text, re.I
    )
    if not m:
        m = re.search(r'TWA\s*:\s*([\d\.]+\s*ppm)', text, re.I)
    if m:
        limits['acgih_tlv_twa'] = m.group(1).strip()

    # NIOSH REL
    m = re.search(
        r'NIOSH\s+(?:REL|R\.E\.L\.)\s*[:\s]*(?:TWA[:\s]*)?([\d\.]+\s*(?:ppm|mg/m[³3]))',
        text, re.I
    )
    if m:
        limits['niosh_rel_twa'] = m.group(1).strip()

    # STEL (any agency)
    m = re.search(r'STEL\s*[:\s]*([\d\.]+\s*(?:ppm|mg/m[³3]))', text, re.I)
    if m:
        limits['stel'] = m.group(1).strip()

    return limits


# ─────────────────────────────────────────────────────────────────────────────
#  TRANSPORT INFORMATION
# ─────────────────────────────────────────────────────────────────────────────

def extract_transport(text: str) -> dict:
    """
    Extract UN number, shipping name, hazard class, packing group from
    Section 14 text.  Works for both Airgas and ThermoFisher layouts.
    """
    transport: dict = {}

    # UN number (most reliable single field)
    m = re.search(r'\bUN\s*(\d{4})\b', text)
    if m:
        transport['un_number'] = 'UN' + m.group(1)

    # Proper shipping name
    m = re.search(
        r'(?:Proper\s+[Ss]hipping\s+[Nn]ame|UN\s+proper\s+shipping\s+name)\s*[:\s]*([A-Z][A-Z,\s\(\)\-]+)',
        text
    )
    if m:
        transport['proper_shipping_name'] = m.group(1).strip()

    # Hazard class
    m = re.search(r'[Hh]azard\s+[Cc]lass(?:es)?\s*[:\s]*([\d\.]+(?:\s*\([\d\.]+\))?)', text)
    if m:
        transport['hazard_class'] = m.group(1).strip()

    # Packing group — value must be I, II, or III as a standalone token,
    # not embedded inside words like "IATA". Use a word boundary after the
    # Roman numeral and require it is followed by whitespace or end-of-line.
    m = re.search(r'[Pp]acking\s+[Gg]roup\s*[:\s]*(I{1,3})(?=\s|$)', text, re.M)
    if m:
        transport['packing_group'] = m.group(1).upper()

    return transport


# ─────────────────────────────────────────────────────────────────────────────
#  SECTION BODY EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

_SECTION_HEADER_RE = re.compile(
    r'^(?:Section\s+)?(\d{1,2})[.\s]+([A-Z][^\n]{3,60})',
    re.MULTILINE
)


def extract_sections_raw(text: str) -> dict[str, dict]:
    """
    Split the plain text into sections by "Section N. Title" headers.
    Returns { '1': {'title': '...', 'text': '...'}, '2': {...}, ... }

    Uses a simple scan: find all section headers, then slice the text
    between consecutive headers.  No layout awareness needed.
    """
    sections: dict[str, dict] = {}
    headers = list(_SECTION_HEADER_RE.finditer(text))

    for i, m in enumerate(headers):
        num = m.group(1)
        title = m.group(2).strip()
        start = m.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        body = text[start:end].strip()
        # Clean up: remove repeated footer noise (page N/M pattern)
        body = re.sub(r'(?m)^.*Date of issue.*\n?', '', body)
        body = re.sub(r'(?m)^.*Date of previous.*\n?', '', body)
        body = re.sub(r'(?m)^.*Revision Date.*\n?', '', body)
        body = re.sub(r'(?m)^Page\s+\d+\s*/\s*\d+.*\n?', '', body)
        body = re.sub(r'\n{3,}', '\n\n', body).strip()
        sections[num] = {'title': title, 'text': body}

    return sections


# ─────────────────────────────────────────────────────────────────────────────
#  TOXICOLOGY DATA
# ─────────────────────────────────────────────────────────────────────────────

def extract_toxicology(text: str) -> dict:
    """
    Extract key toxicology data from Section 11.
    """
    tox: dict = {}

    # LD50 oral
    m = re.search(r'LD50\s+[Oo]ral\s*[:\s]*([\d,\.]+\s*mg/kg[^\n]*)', text)
    if m:
        tox['ld50_oral'] = m.group(1).strip()

    # LC50 inhalation
    m = re.search(r'LC50\s+[Ii]nhalation\s*[:\s]*([\d,\.]+\s*(?:mg/[lL]|ppm)[^\n]*)', text)
    if not m:
        m = re.search(r'LC50\s*[:\s]*([\d,\.]+\s*(?:mg/[lL]|ppm)[^\n]*)', text)
    if m:
        tox['lc50_inhalation'] = m.group(1).strip()

    # Carcinogenicity
    for agency in ['IARC', 'NTP', 'ACGIH', 'OSHA']:
        m = re.search(agency + r'\s*[:\s]*([^\n]{5,60})', text)
        if m:
            tox.setdefault('carcinogenicity', {})[agency] = m.group(1).strip()

    return tox


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN EXTRACTION FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def extract_sds(pdf_path: str) -> dict:
    """
    Master extraction function.  Takes a path to an SDS PDF, returns a
    structured dict with all extracted fields.

    Parameters
    ----------
    pdf_path : str
        Absolute or relative path to the SDS PDF file.

    Returns
    -------
    dict with keys:
        meta, hazards, composition, physical, exposure, transport,
        toxicology, sections_raw
    """
    pdf_path = str(pdf_path)

    # ── Get raw text in two modes ──────────────────────────────────────────
    text_layout = _pdftotext_layout(pdf_path)   # preserves column structure
    text_plain  = _pdftotext_plain(pdf_path)    # clean for section parsing

    # Use layout text for all regex extraction (header/footer fields are
    # single lines there); use plain text for section bodies.
    text_for_regex = text_layout if text_layout.strip() else text_plain

    # ── Detect format ──────────────────────────────────────────────────────
    fmt = detect_format(text_for_regex)

    # ── Extract metadata per format ────────────────────────────────────────
    if fmt == 'airgas':
        meta = _extract_meta_airgas(text_layout, text_plain)
    elif fmt == 'thermofisher':
        meta = _extract_meta_thermofisher(text_layout, text_plain)
    elif fmt == 'nist':
        meta = _extract_meta_nist(text_layout, text_plain)
    else:
        meta = _extract_meta_generic(text_layout, text_plain)
    meta['format_detected'] = fmt
    meta['source_file'] = Path(pdf_path).name

    # ── Shared fields across all formats ──────────────────────────────────
    # Signal word
    sw = re.search(r'\bSignal\s+[Ww]ord\s*:?\s*(Danger|Warning)', text_for_regex, re.I)
    if sw:
        meta['signal_word'] = sw.group(1).capitalize()

    # ── Section bodies ─────────────────────────────────────────────────────
    sections = extract_sections_raw(text_plain if text_plain.strip() else text_layout)

    # ── Composition & CAS numbers ──────────────────────────────────────────
    composition = extract_cas_numbers(text_plain if text_plain.strip() else text_layout)

    # Also put primary CAS in meta if composition has exactly one entry
    if composition and len(composition) == 1 and 'cas_number_primary' not in meta:
        meta['cas_number_primary'] = composition[0]['cas']
    elif not meta.get('cas_number_primary') and composition:
        meta['cas_number_primary'] = composition[0]['cas']  # first found

    # ── Hazards ───────────────────────────────────────────────────────────
    hazards = extract_hazards(text_for_regex)
    if hazards.get('signal_word') and not meta.get('signal_word'):
        meta['signal_word'] = hazards['signal_word']

    # ── Physical properties ───────────────────────────────────────────────
    # Prefer layout text: ThermoFisher PDFs render property values on the
    # same line as their labels only in -layout mode; plain mode separates
    # them into different lines making regex matching fail.
    physical = extract_physical_properties(text_layout if text_layout.strip() else text_plain)

    # ── Exposure limits ───────────────────────────────────────────────────
    exposure = extract_exposure_limits(text_for_regex)

    # ── Transport ─────────────────────────────────────────────────────────
    # Use layout text for transport: ThermoFisher section 14 renders
    # "Hazard Class   3" and "Packing Group   II" on single lines only
    # in layout mode; plain mode separates labels from values across lines.
    sec14_text = sections.get('14', {}).get('text', text_for_regex)
    # Try layout text first (more reliable for column-heavy transport tables)
    transport = extract_transport(text_layout if text_layout.strip() else sec14_text)
    # Fallback: search full plain text for UN number if still empty
    if not transport.get('un_number'):
        transport = extract_transport(text_for_regex)

    # ── Toxicology ────────────────────────────────────────────────────────
    sec11_text = sections.get('11', {}).get('text', text_for_regex)
    toxicology = extract_toxicology(sec11_text)

    return {
        'meta': meta,
        'hazards': hazards,
        'composition': composition,
        'physical': physical,
        'exposure': exposure,
        'transport': transport,
        'toxicology': toxicology,
        'sections_raw': {k: v['title'] + '\n' + v['text'] for k, v in sections.items()},
    }


# ─────────────────────────────────────────────────────────────────────────────
#  HTML REPORT GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

def _esc(s) -> str:
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def render_html(result: dict, title: str = '') -> str:
    """
    Render extraction results as a clean HTML page.
    """
    m = result['meta']
    h = result['hazards']
    comp = result['composition']
    phys = result['physical']
    exp  = result['exposure']
    trans = result['transport']
    tox  = result['toxicology']

    def kv_rows(d: dict) -> str:
        rows = ''
        for k, v in d.items():
            if v is None:
                continue
            if isinstance(v, (dict, list)):
                v = json.dumps(v, ensure_ascii=False)
            rows += f'<tr><td class="label">{_esc(k)}</td><td>{_esc(v)}</td></tr>\n'
        return rows

    def section_table(heading: str, d: dict) -> str:
        if not any(v for v in d.values() if v is not None and v != {} and v != []):
            return ''
        return (
            f'<h3>{_esc(heading)}</h3>'
            f'<table><tbody>{kv_rows(d)}</tbody></table>'
        )

    # Composition table
    comp_html = ''
    if comp:
        comp_html = '<h3>Composition / Ingredients</h3><table>'
        comp_html += '<thead><tr><th>Name</th><th>CAS Number</th><th>Concentration</th></tr></thead><tbody>'
        for c in comp:
            comp_html += (
                f'<tr><td>{_esc(c["name"])}</td>'
                f'<td><code>{_esc(c["cas"])}</code></td>'
                f'<td>{_esc(c.get("concentration") or "")}</td></tr>'
            )
        comp_html += '</tbody></table>'

    # Hazard codes
    haz_html = ''
    if h['h_codes']:
        h_badges = ' '.join(
            f'<span class="badge h-badge">{_esc(c)}</span>' for c in h['h_codes']
        )
        p_badges = ' '.join(
            f'<span class="badge p-badge">{_esc(c)}</span>' for c in h['p_codes']
        )
        ghs_badges = ' '.join(
            f'<span class="badge ghs-badge">{_esc(p["ghs_code"])}</span>'
            for p in h['pictograms']
        )
        haz_html = (
            f'<h3>Hazards</h3>'
            f'<p><strong>Signal word:</strong> {_esc(h.get("signal_word") or "—")}</p>'
            f'<p><strong>GHS Pictograms (inferred):</strong> {ghs_badges or "—"}</p>'
            f'<p><strong>H-Codes:</strong> {h_badges}</p>'
            f'<p><strong>P-Codes:</strong> {p_badges or "—"}</p>'
        )
        if h['classifications']:
            haz_html += '<ul>' + ''.join(
                f'<li>{_esc(c)}</li>' for c in h['classifications']
            ) + '</ul>'

    product = m.get('product_name') or m.get('chemical_name') or title

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>SDS – {_esc(product)}</title>
  <style>
    body  {{ font-family: Arial, sans-serif; font-size: 13px; margin: 24px; color: #222; max-width: 1100px; }}
    h2    {{ color: #1a1a6e; border-bottom: 2px solid #1a1a6e; padding-bottom: 6px; }}
    h3    {{ color: #2c5f8a; margin-top: 20px; margin-bottom: 6px; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 12px; }}
    th, td {{ border: 1px solid #ccc; padding: 5px 10px; vertical-align: top; text-align: left; }}
    th    {{ background: #e0e8f4; font-weight: bold; }}
    td.label {{ background: #f5f7fa; font-weight: bold; white-space: nowrap; width: 220px; }}
    code  {{ background: #f0f0f0; padding: 1px 4px; border-radius: 3px; font-size: 12px; }}
    .badge {{ display: inline-block; border-radius: 4px; padding: 2px 7px; margin: 2px;
              font-size: 11px; font-weight: bold; }}
    .h-badge  {{ background: #f8d7da; color: #721c24; }}
    .p-badge  {{ background: #fff3cd; color: #856404; }}
    .ghs-badge {{ background: #d4edda; color: #155724; }}
    .meta-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0; }}
    .meta-grid table {{ margin: 0; }}
    .highlight {{ background: #fffde7; }}
  </style>
</head>
<body>
  <h2>Safety Data Sheet — {_esc(product)}</h2>
  <p style="color:#555;font-size:12px">
    Source: <code>{_esc(m.get("source_file",""))}</code> &nbsp;|&nbsp;
    Format: <strong>{_esc(m.get("format_detected",""))}</strong>
  </p>

  <h3>Identity &amp; Version</h3>
  <table>
    <tbody>
      <tr class="highlight"><td class="label">Product Name</td><td><strong>{_esc(m.get("product_name") or m.get("chemical_name") or "—")}</strong></td></tr>
      <tr><td class="label">Chemical Name</td><td>{_esc(m.get("chemical_name") or "—")}</td></tr>
      <tr class="highlight"><td class="label">CAS Number (primary)</td><td><code>{_esc(m.get("cas_number_primary") or "—")}</code></td></tr>
      <tr class="highlight"><td class="label">Revision Date</td><td>{_esc(m.get("revision_date") or "—")}</td></tr>
      <tr><td class="label">Previous Revision Date</td><td>{_esc(m.get("previous_revision_date") or m.get("creation_date") or "—")}</td></tr>
      <tr class="highlight"><td class="label">Version / Revision Number</td><td>{_esc(m.get("version") or "—")}</td></tr>
      <tr><td class="label">SDS / SRM Number</td><td>{_esc(m.get("sds_number") or m.get("srm_number") or "—")}</td></tr>
      <tr><td class="label">Signal Word</td><td>{_esc(m.get("signal_word") or "—")}</td></tr>
      <tr><td class="label">Supplier</td><td>{_esc(m.get("supplier") or "—")}</td></tr>
    </tbody>
  </table>

  {haz_html}
  {comp_html}
  {section_table("Physical &amp; Chemical Properties", phys)}
  {section_table("Exposure Limits", exp)}
  {section_table("Transport Information", trans)}
  {section_table("Toxicology", tox)}
</body>
</html>"""
    return html


# ─────────────────────────────────────────────────────────────────────────────
#  BATCH PROCESSING ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def process_batch(pdf_paths: list[str], out_dir: str = 'sds_output') -> dict:
    """
    Process a list of SDS PDFs.  Writes one JSON + one HTML per file
    into out_dir.  Returns a summary dict of all extracted results.

    Parameters
    ----------
    pdf_paths : list of str
        Paths to SDS PDF files.
    out_dir : str
        Output directory (created if it doesn't exist).

    Returns
    -------
    dict mapping filename → extraction result dict
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    all_results: dict = {}

    for pdf_path in pdf_paths:
        name = Path(pdf_path).stem
        print(f'→  Processing: {name} ...', end=' ', flush=True)
        try:
            result = extract_sds(pdf_path)
            all_results[name] = result

            # Write JSON
            json_path = out / f'{name}.json'
            json_path.write_text(
                json.dumps(result, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )

            # Write HTML
            html_path = out / f'{name}.html'
            html_path.write_text(
                render_html(result, title=name),
                encoding='utf-8'
            )

            meta = result['meta']
            print(
                f'✓  product="{meta.get("product_name") or meta.get("chemical_name")}"'
                f'  cas={meta.get("cas_number_primary")}'
                f'  rev={meta.get("revision_date")}'
                f'  ver={meta.get("version")}'
                f'  fmt={meta.get("format_detected")}'
            )
        except Exception as e:
            print(f'✗  ERROR: {e}')
            all_results[name] = {'error': str(e)}

    # Write a combined summary JSON
    summary_path = out / '_summary.json'
    summary = {}
    for name, r in all_results.items():
        if 'error' in r:
            summary[name] = {'error': r['error']}
            continue
        m = r['meta']
        summary[name] = {
            'product_name':    m.get('product_name') or m.get('chemical_name'),
            'chemical_name':   m.get('chemical_name'),
            'cas_number':      m.get('cas_number_primary'),
            'revision_date':   m.get('revision_date'),
            'previous_date':   m.get('previous_revision_date') or m.get('creation_date'),
            'version':         m.get('version'),
            'sds_number':      m.get('sds_number') or m.get('srm_number'),
            'signal_word':     m.get('signal_word'),
            'supplier':        m.get('supplier'),
            'format':          m.get('format_detected'),
            'un_number':       r['transport'].get('un_number'),
            'hazard_class':    r['transport'].get('hazard_class'),
            'flash_point':     r['physical'].get('flash_point'),
            'h_codes':         r['hazards'].get('h_codes', []),
            'pictograms':      [p['ghs_code'] for p in r['hazards'].get('pictograms', [])],
            'composition':     r['composition'],
        }
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding='utf-8'
    )
    print(f'\n✓  Summary → {summary_path}')
    return all_results


# ─────────────────────────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        description='Extract key fields from SDS PDF files.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single file — outputs v5.json next to the PDF
  python sds_extractor.py path/to/chemical.pdf

  # Multiple files — outputs v5.json in the same folder as the first PDF
  python sds_extractor.py sds1.pdf sds2.pdf sds3.pdf

  # Specify a custom output folder
  python sds_extractor.py chemical.pdf --out /my/output/folder

  # Specify a custom JSON filename
  python sds_extractor.py chemical.pdf --json results.json

  # Process an entire folder of PDFs
  python sds_extractor.py /path/to/sds_folder/*.pdf
        """
    )
    parser.add_argument(
        'pdfs',
        nargs='+',
        help='One or more SDS PDF file paths (also accepts glob patterns from the shell).'
    )
    parser.add_argument(
        '--out', '-o',
        default=None,
        help='Output directory (default: same folder as the first input PDF).'
    )
    parser.add_argument(
    '--json', '-j',
    default=None,
    help='Name of the summary JSON file (default: <input_filename>_v5.json).'
)

    args = parser.parse_args()

    # Resolve all input paths
    pdf_paths = []
    for p in args.pdfs:
        resolved = Path(p)
        if not resolved.exists():
            print(f'⚠  File not found, skipping: {p}')
            continue
        if not resolved.suffix.lower() == '.pdf':
            print(f'⚠  Not a PDF, skipping: {p}')
            continue
        pdf_paths.append(str(resolved.resolve()))

    if not pdf_paths:
        print('✗  No valid PDF files found.')
        print('   Usage: python sds_extractor.py yourfile.pdf')
        sys.exit(1)

    # Determine output directory
    if args.out:
        out_dir = Path(args.out)
    else:
        # Default: same folder as the first input PDF
        out_dir = Path(pdf_paths[0]).parent

    out_dir.mkdir(parents=True, exist_ok=True)

    # Default JSON filename if not provided
    if not args.json:
        args.json = Path(pdf_paths[0]).stem + '_v5_.json'

    # Run extraction
    print(f'\nSDS Extractor v2.0')
    print(f'Input : {len(pdf_paths)} file(s)')
    print(f'Output: {out_dir / args.json}\n')

    all_results = {}
    for pdf_path in pdf_paths:
        name = Path(pdf_path).stem
        print(f'→  {Path(pdf_path).name} ...', end=' ', flush=True)
        try:
            result = extract_sds(pdf_path)
            all_results[name] = result

            # Per-file detailed JSON (named after the PDF)
            per_file_json = out_dir / f'{name}_detail.json'
            per_file_json.write_text(
                json.dumps(result, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )

            meta = result['meta']
            print(
                f'✓  "{meta.get("product_name") or meta.get("chemical_name")}"'
                f'  CAS={meta.get("cas_number_primary")}'
                f'  rev={meta.get("revision_date")}'
                f'  ver={meta.get("version")}'
            )
        except Exception as e:
            print(f'✗  ERROR: {e}')
            all_results[name] = {'error': str(e)}

    # Build and write the summary JSON (v5.json by default)
    summary = {}
    for name, r in all_results.items():
        if 'error' in r:
            summary[name] = {'error': r['error']}
            continue
        m = r['meta']
        summary[name] = {
            'product_name':         m.get('product_name') or m.get('chemical_name'),
            'chemical_name':        m.get('chemical_name'),
            'cas_number':           m.get('cas_number_primary'),
            'revision_date':        m.get('revision_date'),
            'previous_date':        m.get('previous_revision_date') or m.get('creation_date'),
            'version':              m.get('version'),
            'sds_number':           m.get('sds_number') or m.get('srm_number'),
            'signal_word':          m.get('signal_word'),
            'supplier':             m.get('supplier'),
            'format_detected':      m.get('format_detected'),
            'un_number':            r['transport'].get('un_number'),
            'hazard_class':         r['transport'].get('hazard_class'),
            'packing_group':        r['transport'].get('packing_group'),
            'flash_point':          r['physical'].get('flash_point'),
            'boiling_point':        r['physical'].get('boiling_point'),
            'h_codes':              r['hazards'].get('h_codes', []),
            'pictograms':           [p['ghs_code'] for p in r['hazards'].get('pictograms', [])],
            'composition':          r['composition'],
            'osha_pel':             r['exposure'].get('osha_pel_twa'),
            'acgih_tlv':            r['exposure'].get('acgih_tlv_twa'),
            'source_file':          m.get('source_file'),
        }

    json_out = out_dir / args.json
    json_out.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding='utf-8'
    )
    print(f'\n✓  {args.json} → {json_out}')
    if len(pdf_paths) > 1:
        print(f'   (Per-file detail JSONs also written to {out_dir})')