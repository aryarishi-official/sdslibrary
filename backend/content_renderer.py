def render_subsection_html(subsection: dict) -> str:
    """
    Convert a parsed subsection dict (with optional 'table' and 'list_items')
    into an HTML string for storage.
    """
    parts = []

    content = subsection.get("content", "")
    table = subsection.get("table")
    list_items = subsection.get("list_items")

    # Plain text content (skip if the table will cover it)
    if content and not table:
        parts.append(f"<p>{_escape(content)}</p>")

    # Render list_items as <ul> if no table
    if list_items and not table:
        items_html = "".join(f"<li>{_escape(i)}</li>" for i in list_items)
        parts.append(f"<ul>{items_html}</ul>")

    # Render table
    if table:
        headers = table.get("headers", [])
        rows = table.get("rows", [])
        parts.append(_render_table(headers, rows))

    return "\n".join(parts) if parts else f"<p>{_escape(content)}</p>"


def _render_table(headers: list, rows: list) -> str:
    thead_cells = "".join(f"<th>{_escape(str(h))}</th>" for h in headers)
    
    # Detect if rows have a leading "" key (row-header tables like section 14)
    has_row_header = rows and "" in rows[0]
    all_keys = [""] + headers if has_row_header else headers

    tbody_rows = ""
    for row in rows:
        cells = ""
        for key in all_keys:
            val = _escape(str(row.get(key, "")).replace("\n", "<br>"))
            tag = "th" if key == "" else "td"
            cells += f"<{tag}>{val}</{tag}>"
        tbody_rows += f"<tr>{cells}</tr>"

    # Build header row: add leading empty <th> if table has row headers
    header_prefix = "<th></th>" if has_row_header else ""
    thead = f"<thead><tr>{header_prefix}{thead_cells}</tr></thead>"
    tbody = f"<tbody>{tbody_rows}</tbody>"

    return f'<table class="sds-table">{thead}{tbody}</table>'


def _escape(text: str) -> str:
    return (text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;"))