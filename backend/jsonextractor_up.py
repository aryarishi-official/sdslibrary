import re
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import fitz          # PyMuPDF
import pdfplumber
try:
    import camelot
except ImportError:
    camelot = None
import spacy
from spacy.language import Language


# ══════════════════════════════════════════════════════
#  SPACY ENTITY RULER  (pure rule-based, no model download)
# ══════════════════════════════════════════════════════

def _build_nlp() -> Language:
    """
    Build a blank English spaCy pipeline with an EntityRuler that uses
    regex patterns to find chemical / safety entities.

    Uses span_ruler (spaCy ≥ 3.x) with regex patterns so no trained model
    is needed.  The recogniser fires on each subsection's content string
    after full extraction.
    """
    nlp = spacy.blank('en')
    ruler = nlp.add_pipe('entity_ruler', config={'overwrite_ents': True})

    patterns = [
        # CAS Registry Number  e.g. 64-17-5 / 124-38-9
        {'label': 'CAS_NUMBER',   'pattern': [{'TEXT': {'REGEX': r'^\d{2,7}-\d{2}-\d$'}}]},

        # GHS Hazard codes  H200–H420
        {'label': 'GHS_H_CODE',
         'pattern': [{'TEXT': {'REGEX': r'^H[2-4]\d{2}$'}}]},

        # GHS Precautionary codes  P100–P501 (single and combined P####+P####)
        {'label': 'GHS_P_CODE',
         'pattern': [{'TEXT': {'REGEX': r'^P[1-5]\d{2}(\+P[1-5]\d{2})*$'}}]},

        # UN Number  e.g. UN1013 / UN 1013
        {'label': 'UN_NUMBER',
         'pattern': [{'TEXT': 'UN'}, {'TEXT': {'REGEX': r'^\d{4}$'}}]},
        {'label': 'UN_NUMBER',
         'pattern': [{'TEXT': {'REGEX': r'^UN\d{4}$'}}]},

        # Temperature values  e.g. 13 °C / -114 °C / 363 °F
        {'label': 'TEMPERATURE',
         'pattern': [{'TEXT': {'REGEX': r'^-?\d+(\.\d+)?$'}},
                     {'TEXT': {'REGEX': r'^°[CFK]$'}}]},
        # fused: "13-17°C"
        {'label': 'TEMPERATURE',
         'pattern': [{'TEXT': {'REGEX': r'^-?\d[\d\.\-]+°[CFK]$'}}]},

        # Percentage  e.g. 95-96 % / 95%
        {'label': 'PERCENTAGE',
         'pattern': [{'TEXT': {'REGEX': r'^\d{1,3}(-\d{1,3})?$'}},
                     {'TEXT': '%'}]},
        {'label': 'PERCENTAGE',
         'pattern': [{'TEXT': {'REGEX': r'^\d{1,3}%$'}}]},

        # Exposure limits  e.g. 1000 ppm / 1900 mg/m3
        {'label': 'EXPOSURE_LIMIT',
         'pattern': [{'TEXT': {'REGEX': r'^\d+$'}},
                     {'LOWER': {'IN': ['ppm', 'mg/m3', 'mg/m³']}}]},

        # Flash point label hint (content)
        {'label': 'FLASH_POINT',
         'pattern': [{'LOWER': 'flash'}, {'LOWER': 'point'}]},

        # Signal words
        {'label': 'SIGNAL_WORD',
         'pattern': [{'LOWER': {'IN': ['danger', 'warning']}}]},
    ]
    ruler.add_patterns(patterns)
    return nlp


NLP = _build_nlp()


def extract_entities(text: str) -> list[dict]:
    """
    Run the EntityRuler over text and return a list of
    {'text': ..., 'label': ...} dicts (deduplicated).
    """
    if not text or len(text) > 5000:
        return []
    doc = NLP(text)
    seen = set()
    result = []
    for ent in doc.ents:
        key = (ent.text.strip(), ent.label_)
        if key not in seen:
            seen.add(key)
            result.append({'text': ent.text.strip(), 'label': ent.label_})
    return result


# ══════════════════════════════════════════════════════
#  LAYOUT-AWARE PDF EXTRACTION  (PyMuPDF)
# ══════════════════════════════════════════════════════

@dataclass
class LayoutLine:
    """A single reconstructed visual line from a PDF page."""
    text:    str
    is_bold: bool
    x0:      float
    size:    float
    page_no: int
    # Column spans: list of (x0, text, is_bold) for multi-column rows
    spans:   list = field(default_factory=list)

    def is_section_header(self) -> bool:
        return self.size >= 12.0 and self.is_bold

    def is_field_label(self) -> bool:
        """Bold left-column text that isn't a section header."""
        return self.is_bold and not self.is_section_header()

    def is_footer(self) -> bool:
        return self.size <= 8.0


def _spans_from_page(page: fitz.Page) -> list[dict]:
    """Extract all text spans from a page as flat list of dicts."""
    spans = []
    blocks = page.get_text('dict', flags=fitz.TEXT_PRESERVE_WHITESPACE)['blocks']
    for block in blocks:
        if block['type'] != 0:   # 0 = text block
            continue
        for line in block['lines']:
            for span in line['spans']:
                txt = span['text']
                if not txt.strip():
                    continue
                bbox = span['bbox']          # (x0, y0, x1, y1)
                y_mid = (bbox[1] + bbox[3]) / 2
                spans.append({
                    'text':    txt,
                    'x0':      bbox[0],
                    'x1':      bbox[2],
                    'y_mid':   y_mid,
                    'size':    span['size'],
                    'bold':    'Bold' in span['font'] or 'bold' in span['font'],
                    'font':    span['font'],
                })
    return spans


def _group_spans_into_lines(spans: list[dict], y_tol: float = 4.0) -> list[LayoutLine]:
    """
    Group spans that share the same vertical midpoint (within y_tol px)
    into LayoutLine objects.  Within each line, spans are sorted by x0.
    """
    if not spans:
        return []

    spans_sorted = sorted(spans, key=lambda s: (round(s['y_mid'] / y_tol) * y_tol, s['x0']))
    lines: list[LayoutLine] = []
    current_spans: list[dict] = []
    current_y: float = spans_sorted[0]['y_mid']

    def _flush(sp_list):
        if not sp_list:
            return
        sp_list.sort(key=lambda s: s['x0'])
        full_text = ' '.join(s['text'].strip() for s in sp_list if s['text'].strip())
        # Dominant bold: majority vote by character count
        bold_chars = sum(len(s['text']) for s in sp_list if s['bold'])
        total_chars = max(sum(len(s['text']) for s in sp_list), 1)
        is_bold = bold_chars / total_chars >= 0.5
        # Dominant size
        size = max(s['size'] for s in sp_list)
        x0 = sp_list[0]['x0']
        page_no = 0   # set by caller
        col_spans = [(s['x0'], s['text'].strip(), s['bold']) for s in sp_list]
        lines.append(LayoutLine(full_text, is_bold, x0, size, page_no, col_spans))

    for sp in spans_sorted:
        if abs(sp['y_mid'] - current_y) <= y_tol:
            current_spans.append(sp)
        else:
            _flush(current_spans)
            current_spans = [sp]
            current_y = sp['y_mid']
    _flush(current_spans)

    # ── Stitch multi-row bold labels ────────────────────────────────
    # Airgas-style PDFs wrap long field labels across two lines at the same
    # x0 (e.g. "Other means of" → "identification").  Detect and merge them.
    _sfx_lower = {s.lower() for s in _LABEL_SUFFIXES}
    stitched: list[LayoutLine] = []
    i = 0
    while i < len(lines):
        ll = lines[i]
        did_merge = False

        # ── Wrapped bold label stitcher ──────────────────────────────
        # Relaxed: x0 < 200, x0-diff < 30, next line need not be bold.
        if (i + 1 < len(lines)
                and ll.is_bold
                and ll.x0 < 200
                and not ll.is_section_header()
                and not lines[i + 1].is_section_header()):
            nxt = lines[i + 1]
            nxt_clean = nxt.text.strip()
            if nxt_clean and abs(nxt.x0 - ll.x0) < 30:
                is_suffix = nxt_clean.lower() in _sfx_lower
                # Only merge short continuation words that are clearly continuations:
                # must start lowercase, have 1–3 words, be >2 chars, and not be a sentence
                is_lowercase_cont = (
                    nxt_clean[0].islower()
                    and len(nxt_clean) > 2
                    and len(nxt_clean.split()) <= 3
                    and not re.search(r'[.!?]$', nxt_clean)
                )
                is_not_sent    = not re.search(r'[.!?]$', nxt_clean)
                is_not_caps    = not nxt_clean.isupper()
                is_not_table   = not re.search(
                    r'\b(CAS|%|UN|number|Exposure|Ingredient)\b', nxt_clean, re.I)
                if is_not_sent and is_not_caps and is_not_table and (is_suffix or is_lowercase_cont):
                    merged_text  = ll.text.rstrip() + ' ' + nxt_clean
                    merged_spans = ll.spans + nxt.spans
                    stitched.append(LayoutLine(
                        merged_text, True, ll.x0, ll.size, ll.page_no, merged_spans))
                    i += 2
                    did_merge = True

        # ── Unclosed parenthesis continuation (superscript units) ────
        # e.g. "Specific Volume (ft"  +  "\u00b3/lb)"  — superscript pushed to
        # a slightly different y_mid, splitting the label across two lines.
        if not did_merge and i + 1 < len(lines):
            txt = ll.text.strip()
            if txt.count('(') > txt.count(')'):
                nxt = lines[i + 1]
                nxt_clean = nxt.text.strip()
                # Next fragment should close the paren and be close-x
                if nxt_clean and ')' in nxt_clean and abs(nxt.x0 - ll.x0) < 80:
                    merged_text  = ll.text.rstrip() + nxt_clean
                    merged_spans = ll.spans + nxt.spans
                    stitched.append(LayoutLine(
                        merged_text, ll.is_bold, ll.x0, ll.size, ll.page_no, merged_spans))
                    i += 2
                    did_merge = True

        if not did_merge:
            stitched.append(ll)
            i += 1

    return stitched


def _extract_kv_from_columns(line: LayoutLine,
                               label_max_x: float,
                               value_min_x: float) -> Optional[tuple[str, str]]:
    """
    For documents with a strict two-column layout (Airgas style):
    label spans have x0 < label_max_x, value spans have x0 > value_min_x.
    Returns (label, value) if both sides are present, else None.
    """
    # Collect label spans: everything left of the value column (not just label column)
    # This captures mid-span superscript characters like "3" in "ft³/lb)"
    label_parts = [
        t for (x, t, _) in line.spans
        if x < value_min_x and t.strip() not in (':', '')
    ]
    value_parts = [t for (x, t, _) in line.spans if x >= value_min_x and t.strip()]
    if label_parts and value_parts:
        label = ' '.join(p.strip() for p in label_parts).strip()
        # Collapse whitespace around superscript-style digit fragments:
        # e.g. "ft 3 /" → "ft3/" and "ft 3 )" → "ft3)"
        label = re.sub(r'(\w)\s+(\d)\s*([/)])', r'\1\2\3', label)
        value = ' '.join(value_parts).strip()
        return label, value
    return None


def _detect_column_layout(layout_lines: list[LayoutLine]) -> tuple[float, float]:
    """
    Auto-detect the label/value column boundary from the most common
    x0 positions of bold (label) vs non-bold (value) spans.

    Returns (label_max_x, value_min_x).
    """
    from collections import Counter
    bold_x0s = Counter()
    nonbold_x0s = Counter()
    for ll in layout_lines:
        for (x, t, bold) in ll.spans:
            if not t.strip() or t.strip() == ':':
                continue
            bucket = round(x / 5) * 5   # bucket to nearest 5px
            if bold:
                bold_x0s[bucket] += 1
            else:
                nonbold_x0s[bucket] += 1

    # Most common bold x0 = label column
    label_x = bold_x0s.most_common(1)[0][0] if bold_x0s else 25
    # Most common non-bold x0 > label_x = value column
    value_candidates = [(x, c) for x, c in nonbold_x0s.items() if x > label_x + 50]
    value_x = sorted(value_candidates, key=lambda t: -t[1])[0][0] if value_candidates else label_x + 150

    # label_max_x = midpoint between label and value columns
    label_max_x = (label_x + value_x) / 2
    # value_min_x = a bit less than the value column start
    value_min_x = value_x - 20

    return label_max_x, value_min_x


def extract_layout_lines(pdf_path: str) -> list[LayoutLine]:
    """
    Open a PDF with PyMuPDF and return a flat list of LayoutLine objects
    (one per visual text row, across all pages), in reading order.
    """
    doc = fitz.open(pdf_path)
    all_lines: list[LayoutLine] = []
    for page_no, page in enumerate(doc):
        spans = _spans_from_page(page)
        lines = _group_spans_into_lines(spans)
        for ll in lines:
            ll.page_no = page_no
        all_lines.extend(lines)
    doc.close()
    return all_lines


# ══════════════════════════════════════════════════════
#  LATTICE TABLE EXTRACTION  (pdfplumber — preserved from v1)
# ══════════════════════════════════════════════════════

_TABLE_EXTRACT_SETTINGS = {
    'vertical_strategy':    'lines',
    'horizontal_strategy':  'lines',
    'snap_tolerance':       3,
    'join_tolerance':       3,
    'edge_min_length':      3,
    'min_words_vertical':   1,
    'min_words_horizontal': 1,
}


def _is_junk_table(headers: list, rows: list) -> bool:
    """
    Return True if a pdfplumber-extracted table should be discarded.
    Catches: section-title noise rows, single-product-name tables,
    HMIS/NFPA rating pseudo-tables, and corrupt transport tables.
    """
    # Reject 1-column tables (usually section headers or product names)
    non_empty_hdrs = [h for h in headers if h]
    if len(non_empty_hdrs) <= 1:
        return True

    # Reject if first header cell looks like a section title or product name
    first_hdr = non_empty_hdrs[0] if non_empty_hdrs else ''
    if re.match(r'^Section\s+\d', first_hdr, re.IGNORECASE):
        return True

    # Reject HMIS / NFPA rating tables: headers like ['Health', '/', '0']
    # These are small 3-col tables where headers are rating labels, not data fields
    if (len(headers) <= 3
            and any(h in ('/', '') for h in headers)
            and any(re.fullmatch(r'\d', h) for h in headers if h)):
        return True

    # Reject if ALL header cells are single digits, slashes, or empty
    if all(re.fullmatch(r'[\d/]?', h) for h in headers):
        return True

    # Reject if the entire table content is just the product name / section label
    all_cell_text = ' '.join(
        str(v) for row in rows for v in row.values() if v
    ).strip()
    if re.match(r'^(Oxygen|Nitrogen|Argon|Hydrogen|Ethanol|Acetone)\s*$',
                all_cell_text, re.IGNORECASE):
        return True

    return False


def _fix_logpow_header(headers: list) -> list:
    """
    pdfplumber splits 'LogPow' into 'LogP' and 'ow' (subscript on different y).
    Merge them back: [..., 'LogP', 'ow', ...] → [..., 'LogPow', ...].
    Also handles variant 'LogPow' split across columns.
    """
    out = []
    i = 0
    while i < len(headers):
        h = headers[i].strip() if headers[i] else ''
        if h.lower() in ('logp', 'log p') and i + 1 < len(headers):
            nxt = (headers[i + 1] or '').strip()
            if nxt.lower() in ('ow', 'ow\n', 'now'):
                out.append('LogPow')
                i += 2
                continue
        # Also fix "LogP\now" (embedded newline variant)
        if re.match(r'^[Ll]og[Pp]\n?ow$', h):
            out.append('LogPow')
            i += 1
            continue
        out.append(h)
        i += 1
    return out


def _expand_newline_rows(rows: list, headers: list) -> list:
    """
    Some pdfplumber cells contain '\n'-joined multiple values
    (e.g. Classification/Justification table).
    Expand them into separate rows when ALL non-empty columns
    have the same number of '\n'-delimited parts.
    """
    expanded = []
    for row in rows:
        # Count newlines in each non-empty cell
        parts_per_col = {}
        for h in headers:
            val = row.get(h, '') or ''
            if val.strip():
                parts_per_col[h] = [p.strip() for p in val.split('\n') if p.strip()]

        if not parts_per_col:
            expanded.append(row)
            continue

        counts = {len(v) for v in parts_per_col.values()}
        # Only expand when all populated cells have the same number of \n-parts
        # and there is more than one part
        if len(counts) == 1 and list(counts)[0] > 1:
            n = list(counts)[0]
            for i in range(n):
                new_row = {}
                for h in headers:
                    parts = parts_per_col.get(h)
                    if parts:
                        new_row[h] = parts[i] if i < len(parts) else ''
                    else:
                        new_row[h] = row.get(h, '') or ''
                expanded.append(new_row)
        else:
            # Flatten \n → space for non-expandable cells
            flat_row = {h: (row.get(h) or '').replace('\n', ' ').strip() for h in headers}
            expanded.append(flat_row)
    return expanded


# Column headers expected in the Airgas-style 5-agency transport table
_TRANSPORT_AGENCIES = ['DOT', 'TDG', 'Mexico', 'IMDG', 'IATA']
_TRANSPORT_ROW_LABELS = [
    'UN number', 'UN proper shipping name', 'Transport hazard class(es)',
    'Packing group', 'Environmental hazards',
]


def _extract_transport_table(page) -> Optional[dict]:
    """
    Reconstruct the 5-agency transport table (DOT/TDG/Mexico/IMDG/IATA)
    by clustering word x-positions instead of relying on lattice lines.

    Returns a dict {'headers': [...], 'rows': [...]} or None.
    """
    words = page.extract_words(keep_blank_chars=False, x_tolerance=3, y_tolerance=3)
    if not words:
        return None

    # ── Step 1: find y-band containing agency header names ───────────
    agency_words = [w for w in words if w['text'] in _TRANSPORT_AGENCIES]
    if len(agency_words) < 3:
        return None  # not the transport table page

    # Cluster agency words by y to find the header row
    header_y = sorted(set(round(w['top']) for w in agency_words))
    if not header_y:
        return None
    hdr_y = header_y[0]

    # Collect x-centres of each agency column from the header row
    agency_positions = {}  # agency_name → x_centre
    for w in agency_words:
        if abs(w['top'] - hdr_y) < 8:
            agency_positions[w['text']] = (w['x0'] + w['x1']) / 2

    if len(agency_positions) < 3:
        return None

    # Determine the leftmost agency column x (= right edge of row-label column)
    min_agency_x = min(agency_positions.values())

    # ── Step 2: column assignment ─────────────────────────────────────
    def _col_for_x(x: float) -> str:
        # Words to the left of all agency columns → row-label column
        if x < min_agency_x - 20:
            return 'Row label'
        # Find nearest agency column centre
        best, best_dist = None, 9999.0
        for agency, cx in agency_positions.items():
            d = abs(x - cx)
            if d < best_dist:
                best, best_dist = agency, d
        return best if best_dist < 80 else 'Row label'

    # ── Step 3: group words into y-bands ─────────────────────────────
    from collections import defaultdict
    row_bands: dict = defaultdict(list)
    for w in words:
        band = round(w['top'] / 4) * 4  # 4px bucket
        row_bands[band].append(w)

    # Skip bands at/above the header row
    data_y_start = hdr_y + 6
    sorted_bands = sorted(k for k in row_bands if k > data_y_start)

    # ── Step 4: accumulate into logical rows ─────────────────────────
    # Each logical row starts when the Row-label column has a word that
    # begins a known row-label phrase.
    col_order = ['Row label'] + _TRANSPORT_AGENCIES
    raw_rows: list[dict] = []
    current_row: dict = {c: [] for c in col_order}

    for band_y in sorted_bands:
        band_words = sorted(row_bands[band_y], key=lambda w: w['x0'])
        row_texts: dict = {c: [] for c in col_order}
        for w in band_words:
            col = _col_for_x((w['x0'] + w['x1']) / 2)
            row_texts[col].append(w['text'])

        label_parts   = row_texts['Row label']
        has_agency    = any(bool(row_texts[a]) for a in _TRANSPORT_AGENCIES)

        # Detect start of a new logical row
        label_str = ' '.join(label_parts)
        is_new_label = any(
            label_str.lower().startswith(r.lower()[:6])
            for r in _TRANSPORT_ROW_LABELS
        )

        if is_new_label and any(current_row['Row label']):
            flushed = {c: ' '.join(current_row[c]).strip() for c in col_order}
            if any(flushed.get(a) for a in _TRANSPORT_AGENCIES):
                raw_rows.append(flushed)
            current_row = {c: [] for c in col_order}

        for c in col_order:
            current_row[c].extend(row_texts[c])

    # Flush last row
    if any(current_row['Row label']):
        flushed = {c: ' '.join(current_row[c]).strip() for c in col_order}
        if any(flushed.get(a) for a in _TRANSPORT_AGENCIES):
            raw_rows.append(flushed)

    if len(raw_rows) < 2:
        return None

    # ── Step 5: normalise row-label values to known names ────────────
    def _best_label(raw: str) -> str:
        raw_l = raw.lower()
        best_match = raw
        best_score = 0
        for label in _TRANSPORT_ROW_LABELS:
            # Score = length of common prefix
            score = sum(1 for a, b in zip(raw_l, label.lower()) if a == b)
            if score > best_score:
                best_score, best_match = score, label
        return best_match if best_score >= 4 else raw

    headers = ['Field'] + _TRANSPORT_AGENCIES
    rows = []
    for r in raw_rows:
        row_dict = {'Field': _best_label(r.get('Row label', ''))}
        for a in _TRANSPORT_AGENCIES:
            row_dict[a] = r.get(a, '')
        rows.append(row_dict)

    return {'headers': headers, 'rows': rows}


def extract_pdf_tables(pdf_path: str) -> list[dict]:
    """
    Extract lattice tables using pdfplumber, with post-processing to:
    - Reject junk / noise tables (section-header rows, HMIS ratings, etc.)
    - Fix the LogPow split-header bug
    - Expand '\n'-embedded multi-value cells into proper rows
    - Reconstruct the 5-agency transport table via word-position clustering
    """
    pdf_tables = []
    transport_table_found = False

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_no = page.page_number - 1  # 0-indexed to match PyMuPDF

            # ── Transport table: custom word-clustering extractor ──────────
            transport = _extract_transport_table(page)
            if transport and not transport_table_found:
                transport_table_found = True
                pdf_tables.append({
                    'page':    page_no,
                    'bbox':    (-1, -1, -1, -1),
                    'headers': transport['headers'],
                    'rows':    transport['rows'],
                })

            # ── Standard lattice tables ───────────────────────────────────
            raw_tables = page.extract_tables(_TABLE_EXTRACT_SETTINGS)
            for raw in (raw_tables or []):
                if not raw or len(raw) < 2:
                    continue

                # Fix LogPow header split
                raw_headers = [str(h).strip() if h else '' for h in raw[0]]
                headers = _fix_logpow_header(raw_headers)

                if not any(headers):
                    continue

                # Build rows (raw)
                rows = []
                for row in raw[1:]:
                    row_dict = {
                        headers[j]: str(cell).strip() if cell else ''
                        for j, cell in enumerate(row)
                        if j < len(headers)
                    }
                    if any(row_dict.values()):
                        rows.append(row_dict)

                if not rows:
                    continue

                # Reject junk tables
                if _is_junk_table(headers, rows):
                    continue

                # Skip the transport table here — already handled above
                norm_hdr = _normalise_header(' '.join(headers))
                if 'dot' in norm_hdr and 'tdg' in norm_hdr:
                    continue
                # Also skip if this is the broken 2-col version of transport
                if (len(headers) == 2
                        and re.search(r'dot|tdg|mexico|imdg|iata', norm_hdr, re.I)):
                    continue

                # Expand \n-embedded multi-value cells
                rows = _expand_newline_rows(rows, headers)

                pdf_tables.append({
                    'page':    page_no,
                    'bbox':    (-1, -1, -1, -1),
                    'headers': headers,
                    'rows':    rows,
                })

    return pdf_tables

def extract_tables_camelot(pdf_path):
    if camelot is None:
        return []

    tables_out = []

    tables = camelot.read_pdf(pdf_path, pages='all', flavor='lattice')

    for t in tables:
        df = t.df

        # ❌ Reject junk tables (too small)
        if df.shape[0] < 2 or df.shape[1] < 2:
            continue

        # Clean headers
        headers = [str(h).strip() for h in df.iloc[0]]

        # ❌ Reject bad headers (repeated text or all empty)
        if len(set(h for h in headers if h)) <= 1:
            continue

        # ❌ Reject fake tables: headers that look like product names or section titles
        #    e.g. headers=["Oxygen"] or headers=["Section 1. Identification"]
        joined_hdrs = ' '.join(headers).strip()
        if re.match(r'^(Section\s+\d|[A-Z][a-z]+\s*$)', joined_hdrs):
            continue
        # Header tokens that are just a single chemical name / single word (no table meaning)
        if len([h for h in headers if h]) == 1:
            continue

        # ❌ Reject tables where header cells look like merged header+value
        #    e.g. "UN proper Oxygen, shipping name compressed"
        bad_header = any(
            len(h.split()) > 6 or re.search(r'\d{4,}', h)
            for h in headers if h
        )
        if bad_header:
            continue

        # ❌ Reject HMIS / NFPA rating pseudo-tables: small tables with '/' or
        #    single-digit cells as headers (e.g. Health / 0, Flammability / 0)
        if (len(headers) <= 3
                and any(h in ('/', '') for h in headers)
                and any(re.fullmatch(r'\d', h) for h in headers if h)):
            continue

        # ❌ Skip broken 2-col transport table — handled by word-clustering extractor
        joined_hdrs_lower = ' '.join(headers).lower()
        if re.search(r'\b(dot|tdg|imdg|iata)\b', joined_hdrs_lower):
            continue

        rows = []
        for i in range(1, len(df)):
            row = df.iloc[i]

            row_dict = {
                headers[j]: str(row[j]).strip()
                for j in range(len(headers))
                if j < len(headers)
            }

            # ❌ skip empty rows
            if not any(row_dict.values()):
                continue

            rows.append(row_dict)

        if not rows:
            continue

        tables_out.append({
            'page': int(t.page),
            'bbox': t._bbox,
            'headers': headers,
            'rows': rows
        })

    return tables_out


# ══════════════════════════════════════════════════════
#  NOISE FILTER  (v1 patterns preserved + footer size guard)
# ══════════════════════════════════════════════════════

NOISE_RE = re.compile(
    r'^\s*('
    r'Page\s+\d+\s*/\s*\d+.*'
    r'|_{5,}'
    r'|\d{6,}-\d+\s+\d+\s*/\s*\d+.*'
    r'|Safety\s+[Dd]ata\s+[Ss]heet.*'
    r'|acc\.\s+to\s+Regulation.*'
    r'|SAFETY\s+DATA\s+SHEET'
    r'|article\s+number:.*'
    r'|United\s+Kingdom\s+\(en\).*'
    r'|Version:\s*\d.*'
    r'|Replaces\s+version.*'
    r'|Date\s+of\s+issue/Date\s+of\s+revision\s*:.*'
    r'|Date\s+of\s+issue.*\d{4}.*\d+/\d+\s*$'
    r'|\d+/\d{2}/\d{4}\s+Date\s+of\s+previous.*'
    r'|Version\s*:\s*\d+\.\d+\s+\d+/\d+\s*$'
    r'|Ethanol\s+Solution\s+\d+%\s+Revision.*'
    r'|HYDROGEN\s+PEROXIDE\s*$'
    r'|Nitrogen\s*$'
    r'|Already\s+have\s+an\s+account.*'
    r'|Log\s+In\s+\|.*'
    r'|Safety\s+Catalog.*'
    r')\s*$',
    re.IGNORECASE
)

_FOOTER_INLINE_RE = re.compile(
    r'\s*Date\s+of\s+issue/Date\s+of\s+revision\s*:.*?(?:\d+/\d+\s*)?$',
    re.IGNORECASE
)


def is_noise(text: str, layout_line: Optional[LayoutLine] = None) -> bool:
    """Return True if this line should be dropped entirely."""
    if layout_line and layout_line.is_footer():
        return True
    return bool(NOISE_RE.match(text.strip()))


def clean_content(text: str) -> str:
    text = _FOOTER_INLINE_RE.sub('', text)
    text = text.replace("SDS'S", 'SDSs').replace("SDS\u2019S", 'SDSs')
    text = re.sub(r'  +', ' ', text)
    return text.strip()


def deduplicate_sentences(text: str) -> str:
    if not text:
        return text
    parts = re.split(r'(?<=[.!?])\s+', text)
    seen = []
    result = []
    for part in parts:
        norm = re.sub(r'\s+', ' ', part.strip().lower())
        if norm and norm not in seen:
            seen.append(norm)
            result.append(part)
    joined = ' '.join(result)
    # Also collapse runs of the same short phrase repeated without punctuation
    # e.g. "Not available. Not available." → already handled above
    # e.g. "UN1072 UN1072 UN1072" → "UN1072"
    joined = re.sub(r'\b(\S+(?:\s+\S+){0,3})\s+(?:\1\s*){1,}', r'\1 ', joined).strip()
    return joined


# ══════════════════════════════════════════════════════
#  KEY NORMALISATION  (v1 preserved)
# ══════════════════════════════════════════════════════

def normalise_key(key: str) -> str:
    k = key.strip()
    _SPECIAL = {
        'SDS #': 'sds_number', 'SDS#': 'sds_number',
        'Cat No.': 'catalogue_number',
        'CAS No': 'cas_number', 'CAS No.': 'cas_number',
        'UN-No': 'un_number', 'UN-No.': 'un_number',
        'pH': 'ph', 'LogPow': 'log_pow',
        'Partition coefficient: n-octanol/water': 'partition_coefficient_n_octanol_water',
        'Partition coefficient: noctanol/water':  'partition_coefficient_n_octanol_water',
    }
    if k in _SPECIAL:
        return _SPECIAL[k]
    # Normalise slashes to _or_ so substance/mixture → substance_or_mixture
    k = re.sub(r'/', '_or_', k)
    k = re.sub(r'[\\()+&,.\'\[\]#:]', '', k)
    k = re.sub(r'[\s\-]+', '_', k)
    k = re.sub(r'_+', '_', k).strip('_').lower()
    # Remove consecutively duplicated words e.g. reactions_reactions
    k = re.sub(r'\b(\w+)_\1\b', r'\1', k)
    return k


# ══════════════════════════════════════════════════════
#  SECTION HEADER DETECTION  (v1 preserved)
# ══════════════════════════════════════════════════════

_SDS_SECTION_TITLES = {
    '1': 'Identification',
    '2': 'Hazards identification',
    '3': 'Composition/information on ingredients',
    '4': 'First aid measures',
    '5': 'Fire-fighting measures',
    '6': 'Accidental release measures',
    '7': 'Handling and storage',
    '8': 'Exposure controls/personal protection',
    '9': 'Physical and chemical properties',
    '10': 'Stability and reactivity',
    '11': 'Toxicological information',
    '12': 'Ecological information',
    '13': 'Disposal considerations',
    '14': 'Transport information',
    '15': 'Regulatory information',
    '16': 'Other information',
}

SECTION_KEYWORD_RE = re.compile(r'^SECTION\s+(\d{1,2})[.:\s]\s*(.+)$', re.IGNORECASE)
SECTION_FISHER_RE  = re.compile(r'^(\d{1,2})\.\s+([A-Za-z].+)$')
NUMBERED_SUB_RE    = re.compile(r'^(\d{1,2}\.\d{1,2}(?:\.\d+)?)\s+(.+)$')
_MAX_TITLE_LEN     = 80

_TITLE_LEADING_PREP_RE = re.compile(
    r'^(on|in|of|for|at|to|and|or|with|by|from|about|see|as|than|that|which|where|when)\b',
    re.IGNORECASE
)


def parse_numbered_subsection(text: str):
    m = NUMBERED_SUB_RE.match(text.strip())
    return (m.group(1), m.group(2).strip()) if m else None


def parse_section_header(text: str, layout_line: Optional[LayoutLine] = None):
    s = text.strip()

    # ❌ Ignore if too long (likely sentence)
    if len(s.split()) > 10:
        return None

    # ❌ Must start with "Section" OR number-dot format
    m1 = re.match(r'^Section\s+(\d{1,2})[.:]?\s+(.+)$', s, re.IGNORECASE)
    m2 = re.match(r'^(\d{1,2})\.\s+([A-Za-z].+)$', s)

    m = m1 or m2
    if not m:
        return None

    num = int(m.group(1))
    title = m.group(2).strip()

    # ❌ Reject lowercase-start titles (sentences)
    if title and title[0].islower():
        return None

    # ❌ Reject sentences (ending with .)
    if re.search(r'[.!?]$', s):
        return None

    # ❌ Must contain at least one long word
    if not re.search(r'[A-Za-z]{3,}', title):
        return None

    if 1 <= num <= 16:
        return str(num), title

    return None


# ══════════════════════════════════════════════════════
#  CONTEXT / GROUP TRACKING  (v1 preserved)
# ══════════════════════════════════════════════════════

_DUPLICATE_CONTEXT_MAP = {
    '4': {
        'eye contact':  ['First aid measures', 'Potential acute health effects', 'Over-exposure signs/symptoms'],
        'skin contact': ['First aid measures', 'Potential acute health effects', 'Over-exposure signs/symptoms'],
        'inhalation':   ['First aid measures', 'Potential acute health effects', 'Over-exposure signs/symptoms'],
        'ingestion':    ['First aid measures', 'Potential acute health effects', 'Over-exposure signs/symptoms'],
    },
    '11': {
        'inhalation':   ['Routes of exposure', 'Acute health effects', 'Short/long term exposure'],
        'skin contact': ['Routes of exposure', 'Acute health effects', 'Short/long term exposure'],
        'eye contact':  ['Routes of exposure', 'Acute health effects', 'Short/long term exposure'],
        'ingestion':    ['Routes of exposure', 'Acute health effects', 'Short/long term exposure'],
    },
}

_GROUP_HEADERS = {
    '2':  ['ghs label elements', 'precautionary statements', 'label elements'],
    '4':  ['description of necessary first aid measures',
           'most important symptoms', 'over-exposure signs/symptoms',
           'overexposure', 'potential acute health effects',
           'indication of immediate medical attention', 'protection of first-aiders'],
    '11': ['information on the likely routes of exposure',
           'information on toxicological effects', 'potential acute health effects',
           'symptoms related to the physical', 'delayed and immediate effects',
           'short term exposure', 'long term exposure',
           'numerical measures of toxicity', 'potential chronic health effects'],
}


def _resolve_context(section_num: str, sub_title: str, seen_counts: dict) -> Optional[str]:
    norm = sub_title.strip().lower()
    sec_map = _DUPLICATE_CONTEXT_MAP.get(section_num, {})
    contexts = sec_map.get(norm)
    if not contexts:
        return None
    count = seen_counts.get(norm, 0)
    ctx = contexts[count] if count < len(contexts) else f'Context {count + 1}'
    seen_counts[norm] = count + 1
    return ctx


# ══════════════════════════════════════════════════════
#  LABEL SUFFIX / KV HELPERS  (v1 preserved)
# ══════════════════════════════════════════════════════

_LABEL_SUFFIXES = sorted([
    'substance or mixture', 'boiling point and boiling range',
    'including any incompatibilities', 'equipment for fire-fighters',
    'decomposition products', 'routes of exposure', 'occupational hygiene',
    '(flammable) limits', 'for fire-fighters', 'octanol/water',
    'incompatibilities', 'identification', 'coefficient',
    'personnel', 'classified', 'elements', 'controls',
    'mixture', 'media', 'range', 'reactions', 'hazard class(es)',
    'shipping name', 'hazards',
], key=len, reverse=True)


# ── Paragraph / sentence opener prefixes ─────────────────────────────────────
# Text whose key starts with any of these is paragraph body, not a field label.
_PARAGRAPH_OPENERS = (
    'caution:', 'the customer', 'final determination', 'to the best',
    'reprinted with', 'copyright \xa9', 'sdss or', 'nfpa 49',
    'there are no ', 'there is no ', 'keep out of reach',
    'occupational exposure limits, if available',
    'see toxicological information',
    'any concentration shown',
    '\u201crefer to cfr',  # curly-quote variant
    '"refer to cfr',
    'wash contaminated',
    'emissions from ventilation',
    'good general ventilation',
    'eating, drinking and smoking',
    'based on the hazard',
    'personal protective equipment for the body',
    'appropriate footwear',
    'store in accordance',
    'in a fire or if heated',
    'promptly isolate',
    'no action shall be taken',
    'ensure emergency',
    'immediately contact emergency',
)


def _is_paragraph_key(key: str) -> bool:
    """Return True if *key* is actually sentence / paragraph body, not a label."""
    k = key.strip()
    if not k:
        return False
    # Ends with sentence-terminal punctuation
    if re.search(r'[.!?\u201d"]$', k):
        return True
    # Too many words to be a field label
    if len(k.split()) > 10:
        return True
    kl = k.lower()
    for opener in _PARAGRAPH_OPENERS:
        if kl.startswith(opener):
            return True
    # Sentence-starter patterns
    if re.match(
        r'^(The |This |There |These |Those |It |In |As |For |Note |See |Any |All |No )', k
    ):
        return True
    return False


def _strip_label_suffix(line: str):
    s  = line.strip()
    sl = s.lower()
    for sfx in _LABEL_SUFFIXES:
        if sl == sfx:
            return sfx, ''
        if sl.startswith(sfx + ' '):
            return sfx, s[len(sfx):].strip()
    words = s.split()
    if (len(words) <= 2 and len(s) <= 20
            and s[0].islower() and ':' not in s
            and not any(c in s for c in '.!?')):
        return s, ''
    return '', s


KV_COLON_RE = re.compile(
    r'^([A-Za-z0-9][A-Za-z0-9 \-/()+&,.\'#\[\]]{1,60}?)\s+:\s*(.*)$'
)
KV_SPACE_RE = re.compile(
    r'^([A-Z0-9][A-Za-z0-9 \-/()+&,.\'#\[\]]{1,60}?)\s{2,}(.+)$'
)

KNOWN_KEYS = sorted([
    'Product Name', 'Cat No.', 'CAS No', 'Synonyms', 'Recommended Use',
    'Uses advised against', 'Details of the supplier of the safety data sheet',
    'Identification of the substance', 'Article number',
    'EC number', 'CAS number', 'Molecular formula', 'Molar mass',
    'Relevant identified uses', 'Name of substance',
    'Signal word', 'Signal Word', 'Labelling',
    'General Advice', 'Eye Contact', 'Skin Contact', 'Inhalation', 'Ingestion',
    'Notes to Physician', 'Most important symptoms and effects',
    'Most important symptoms', 'General notes', 'Following inhalation',
    'Following skin contact', 'Following eye contact', 'Following ingestion',
    'Suitable Extinguishing Media', 'Unsuitable Extinguishing Media',
    'Suitable extinguishing media', 'Unsuitable extinguishing media',
    'Flash Point', 'Autoignition Temperature',
    'Specific Hazards Arising from the Chemical',
    'Hazardous Combustion Products', 'Hazardous combustion products',
    'Protective Equipment and Precautions for Firefighters',
    'Sensitivity to Mechanical Impact', 'Sensitivity to Static Discharge',
    'Personal Precautions', 'Environmental Precautions',
    'Methods for Containment and Clean',
    'Handling', 'Storage',
    'Engineering Measures', 'Eye/face Protection',
    'Skin and body protection', 'Respiratory Protection',
    'Recommended Filter type', 'Hygiene Measures',
    'Physical State', 'Color', 'Odor', 'Odor Threshold',
    'Melting Point/Range', 'Softening Point', 'Boiling Point/Range',
    'Flammability (liquid)', 'Flammability (solid,gas)',
    'Decomposition Temperature', 'Water Solubility',
    'Vapor Pressure', 'Density / Specific Gravity', 'Vapor Density',
    'Molecular Formula', 'Molecular Weight', 'Explosive Properties',
    'Reactive Hazard', 'Stability', 'Conditions to Avoid',
    'Incompatible Materials', 'Hazardous Decomposition Products',
    'Hazardous Polymerization', 'Hazardous Reactions',
    'Target Organs', 'Other Adverse Effects', 'Endocrine Disrupting Properties',
    'Persistence and Degradability', 'Mobility',
    'Waste Disposal Methods',
    'Prepared By', 'Creation Date', 'Revision Date', 'Print Date',
    'Revision Summary',
], key=len, reverse=True)


def parse_kv(text: str, layout_line: Optional[LayoutLine] = None):
    """
    Parse a key-value pair from a line of text.
    With layout_line: if the line has a known two-column structure, that
    takes priority and was already handled upstream; this is the fallback
    for formats without strict column alignment.
    """
    s = text.strip()
    if not s or not s[0].isalnum():
        return None

    m = KV_COLON_RE.match(s)
    if m:
        key = m.group(1).strip()
        val = m.group(2).strip()
        if 1 <= len(key.split()) <= 6 and not key[0].islower():
            return key, val

    m = KV_SPACE_RE.match(s)
    if m:
        key = m.group(1).strip()
        val = m.group(2).strip()
        if len(key.split()) <= 6:
            return key, val

    for known in KNOWN_KEYS:
        if s.startswith(known) and len(s) > len(known):
            remainder = s[len(known):].strip()
            if remainder and (remainder[0] not in ('(', '-') or remainder.startswith('(')):
                return known, remainder

    return None

def assign_tables_to_sections(sections, tables):
    for table in tables:
        page = int(table.get('page', 0))
        headers = table.get('headers', [])
        hdr_key = _normalise_header(' '.join(headers))

        matched = False
        for sec in sections:
            if 'page_range' not in sec:
                continue
            start, end = sec['page_range']
            if start <= page <= end:
                # Try to attach to a matching subsection by schema
                for sub in sec.get('subsections', []):
                    sub_key = sub.get('normalised_key', '')
                    # Match by header content similarity
                    if any(h.lower() in sub_key or sub_key in h.lower()
                           for h in headers if h):
                        if 'table' not in sub:
                            sub['table'] = {'headers': headers, 'rows': table.get('rows', [])}
                            matched = True
                            break
                # Always also attach at section level for access
                sec.setdefault('tables', []).append(table)
                matched = True
                break


def is_inside_table(line, tables):
    for t in tables:
        bbox = t.get('bbox', (-1, -1, -1, -1))
        if bbox[0] < 0:  # sentinel — spatial position unknown, skip
            continue
        if line.page_no == int(t.get('page', -1)):
            if abs(line.x0 - bbox[0]) < 50:
                return True
    return False


def dedup_words(text):
    words = text.split()
    result = []
    for w in words:
        if not result or result[-1].lower() != w.lower():
            result.append(w)
    return ' '.join(result)


# ══════════════════════════════════════════════════════
#  INLINE PROPERTY SPLITTER  (v1 FIX 5)
# ══════════════════════════════════════════════════════

_INLINE_KV_RE = re.compile(
    r'(?:^|(?<=\. ))'
    r'([A-Z][A-Za-z0-9 \-/()]{1,40}?)\s*:\s*'
    r'([^.]+\.?)'
)


def split_mixed_properties(content: str) -> list[dict]:
    matches = list(_INLINE_KV_RE.finditer(content))
    if len(matches) < 2:
        return []
    result = []
    for m in matches:
        key = m.group(1).strip()
        val = m.group(2).strip().rstrip('.')
        if len(key.split()) <= 6:
            result.append({'key': normalise_key(key), 'value': val})
    return result if len(result) >= 2 else []


# ══════════════════════════════════════════════════════
#  TABLE SCHEMA DETECTION  (v1 preserved)
# ══════════════════════════════════════════════════════

_TABLE_SCHEMAS = {
    'classification justification':
        {'headers': ['Classification', 'Justification'],
         'right_hints': ['Expert judgment', 'Classification regulation', 'Supplier', 'Test data', 'Calculation method']},
    'ingredient name % cas number':
        {'headers': ['Ingredient name', '%', 'CAS number'], 'right_hints': None},
    'ingredient name exposure limits':
        {'headers': ['Ingredient name', 'Exposure limits'], 'right_hints': None},
    'product/ingredient name logpow bcf potential':
        {'headers': ['Product/ingredient name', 'LogPow', 'BCF', 'Potential'],
         'right_hints': ['Low', 'High', 'Medium', '-']},
    # Airgas full transport table (DOT / TDG / Mexico / IMDG / IATA columns)
    # — old flat-column variant (fallback)
    'dot tdg mexico imdg iata':
        {'headers': ['DOT', 'TDG', 'Mexico', 'IMDG', 'IATA'], 'right_hints': None},
    # — new word-clustered variant with row-label column
    'field dot tdg mexico imdg iata':
        {'headers': ['Field', 'DOT', 'TDG', 'Mexico', 'IMDG', 'IATA'], 'right_hints': None},
    # Simplified 3-column fallback
    'un number un proper shipping name transport hazard class':
        {'headers': ['UN number', 'UN proper shipping name', 'Transport hazard class(es)'], 'right_hints': None},
    # Ecological: LogPow / BCF / Potential
    'logpow bcf potential':
        {'headers': ['Product/ingredient name', 'LogPow', 'BCF', 'Potential'],
         'right_hints': ['Low', 'High', 'Medium', '-']},
    'product/ingredient name logpow bcf potential':
        {'headers': ['Product/ingredient name', 'LogPow', 'BCF', 'Potential'],
         'right_hints': ['Low', 'High', 'Medium', '-']},
    'component cas-no. concentration (%)':
        {'headers': ['Component', 'CAS-No.', 'Concentration (%)'], 'right_hints': None},
    'component cas no weight %':
        {'headers': ['Component', 'CAS No', 'Weight %'], 'right_hints': None},
    'component cas no tsca tsca inventory notification - tsca - epa regulatory':
        {'headers': ['Component', 'CAS No', 'TSCA',
                     'TSCA Inventory notification - Active-Inactive',
                     'TSCA - EPA Regulatory Flags'],
         'right_hints': None},
}


def _normalise_header(line: str) -> str:
    s = re.sub(r'\s+', ' ', line.strip().lower())
    # Merge "logp ow" / "log p ow" / "logp\now" → "logpow"
    s = re.sub(r'log\s*p\s*\n?\s*ow\b', 'logpow', s)
    s = re.sub(r'log\s*p\s*ow', 'logpow', s)
    # Airgas Section 12 table header variant: "LogPow BCF Potential" without product col
    s = re.sub(r'^logpow\s+bcf\s+potential$', 'logpow bcf potential', s)
    # Slash variants in header lines
    s = re.sub(r'product/ingredient', 'product/ingredient', s)
    return s


def _detect_table_schema(line: str):
    return _TABLE_SCHEMAS.get(_normalise_header(line))


def _split_two_col_row(line: str, right_hints=None):
    s = line.strip()
    if right_hints:
        for hint in sorted(right_hints, key=len, reverse=True):
            if s.lower().endswith(hint.lower()):
                left = s[: len(s) - len(hint)].strip()
                if left:
                    return left, hint
    m = re.search(r'  +', s)
    if m:
        return s[: m.start()].strip(), s[m.end():].strip()
    return s, ''


# ══════════════════════════════════════════════════════
#  PRODUCT NAME EXTRACTOR  (v1 preserved)
# ══════════════════════════════════════════════════════

PRODUCT_NAME_KEYS = [
    'Product name', 'Product Name', 'GHS product identifier',
    'Identification of the substance', 'Product identifier',
    'Trade name', 'Chemical name',
]

HEADER_NOISE_RE = re.compile(
    r'safety\s+data\s+sheet|acc\.\s+to|regulation|revision|version|'
    r'article\s+number|date\s+of|pursuant|created|CFR\s+\d|'
    r'this\s+safety|OSHA',
    re.IGNORECASE
)


def extract_product_name(sections: list, layout_lines: list[LayoutLine]) -> str:
    sec1 = next((s for s in sections if s['section_number'] == '1'), None)
    if sec1:
        for sub in sec1['subsections']:
            title   = sub['title'].strip()
            content = sub.get('content', '').strip().lstrip(': ')
            for key in PRODUCT_NAME_KEYS:
                if title.lower() == key.lower() and content:
                    return content

    # Fallback: first large bold line before Section 1
    for ll in layout_lines:
        if ll.size >= 10.0 and ll.is_bold:
            t = ll.text.strip()
            if (3 < len(t) <= 80
                    and not is_noise(t, ll)
                    and not HEADER_NOISE_RE.search(t)
                    and not parse_section_header(t, ll)
                    and re.search(r'[A-Za-z]{2,}', t)):
                return t
    return ''


# ══════════════════════════════════════════════════════
#  INCOMPLETE SENTENCE  (v1 preserved)
# ══════════════════════════════════════════════════════

def _is_incomplete(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    if re.search(r'\b(in|of|the|a|an|and|or|to|for|with|by|from|on|at)\s*$', t, re.IGNORECASE):
        return True
    if (
        len(t) < 80
        and not re.search(r'[.!?)\]]$', t)
        and not re.match(r'^[A-Z][a-z]+( [A-Z][a-z]+)*$', t)  # avoid titles
    ):
        return True
    return False


def is_continuation(text: str) -> bool:
    s = text.strip()
    if not s or is_noise(s):
        return False
    if parse_section_header(text):
        return False
    if parse_numbered_subsection(text):
        return False
    if parse_kv(text):
        return False
    if _detect_table_schema(s):
        return False
    if re.match(r'^(United Kingdom|acc\.\s+to|Version:|Replaces|article number)', s, re.IGNORECASE):
        return False
    norm = s.lower()
    for markers in _GROUP_HEADERS.values():
        for marker in markers:
            if norm == marker or norm.startswith(marker + ' ') or norm.startswith(marker + ':'):
                return False
    # Reject paragraph-body sentences — long lines ending in punctuation or
    # starting with a known paragraph-opener prefix are not value continuations.
    if _is_paragraph_key(s):
        return False
    if len(s.split()) > 12 and re.search(r'[.!?]$', s):
        return False
    return True


# ══════════════════════════════════════════════════════
#  LAYOUT-AWARE KV BUILDER
#  Converts LayoutLine list → flat line/KV stream
#  honouring column positions before falling back to regex
# ══════════════════════════════════════════════════════

def layout_lines_to_text_and_kvs(
        layout_lines: list[LayoutLine],
) -> tuple[list[tuple], list[LayoutLine]]:
    """
    Pass 1: detect column geometry.
    Pass 2: for each line, try column-based KV extraction first.

    Returns:
        structured_lines: list of ('kv', key, val, ll) | ('text', text, ll)
        clean_lines:      LayoutLine list with noise removed
    """
    # Filter noise
    clean = [ll for ll in layout_lines
             if not is_noise(ll.text, ll) and ll.text.strip()]

    label_max_x, value_min_x = _detect_column_layout(clean)

    structured: list[tuple] = []
    prev_label: Optional[str]  = None
    prev_val_parts: list[str]  = []

    def flush_prev():
        nonlocal prev_label, prev_val_parts
        if prev_label is not None:
            val = ' '.join(prev_val_parts).strip()
            structured.append(('kv', prev_label, val, None))
            prev_label    = None
            prev_val_parts = []

    for ll in clean:
        # ── Section header (size ≥ 12 and bold) ──────────────────
        sec = parse_section_header(ll.text, ll)
        if sec:
            flush_prev()
            structured.append(('section', sec[0], sec[1], ll))
            continue

        # ── Column-based KV (Airgas / Fisher layout) ─────────────
        col_kv = _extract_kv_from_columns(ll, label_max_x, value_min_x)
        if col_kv and col_kv[0].strip():
            label, val = col_kv
            label = label.rstrip(':').strip()
            val   = val.lstrip(': ').strip()
            # Reject: if the 'label' is actually a sentence or paragraph body
            if _is_paragraph_key(label):
                full = (label + ' ' + val).strip()
                structured.append(('text', full, ll))
                continue
            # Reject purely numeric / symbolic keys (HMIS ratings, etc.)
            if not re.search(r'[A-Za-z]', label):
                full = (label + ' ' + val).strip()
                structured.append(('text', full, ll))
                continue
            # Reject labels where the last word is a standalone number
            # e.g. "Health 0", "Physical hazards 3" from HMIS/NFPA rating bleed-in
            _lbl_words = label.split()
            if _lbl_words and re.fullmatch(r'\d+', _lbl_words[-1]):
                full = (label + ' ' + val).strip()
                structured.append(('text', full, ll))
                continue
            flush_prev()
            structured.append(('kv', label, val, ll))
            continue

        # ── Bold-only line (label without inline value) ───────────
        if ll.is_field_label() and ll.x0 < label_max_x:
            text = ll.text.strip()
            # Reject sentences, paragraphs, and other non-label text
            if _is_paragraph_key(text):
                structured.append(('text', text, ll))
                continue
            # Reject purely numeric / symbolic text (HMIS ratings, page numbers)
            if not re.search(r'[A-Za-z]', text):
                structured.append(('text', text, ll))
                continue
            # Reject lowercase-start lines
            if text and text[0].islower():
                structured.append(('text', text, ll))
                continue
            flush_prev()
            label = text.rstrip(':').strip()
            prev_label     = label
            prev_val_parts = []
            continue

        # ── Value continuation for pending label ──────────────────
        if prev_label is not None:
            if ll.x0 >= value_min_x - 10 and not ll.is_bold:
                prev_val_parts.append(ll.text.strip())
                continue
            else:
                flush_prev()

        # ── Regex fallback ────────────────────────────────────────
        kv = parse_kv(ll.text, ll)
        if kv:
            structured.append(('kv', kv[0], kv[1], ll))
            continue

        # ── Plain content ─────────────────────────────────────────
        structured.append(('text', ll.text.strip(), ll))

    flush_prev()
    return structured, clean


# ══════════════════════════════════════════════════════
#  LIST ITEM EXTRACTOR  — preserves bullet/semicolon lists
# ══════════════════════════════════════════════════════

def _extract_list_items(text: str) -> list[str]:
    """
    Given a content string that may contain a semicolon-separated or
    period-separated list (e.g. incompatible materials, synonyms),
    return a clean list of items.  Returns [] if it doesn't look like a list.
    """
    if not text or len(text) < 4:
        return []
    # Semicolon-separated list
    if ';' in text:
        parts = [p.strip().rstrip('.') for p in text.split(';') if p.strip()]
        if len(parts) >= 2:
            return parts
    # Newline-separated
    if '\n' in text:
        parts = [p.strip().rstrip('.') for p in text.split('\n') if p.strip()]
        if len(parts) >= 2:
            return parts
    # Short items separated by periods (not sentences): e.g. "grease. oil. reducing materials."
    # Only apply when all items are short (≤ 5 words)
    period_parts = [p.strip() for p in re.split(r'\.\s+', text) if p.strip()]
    if (len(period_parts) >= 2
            and all(len(p.split()) <= 5 for p in period_parts)):
        return period_parts
    return []


# ══════════════════════════════════════════════════════
#  MAIN EXTRACTOR  (rebuilt on top of structured_lines)
# ══════════════════════════════════════════════════════

def extract(layout_lines: list[LayoutLine], pdf_tables: list = None) -> list:
    """
    Convert a list of LayoutLine objects into a structured SDS section list.
    """
    # Build pdfplumber lattice-table lookup
    _ptbl_lookup = {}
    _ptbl_headers_lookup = {}
    for tbl in (pdf_tables or []):
        key = _normalise_header(' '.join(tbl['headers']))
        _ptbl_lookup[key] = tbl['rows']
        _ptbl_headers_lookup[key] = tbl['headers']

    structured, _ = layout_lines_to_text_and_kvs(layout_lines)

    sections: list[dict] = []
    current_section: Optional[dict] = None
    current_sub:     Optional[dict] = None
    current_group:   Optional[str]  = None
    _seen_counts:    dict           = {}

    _flush_sfx_lower = {s.lower() for s in _LABEL_SUFFIXES}

    def flush_sub():
        nonlocal current_sub
        if current_section is None or current_sub is None:
            current_sub = None
            return
        t = current_sub['title'].strip()
        c = current_sub.get('content', '').strip()
        if not t:
            current_sub = None
            return

        c = clean_content(c)
        c = deduplicate_sentences(c)

        # ── Title fragment merger ──────────────────────────────────────
        # If this title is a known label-suffix word (e.g. "range", "media",
        # "identification") or a tiny lowercase continuation, merge it back
        # into the previous subsection instead of creating a spurious node.
        if current_section['subsections'] and 'table' not in current_sub:
            prev = current_section['subsections'][-1]
            t_lower = t.lower()
            is_known_suffix = t_lower in _flush_sfx_lower
            is_tiny_cont = (
                len(t.split()) <= 4
                and len(t) <= 30
                and len(t) >= 3          # skip 1-2 char abbreviations like 'pH'
                and not re.search(r'[.!?]$', t)
                and t[0].islower()
                and not re.search(r'\b(materials|material|agents|grease|oil)\b', t, re.I)
            )
            if is_known_suffix or is_tiny_cont:
                prev['title'] = prev['title'].rstrip() + ' ' + t
                prev['normalised_key'] = normalise_key(prev['title'])
                if c:
                    pc = prev.get('content', '')
                    prev['content'] = (pc + (' ' if pc else '') + c).strip()
                current_sub = None
                return

        # ── Conclusion/Summary suppression ────────────────────────────
        # Fold repeated "Conclusion/Summary [Product]" nodes into the
        # previous subsection's content to avoid flat repetition.
        if re.match(r'^Conclusion/Summary\b', t, re.IGNORECASE):
            if current_section['subsections']:
                prev = current_section['subsections'][-1]
                if c:
                    pc = prev.get('content', '')
                    prev['content'] = (pc + (' ' if pc else '') + c).strip()
                current_sub = None
                return

        entry: dict = {
            'title':          t,
            'normalised_key': normalise_key(t),
            'content':        c,
        }

        # ── List structure preservation ───────────────────────────────
        # If the content contains multiple items separated by semicolons,
        # newlines, or the pattern "item. item." preserve them as a list.
        _list_items = _extract_list_items(c)
        if _list_items and len(_list_items) > 1:
            entry['list_items'] = _list_items

        sec_num = current_section['section_number']
        ctx = _resolve_context(sec_num, t, _seen_counts)
        if ctx:
            entry['context'] = ctx
        if current_group:
            entry['group'] = current_group

        props = split_mixed_properties(c)
        if props:
            entry['properties'] = props

        # spaCy entity extraction on content
        entities = extract_entities(c)
        if entities:
            entry['entities'] = entities

        if 'table' in current_sub:
            entry['table'] = current_sub['table']

        current_section['subsections'].append(entry)
        current_sub = None

    # ── Process structured stream ───────────────────────────────────
    idx = 0
    items = structured   # list of ('type', ..., ll)


    while idx < len(items):
        item = items[idx]
        kind = item[0]
        idx += 1
        if current_section is not None and len(item) > 3:
            ll = item[-1]
            if hasattr(ll, "page_no"):
                current_section['page_range'][1] = ll.page_no

        # ── Section ───────────────────────────────────────────────
        if kind == 'section':
            _, num, title, ll = item
            current_sec_int = int(current_section['section_number']) if current_section else 0
            if int(num) <= current_sec_int:
                # Duplicate or backwards reference — treat title as content
                if int(num) < current_sec_int and current_sub is not None:
                    sep = ' ' if current_sub['content'] else ''
                    current_sub['content'] += sep + title
                # Equal (duplicate header on a new page) — just skip, keep current section
                continue

            # Absorb lowercase continuation lines into title
            while idx < len(items):
                nxt = items[idx]
                if nxt[0] == 'text':
                    nxt_text = nxt[1]
                    if re.match(r'^[a-z(]', nxt_text) and len(title + ' ' + nxt_text) <= _MAX_TITLE_LEN:
                        title += ' ' + nxt_text
                        idx += 1
                    else:
                        break
                else:
                    break

            if len(title) > _MAX_TITLE_LEN or not re.search(r'[A-Za-z]{3,}', title):
                title = _SDS_SECTION_TITLES.get(num, title)

            flush_sub()
            current_group = None
            _seen_counts  = {}
            current_section = {
                'section_number': num,
                'section_title':  title,
                'subsections':    [],
                'page_range': [ll.page_no, ll.page_no]
            }
            sections.append(current_section)
            continue

        if current_section is None:
            continue

        sec_num = current_section['section_number']

        # ── KV ────────────────────────────────────────────────────
        if kind == 'kv':
            _, key, val, ll = item

            # ── Table-header interceptor ──────────────────────────
            # The column-based KV splitter can extract e.g.
            #   key="Ingredient name"  val="% CAS number"
            # which is actually the header row of a table schema.
            # Detect this before treating it as a KV pair and
            # re-route to the table-schema handler (same logic as
            # the 'text' branch below).
            _combined = (key + ' ' + val).strip()
            _kv_schema = _detect_table_schema(_combined)
            if not _kv_schema:
                # Also check pdfplumber dynamic schemas
                _dyn_key = _normalise_header(_combined)
                if _dyn_key in _ptbl_lookup:
                    _kv_schema = {'headers': _ptbl_headers_lookup[_dyn_key], 'right_hints': None}
            if _kv_schema:
                headers  = _kv_schema['headers']
                r_hints  = _kv_schema.get('right_hints')
                ptbl_key  = _normalise_header(' '.join(headers))
                ptbl_rows = _ptbl_lookup.get(ptbl_key)

                if ptbl_rows:
                    table_rows = ptbl_rows
                    # Skip over any flat-text duplicate rows
                    _skipped = 0
                    _max_skip = max(len(ptbl_rows) * 3, 3)
                    while idx < len(items) and _skipped < _max_skip:
                        nxt = items[idx]
                        if nxt[0] in ('kv', 'text') and (nxt[1] if nxt[0] == 'text' else (nxt[1]+' '+nxt[2])).strip():
                            nxt_text = nxt[1] if nxt[0] == 'text' else (nxt[1]+' '+nxt[2])
                            if (parse_section_header(nxt_text)
                                    or _detect_table_schema(nxt_text.strip())
                                    or _normalise_header(nxt_text.strip()) in _ptbl_lookup):
                                break
                        idx += 1
                        _skipped += 1
                else:
                    table_rows = []
                    while idx < len(items):
                        nxt = items[idx]
                        if nxt[0] not in ('text', 'kv'):
                            break
                        row = (nxt[1] if nxt[0] == 'text' else nxt[1] + '  ' + nxt[2]).strip()
                        if not row:
                            idx += 1
                            continue
                        if parse_section_header(row) or _detect_table_schema(row):
                            break
                        if len(headers) == 3:
                            parts = re.split(r'  +', row)
                            # If reconstruction only gave 2 parts for 3 columns,
                            # further split the last part on the first whitespace
                            # (e.g. "100 7782-44-7" → ["100", "7782-44-7"])
                            if len(parts) == 2:
                                sub = parts[1].split(None, 1)
                                parts = [parts[0]] + sub
                            parts += [''] * (3 - len(parts))
                            table_rows.append(dict(zip(headers, parts[:3])))
                        elif len(headers) == 2:
                            left, right = _split_two_col_row(row, r_hints)
                            table_rows.append({headers[0]: left, headers[1]: right})
                        else:
                            parts = re.split(r'  +', row)
                            parts += [''] * (len(headers) - len(parts))
                            table_rows.append(dict(zip(headers, parts[:len(headers)])))
                        idx += 1

                tbl = {'headers': headers, 'rows': table_rows}
                # Always flush any pending subsection (e.g. "Product code") before
                # creating the table node — prevents the table from being stapled
                # onto the wrong preceding KV entry.
                flush_sub()
                current_sub = {'title': _combined, 'content': '', 'table': tbl}
                continue

            # Reject sentence / paragraph keys — treat as plain content
            if _is_paragraph_key(key):
                full_text = (key + ' ' + val).strip()
                if current_sub is not None:
                    sep = ' ' if current_sub['content'] else ''
                    current_sub['content'] += sep + full_text
                # else: silently discard orphaned paragraph (no current subsection)
                continue

            # Absorb continuation text lines into value
            while idx < len(items):
                nxt = items[idx]
                if nxt[0] == 'text' and is_continuation(nxt[1]):
                    sfx, remainder = _strip_label_suffix(nxt[1])
                    if sfx:
                        key = key + ' ' + sfx
                        if remainder:
                            val = val.rstrip() + ' ' + remainder
                        idx += 1
                        continue
                    if _is_incomplete(val):
                        val = val.rstrip() + ' ' + nxt[1]
                        idx += 1
                        continue
                    val = val.rstrip() + ' ' + nxt[1]
                    idx += 1
                else:
                    break

            # Check group-header
            norm_key = key.lower()
            group_markers = _GROUP_HEADERS.get(sec_num, [])
            is_group = any(
                norm_key == m or norm_key.startswith(m + ' ') or norm_key.startswith(m + ':')
                for m in group_markers
            )
            flush_sub()
            if is_group:
                current_group = key
            current_sub = {'title': key, 'content': val.strip()}
            continue

        # ── Text (plain content) ──────────────────────────────────
        if kind == 'text':
            _, text, ll = item  # unpack FIRST so ll is correct for this item
            if is_inside_table(ll, pdf_tables):
                if not parse_section_header(ll.text, ll):
                    continue
            stripped = text.strip()

            # Check for group-header text lines
            norm_stripped = stripped.lower()
            group_markers = _GROUP_HEADERS.get(sec_num, [])
            is_group = any(
                norm_stripped == m or norm_stripped.startswith(m + ' ') or norm_stripped.startswith(m + ':')
                for m in group_markers
            )
            if is_group:
                flush_sub()
                current_group = stripped
                clean_title = dedup_words(stripped)
                current_sub = {'title': clean_title, 'content': ''}
                continue

            # Numbered subsection group
            nsub = parse_numbered_subsection(stripped)
            if nsub:
                flush_sub()
                sub_id, sub_title = nsub
                current_group = f'{sub_id} {sub_title}'
                current_section['subsections'].append({
                    'title':           current_group,
                    'normalised_key':  normalise_key(sub_title),
                    'content':         '',
                    'is_group_header': True,
                })
                continue

            # Table schema detection
            schema = _detect_table_schema(stripped)
            # 🔧 Fallback for transport tables (Section 14 type)
            if not schema:
                s_lower = stripped.lower()
                if "un number" in s_lower and "shipping" in s_lower:
                    schema = {
                        'headers': [
                            'UN number',
                            'UN proper shipping name',
                            'Transport hazard class'
                        ],
                        'right_hints': None
                    }
            if not schema:
                _dyn_key = _normalise_header(stripped)
                if _dyn_key in _ptbl_lookup:
                    schema = {'headers': _ptbl_headers_lookup[_dyn_key], 'right_hints': None}

            if schema:
                headers = schema['headers']
                r_hints = schema.get('right_hints')
                ptbl_key  = _normalise_header(' '.join(headers))
                ptbl_rows = _ptbl_lookup.get(ptbl_key)

                if ptbl_rows:
                    table_rows = ptbl_rows
                    # Skip over flat-text representation
                    _skipped = 0
                    _max_skip = max(len(ptbl_rows) * 3, 3)
                    while idx < len(items) and _skipped < _max_skip:
                        nxt = items[idx]
                        if nxt[0] == 'text' and nxt[1].strip():
                            if (parse_section_header(nxt[1])
                                    or parse_kv(nxt[1])
                                    or _detect_table_schema(nxt[1].strip())
                                    or _normalise_header(nxt[1].strip()) in _ptbl_lookup):
                                break
                        idx += 1
                        _skipped += 1
                else:
                    table_rows = []
                    while idx < len(items):
                        nxt = items[idx]
                        if nxt[0] != 'text':
                            break
                        row = nxt[1].strip()
                        if not row:
                            idx += 1
                            continue
                        if parse_section_header(row) or parse_kv(row) or _detect_table_schema(row):
                            break
                        if len(headers) == 2:
                            left, right = _split_two_col_row(row, r_hints)
                            table_rows.append({headers[0]: left, headers[1]: right})
                        elif len(headers) == 3:
                            parts = re.split(r'  +', row)
                            parts += [''] * (3 - len(parts))
                            table_rows.append(dict(zip(headers, parts[:3])))
                        else:
                            parts = re.split(r'  +', row)
                            parts += [''] * (len(headers) - len(parts))
                            table_rows.append(dict(zip(headers, parts[:len(headers)])))
                        idx += 1

                tbl = {'headers': headers, 'rows': table_rows}
                if current_sub is not None:
                    if 'table' in current_sub:
                        flush_sub()
                        current_sub = {'title': stripped, 'content': '', 'table': tbl}
                    else:
                        current_sub['table'] = tbl
                else:
                    flush_sub()
                    current_sub = {'title': stripped, 'content': '', 'table': tbl}
                continue

            # Plain content
            if current_sub is not None:
                sep = ' ' if current_sub['content'] else ''
                current_sub['content'] += sep + stripped
            else:
                # ❌ Reject sentences as titles — drop silently (no sub to append to)
                if re.search(r'[.!?]$', stripped):
                    continue

                # ❌ Reject long lines (likely paragraph text) — drop silently
                if len(stripped.split()) > 10:
                    continue

                # ❌ Reject lowercase-start lines — drop silently
                if stripped and stripped[0].islower():
                    continue

                clean_title = dedup_words(stripped)
                current_sub = {'title': clean_title, 'content': ''}

            continue  # keep processing remaining items

    # Flush any pending subsection after the loop ends
    flush_sub()
    return sections


# ══════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════

FILES = {
    'o2':  'uploads/o2.pdf',
}

if __name__ == '__main__':
    print('✦  Script version: 2025-v2 (17-issues-fixed)')
    all_output = {}

    for name, path in FILES.items():
        pdf_path = Path(path)
        if not pdf_path.exists():
            print(f'⚠  Skipping {name}: {path} not found')
            continue

        print(f'→  Processing {name} …')
        layout_lines = extract_layout_lines(str(pdf_path))

        # Debug: show which lines the structured stream classifies as section events
        structured_debug, _ = layout_lines_to_text_and_kvs(layout_lines)
        sec_events = [item for item in structured_debug if item[0] == 'section']
        print(f'   Structured-stream section events ({len(sec_events)}):')
        for item in sec_events:
            print(f'     § {item[1]}: {item[2]}')
        pdf_tables_plumber = extract_pdf_tables(str(pdf_path))
        pdf_tables_camel   = extract_tables_camelot(str(pdf_path))
        pdf_tables = pdf_tables_camel + pdf_tables_plumber

        # ❗ IMPORTANT: do NOT pass tables into extract
        sections = extract(layout_lines, pdf_tables=pdf_tables)

        # ✅ ADD THIS LINE RIGHT HERE
        assign_tables_to_sections(sections, pdf_tables)
        product_name = extract_product_name(sections, layout_lines)

        all_output[name] = {
            'product_name': product_name,
            'sections':     sections,
        }
        sec_nums = [s['section_number'] for s in sections]
        print(f'✓  {name}  |  product: "{product_name}"  |  sections: {sec_nums}')

    # ── Save JSON ──────────────────────────────────────────────────────
    out_dir = Path('outputjson')
    out_dir.mkdir(parents=True, exist_ok=True)

    for name, data in all_output.items():
        json_path = out_dir / f'{name}_new_camelot.json'
        json_path.write_text(
            json.dumps({name: data}, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
        print(f'✓  Saved JSON  → {json_path}')

    # ── Build HTML preview ─────────────────────────────────────────────
    def _esc(s: str) -> str:
        return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    def _render_content(sub: dict) -> str:
        parts = []
        if sub.get('content'):
            parts.append(f'<p style="margin:0 0 4px">{_esc(sub["content"])}</p>')
        if sub.get('properties'):
            rows = ''.join(
                f'<tr><td>{_esc(p["key"])}</td><td>{_esc(p["value"])}</td></tr>'
                for p in sub['properties']
            )
            parts.append(f'<table class="inner"><tbody>{rows}</tbody></table>')
        if sub.get('entities'):
            badges = ''.join(
                f'<span class="badge {_esc(e["label"].lower())}">{_esc(e["text"])} '
                f'<em>{_esc(e["label"])}</em></span> '
                for e in sub['entities']
            )
            parts.append(f'<div class="entities">{badges}</div>')
        if sub.get('table'):
            tbl = sub['table']
            ths = ''.join(f'<th>{_esc(h)}</th>' for h in tbl['headers'])
            trs = ''.join(
                '<tr>' + ''.join(
                    f'<td>{_esc(row.get(h, ""))}</td>' for h in tbl['headers']
                ) + '</tr>'
                for row in tbl['rows']
            )
            parts.append(
                f'<table class="inner">'
                f'<thead><tr>{ths}</tr></thead>'
                f'<tbody>{trs}</tbody></table>'
            )
        return ''.join(parts) or ''

    for name, data in all_output.items():
        table_rows_html = ''
        for sec in data.get('sections', []):
            sec_label = f'§{sec["section_number"]} {_esc(sec["section_title"])}'
            subs = sec.get('subsections', [])
            span = max(len(subs), 1)
            for idx, sub in enumerate(subs):
                ctx_grp = _esc(sub.get('context') or sub.get('group', ''))
                sec_td  = f'<td class="sec" rowspan="{span}">{sec_label}</td>' if idx == 0 else ''
                table_rows_html += (
                    f'<tr>{sec_td}'
                    f'<td>{_esc(sub["title"])}</td>'
                    f'<td>{ctx_grp}</td>'
                    f'<td>{_render_content(sub)}</td>'
                    f'</tr>\n'
                )

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>SDS Extracted Data – {_esc(name)}</title>
  <style>
    body  {{ font-family: Arial, sans-serif; font-size: 13px; margin: 24px; color: #222; }}
    h2    {{ margin-bottom: 10px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #bbb; padding: 6px 10px; vertical-align: top; text-align: left; }}
    th {{ background: #e8e8e8; font-weight: bold; }}
    td.sec {{ background: #f5f5f5; font-weight: bold; white-space: nowrap; min-width: 180px; }}
    table.inner {{ border-collapse: collapse; width: 100%; margin: 4px 0 0; }}
    table.inner th, table.inner td {{ border: 1px solid #ccc; padding: 3px 7px; font-size: 12px; }}
    table.inner th {{ background: #dde; }}
    tr:hover > td {{ background-color: #fffbe6; }}
    .entities {{ margin-top: 4px; }}
    .badge {{ display: inline-block; background: #e0eaf8; border-radius: 4px;
              padding: 1px 5px; margin: 2px 2px 0 0; font-size: 11px; }}
    .badge em {{ font-style: normal; color: #556; font-size: 10px; margin-left: 4px; }}
    .badge.cas_number {{ background: #d4edda; }}
    .badge.ghs_h_code  {{ background: #f8d7da; }}
    .badge.ghs_p_code  {{ background: #fff3cd; }}
    .badge.un_number   {{ background: #d1ecf1; }}
    .badge.temperature {{ background: #fde; }}
    .badge.percentage  {{ background: #ede; }}
  </style>
</head>
<body>
  <h2>SDS Extracted Data – {_esc(data.get("product_name", name))}</h2>
  <table>
    <thead>
      <tr>
        <th>Section</th><th>Field / Subsection</th>
        <th>Group / Context</th><th>Content + Entities</th>
      </tr>
    </thead>
    <tbody>
{table_rows_html}    </tbody>
  </table>
</body>
</html>"""

        html_path = out_dir / f'sds_{name}_new_camelot.html'
        html_path.write_text(html, encoding='utf-8')
        print(f'✓  Saved HTML  → {html_path}')