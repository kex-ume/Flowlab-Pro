"""Parse OCR output of an incoming waybill into structured equipment items.

Each item maps to a :class:`core.models.WaybillItem` column:
``equipment_description``, ``quantity``, ``serial_no``, ``model_no``,
``manufacturer``, ``range_field``.

Strategy (robust to both column-tables and labelled-field layouts):

1. Column/table parse (primary): detect column header lines by keyword, cluster
   body lines into rows by vertical position, and assign every token to the
   nearest header column by horizontal position. A row becomes an item when it
   yields a serial number.
2. Label-value fallback: lines shaped like ``"Serial No: ABC123"`` (keyword +
   colon/separator + value) are parsed for any field.
3. Serial-regex fallback: any token matching a serial-number pattern is treated
   as an item, with the nearest preceding description token.
"""

import re

KEYWORDS = {
    'desc': ['equipment description', 'description', 'equipment', 'instrument', 'item', 'part'],
    'serial': ['serial no', 'serialno', 'serial', "s/n", 'sr no', 'sn', 's.n.'],
    'model': ['model no', 'model no.', 'model'],
    'manufacturer': ['manufacturer', 'mfr', 'make'],
    'range': ['range', 'span', 'measurement range'],
}

SERIAL_RE = re.compile(r'^[A-Z0-9][A-Z0-9\-/.]{3,}[A-Z0-9]$')
ROW_NUM_RE = re.compile(r'^\d{1,4}$')


def _norm(t):
    return re.sub(r'\s+', ' ', (t or '').strip())


def _kw_category(text):
    low = _norm(text).lower()
    for cat, kws in KEYWORDS.items():
        for kw in kws:
            if kw in low:
                return cat
    return None


def _avg_x(bbox):
    if not bbox or len(bbox) < 4:
        return None
    return sum(p[0] for p in bbox[:4]) / 4.0


def _top_y(bbox):
    if not bbox or len(bbox) < 4:
        return None
    return min(p[1] for p in bbox[:4])


def _prep(line):
    txt = _norm(line.get('text', ''))
    conf = float(line.get('confidence', 1.0))
    bbox = line.get('bbox')
    return {
        'text': txt,
        'confidence': conf,
        'bbox': bbox,
        'x': _avg_x(bbox),
        'y': _top_y(bbox),
    }


def _join(parts):
    return ' '.join(_norm(p) for p in parts if p and _norm(p)).strip()


def _cluster_rows(lines):
    """Group bbox'd lines into rows using an adaptive vertical gap threshold."""
    pts = [l for l in lines if l['y'] is not None]
    if not pts:
        return []
    pts = sorted(pts, key=lambda x: x['y'])
    ys = [p['y'] for p in pts]
    diffs = [ys[i + 1] - ys[i] for i in range(len(ys) - 1) if ys[i + 1] - ys[i] > 2]
    if diffs:
        median_gap = sorted(diffs)[len(diffs) // 2]
        tol = min(40, max(12, median_gap * 0.6))
    else:
        tol = 20

    rows, current, base_y = [], [], None
    for l in pts:
        y = l['y']
        if base_y is None or abs(y - base_y) <= tol:
            current.append(l)
            if base_y is None:
                base_y = y
        else:
            if current:
                rows.append(current)
            current, base_y = [l], y
    if current:
        rows.append(current)
    return rows


def _is_header_line(l, header_rows):
    if l['y'] is None:
        return False
    for ry in header_rows:
        if abs(l['y'] - ry) <= 40:
            return True
    return False


def _column_parse(lines):
    header_lines = [l for l in lines if _kw_category(l['text'])]
    if not header_lines:
        return []

    # build header bands by y, pick the band with most distinct categories
    bands, header_rows = [], []
    for hl in sorted(header_lines, key=lambda x: x['y'] or 0):
        placed = False
        for b in bands:
            if abs(b[0]['y'] - hl['y']) <= 40:
                b.append(hl); placed = True; break
        if not placed:
            bands.append([hl])
    band = max(bands, key=len)
    header_rows = [b['y'] for b in band]

    # column centroids: category -> x-centers (leftmost token per category)
    cat_x = {}
    centroids = []  # (x, category-or-None)
    for b in sorted(band, key=lambda x: x['x'] or 0):
        cat = _kw_category(b['text'])
        centroids.append((b['x'], cat))
        if cat:
            cat_x.setdefault(cat, []).append(b['x'])
    cat_center = {c: sum(xs) / len(xs) for c, xs in cat_x.items()}

    body = [l for l in lines if not _is_header_line(l, header_rows)]
    rows = _cluster_rows(body)

    items = []
    for row in rows:
        cell = {}
        for l in row:
            if l['x'] is None:
                continue
            # skip table row-number tokens (e.g. "1", "12") — not equipment text
            if re.fullmatch(r'\d{1,4}', l['text']):
                continue
            best = min(centroids, key=lambda c: abs((c[0] or 0) - l['x']))
            cat = best[1]
            if cat:
                cell.setdefault(cat, []).append(l['text'])
        if 'serial' not in cell:
            continue
        serials = cell.get('serial', [])
        serial = sorted(serials, key=len, reverse=True)[0]
        items.append({
            'equipment_description': _join(cell.get('desc', [])),
            'quantity': 1,
            'serial_no': _norm(serial),
            'model_no': _join(cell.get('model', [])),
            'manufacturer': _join(cell.get('manufacturer', [])),
            'range_field': _join(cell.get('range', [])),
        })
    return items


def _label_value_parse(lines):
    """Handle ``"Serial No: ABC123"`` style single lines."""
    found = {}
    for l in lines:
        txt = l['text']
        cat = _kw_category(txt)
        if not cat:
            continue
        val = txt
        for kw in KEYWORDS[cat]:
            pattern = re.escape(kw)
            m = re.search(pattern + r'\s*[:#]?\s*(.+)', val, re.IGNORECASE)
            if m:
                val = m.group(1)
                break
        val = _norm(val)
        if val and val.lower() not in KEYWORDS[cat]:
            found[cat] = val
    if not found:
        return None
    # find a description token if present
    desc = found.get('desc') or ''
    return {
        'equipment_description': desc,
        'quantity': 1,
        'serial_no': found.get('serial', ''),
        'model_no': found.get('model', ''),
        'manufacturer': found.get('manufacturer', ''),
        'range_field': found.get('range', ''),
    }


def _serial_regex_parse(lines):
    """Last resort: any token that looks like a serial number becomes an item."""
    items, last_desc = [], ''
    for l in lines:
        txt = l['text']
        if _kw_category(txt) is None and not ROW_NUM_RE.match(txt):
            last_desc = txt
        if SERIAL_RE.match(txt):
            items.append({
                'equipment_description': last_desc,
                'quantity': 1,
                'serial_no': txt,
                'model_no': '',
                'manufacturer': '',
                'range_field': '',
            })
    return items


def _token_parse(lines):
    """Token-stream parse for text-only OCR (no bounding boxes).

    Walks the text in reading order; the token preceding a detected serial is
    treated as the description, and up to three following tokens (until the
    next serial / row number / header keyword) become model, manufacturer and
    range in order.
    """
    toks = [l['text'] for l in lines if l['text']]
    items, last_desc = [], ''
    i, n = 0, len(toks)
    while i < n:
        tok = toks[i]
        if ROW_NUM_RE.match(tok) or _kw_category(tok):
            i += 1
            continue
        is_serial = bool(SERIAL_RE.match(tok))
        if is_serial:
            grabbed = []
            j = i + 1
            while j < n and len(grabbed) < 3:
                nxt = toks[j]
                if ROW_NUM_RE.match(nxt) or _kw_category(nxt):
                    break
                grabbed.append(nxt)
                j += 1
            items.append({
                'equipment_description': last_desc,
                'quantity': 1,
                'serial_no': tok,
                'model_no': grabbed[0] if len(grabbed) >= 1 else '',
                'manufacturer': grabbed[1] if len(grabbed) >= 2 else '',
                'range_field': grabbed[2] if len(grabbed) >= 3 else '',
            })
            last_desc = ''
            i = j
        else:
            last_desc = tok
            i += 1
    return items


def parse_waybill_items(result, min_conf=0.5):
    """Parse an OCR result dict (from :mod:`core.ocr_engine`) into items."""
    raw = result.get('lines') or []
    lines = [_prep(l) for l in raw if l.get('text')]
    lines = [l for l in lines if l['confidence'] >= min_conf]

    items = _column_parse([l for l in lines if l['x'] is not None and l['y'] is not None])
    if items:
        return items
    items = _token_parse(lines)
    if items:
        return items
    if len(lines) >= 1:
        lv = _label_value_parse(lines)
        if lv and lv.get('serial_no'):
            return [lv]
        sr = _serial_regex_parse(lines)
        if sr:
            return sr
    return []


def parse_waybill_text(text, min_conf=0.5):
    """Parse plain OCR *text* (e.g. from a browser-side tesseract.js run) into
    items. Useful when the OCR itself is done client-side (PythonAnywhere free
    tier, which has no server-side OCR) but parsing stays server-side."""
    lines = []
    for ln in (text or '').splitlines():
        norm = _norm(ln)
        if norm:
            lines.append({'text': norm, 'confidence': 1.0, 'bbox': None})
    return parse_waybill_items({'lines': lines}, min_conf)



def build_line_summary(result):
    """Human-readable text of all detected lines (for UI debug panel)."""
    return '\n'.join(
        f"{float(l.get('confidence', 0)):.0%}\t{l.get('text', '')}"
        for l in (result.get('lines') or [])
    )
