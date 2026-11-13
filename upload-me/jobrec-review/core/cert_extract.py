"""Deterministic extraction of calibration-certificate details.

No AI, no LLM, no external API. Every supported file type (PDF, Word 97–2003,
Word .docx, Excel .xls/.xlsx, CSV) is read through ONE normalized text view, and
fields are matched against the template's labels by normalized proximity —
never against the template's layout. Certificates don't share a structure;
they share labels. Values not found are left blank — nothing is ever invented.

Public API:
    extract_certificate(path, filename, template_columns, template_activities=None) -> dict
"""
from __future__ import annotations

import re
import csv
from datetime import date
from pathlib import Path

# ----------------------------------------------------------------- reading

_MIN_TEXT_CHARS = 20
_MAX_ROWS = 500


def _read_word_binary(path):
    """Extract text from a legacy .doc (OLE binary Word) straight from its bytes.

    Visible text inside a real Word document lives in the WordDocument stream,
    mostly encoded as UTF-16LE, else as an 8-bit codepage. We scan the whole
    file for runs of either encoding and join them — robust across codepages
    without OLE parsing.
    """
    data = Path(path).read_bytes()
    utf16_chunks = re.findall(rb'(?:[\x09\x0A-\x0D\x20-\xFF]\x00){6,}', data)
    utf16_text = '\n'.join(chunk.decode('utf-16-le', 'ignore') for chunk in utf16_chunks)
    ascii_chunks = b'\n'.join(re.findall(rb'[\x20-\x7E]{6,}', data)).decode('latin-1', 'ignore')
    if len(utf16_text.strip()) >= 20:
        text = _normalize_whitespace(utf16_text)
    else:
        text = _normalize_whitespace(ascii_chunks)
    return text, _tables_from_text(text), 'doc'


def _normalize_whitespace(text):
    text = (text or '').replace('\r\n', '\n').replace('\r', '\n').replace('\x00', ' ')
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def _tables_from_text(text):
    """Detect tabular data in free text (tab- or pipe-separated line groups)."""
    tables = []
    current = []
    current_width = None
    for raw in text.split('\n'):
        line = raw.strip()
        if not line:
            if len(current) >= 2:
                tables.append(current)
            current, current_width = [], None
            continue
        if '\t' in line:
            row = [cell.strip() for cell in line.split('\t')]
        elif '|' in line:
            row = [cell.strip() for cell in line.split('|')]
        else:
            if len(current) >= 2:
                tables.append(current)
            current, current_width = [], None
            continue
        non_empty = [cell for cell in row if cell]
        if len(non_empty) < 2:
            if len(current) >= 2:
                tables.append(current)
            current, current_width = [], None
            continue
        if current and len(row) != current_width:
            if len(current) >= 2:
                tables.append(current)
            current, current_width = [], None
            continue
        current.append(row)
        current_width = len(row)
    if len(current) >= 2:
        tables.append(current)
    return tables


def _read_docx(path):
    from docx import Document

    document = Document(path)
    paragraphs = [p.text for p in document.paragraphs]
    tables = [[[cell.text.strip() for cell in row.cells] for row in table.rows]
              for table in document.tables]
    text = '\n'.join(paragraphs)
    for table in tables:
        for row in table:
            text += '\n' + ' | '.join(cell for cell in row if cell)
    return _normalize_whitespace(text), tables, 'docx'


def _read_pdf(path):
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        text = '\n'.join((page.extract_text() or '') for page in pdf.pages)
        tables = []
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                tables.append([[('' if cell is None else str(cell)) for cell in row] for row in table])
    if len(text.strip()) >= _MIN_TEXT_CHARS:
        return _normalize_whitespace(text), tables, 'pdf'
    # Scanned / image-only PDFs: read with the local OCR engine when available.
    if _ocr_available():
        return _read_pdf_ocr(path)
    return _normalize_whitespace(text), tables, 'pdf-scanned-no-ocr'


def _read_pdf_ocr(path):
    import fitz  # PyMuPDF
    import tempfile

    from .ocr_engine import extract as ocr_extract

    text_parts, tables = [], []
    with fitz.open(path) as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as handle:
                temp = handle.name
            pix.save(temp)
            try:
                result = ocr_extract(temp)
            finally:
                Path(temp).unlink(missing_ok=True)
            lines = result.get('lines') or []
            if lines:
                rows = _group_ocr_lines(lines)
                page_tables = _guess_table_from_lines(rows)
                tables.extend(page_tables)
                text_parts.append('\n'.join(' | '.join(row) for row in rows))
            else:
                text_parts.append(result.get('text') or '')
    return _normalize_whitespace('\n'.join(text_parts)), tables, 'pdf-ocr'


def _read_excel(path, suffix):
    text_parts = []
    tables = []
    if suffix == '.xlsx':
        from openpyxl import load_workbook
        workbook = load_workbook(path, data_only=True, read_only=True)
        try:
            for sheet in workbook.worksheets:
                lines, table = [], []
                for row in sheet.iter_rows(values_only=True):
                    values = [_cell_text(cell) for cell in row]
                    line = ' | '.join(value for value in values if value)
                    if line:
                        lines.append(line)
                    if any(values):
                        table.append(list(values))
                if len(table) >= 2:
                    for group in _group_by_width(table):
                        if len(group) >= 2:
                            tables.append(_trim_table(group))
                if lines:
                    text_parts.append('\n'.join(lines))
        finally:
            workbook.close()
    else:
        import xlrd
        book = xlrd.open_workbook(path, on_demand=True)
        try:
            for sheet in book.sheets():
                lines, table = [], []
                for row_index in range(min(sheet.nrows, _MAX_ROWS)):
                    values = [_cell_text(sheet.cell_value(row_index, col_index))
                              for col_index in range(min(sheet.ncols, 30))]
                    line = ' | '.join(value for value in values if value)
                    if line:
                        lines.append(line)
                    if any(values):
                        table.append(list(values))
                if len(table) >= 2:
                    for group in _group_by_width(table):
                        if len(group) >= 2:
                            tables.append(_trim_table(group))
                if lines:
                    text_parts.append('\n'.join(lines))
        finally:
            book.release_resources()
    return _normalize_whitespace('\n'.join(text_parts)), tables, 'excel'


def _read_csv(path):
    with open(path, newline='', encoding='utf-8-sig', errors='ignore') as handle:
        rows = list(csv.reader(handle))
    table = [list(row) for row in rows if any(value.strip() for value in row)]
    text = '\n'.join(' | '.join(cell.strip() for cell in row) for row in table)
    return _normalize_whitespace(text), [_trim_table(table)] if len(table) >= 2 else [], 'csv'


def _cell_text(value):
    if value is None:
        return ''
    return re.sub(r'\s+', ' ', str(value)).strip()


def _trim_table(rows):
    if not rows:
        return []
    width = max(len(row) for row in rows)
    return [list(row) + [''] * (width - len(row)) for row in rows]


def _ocr_available():
    try:
        from .ocr_engine import is_available
        return is_available()
    except Exception:
        return False


def _group_ocr_lines(lines):
    """Group OCR word boxes into visual rows (top-to-bottom, left-to-right)."""
    items = []
    for line in lines:
        box = line.get('bbox')
        if not box:
            if line.get('text'):
                items.append((0, 0, str(line['text'])))
            continue
        ys = [point[1] for point in box]
        xs = [point[0] for point in box]
        items.append((min(ys), min(xs), str(line.get('text') or '')))
    items.sort(key=lambda item: (item[0], item[1]))
    rows, current, last_y = [], [], None
    for y, x, text in items:
        if last_y is None or abs(y - last_y) <= 12:
            current.append((x, text))
            last_y = y if last_y is None else (last_y + y) / 2
        else:
            rows.append([text for _, text in sorted(current, key=lambda item: item[0])])
            current, last_y = [(x, text)], y
    if current:
        rows.append([text for _, text in sorted(current, key=lambda item: item[0])])
    return rows


def _guess_table_from_lines(rows):
    """Heuristic: treat a block of similar-width rows as a table."""
    tables, block = [], []
    for row in rows:
        cells = [cell.strip() for cell in row]
        if len(cells) >= 3:
            block.append(cells)
            continue
        if len(block) >= 3:
            tables.append(block)
        block = []
    if len(block) >= 3:
        tables.append(block)
    return tables


def read_document(path, filename=''):
    suffix = Path(filename or path).suffix.lower()
    if suffix == '.pdf':
        return _read_pdf(path)
    if suffix == '.docx':
        return _read_docx(path)
    if suffix == '.doc':
        return _read_word_binary(path)
    if suffix in ('.xlsx', '.xls'):
        return _read_excel(path, suffix)
    if suffix == '.csv':
        return _read_csv(path)
    return '', [], 'unsupported'


# ------------------------------------------------------------- fields

_SYNONYMS = {
    'equipment owner': ['Equipment Owner', 'Owner', 'Customer', 'Client', 'Instrument Owner',
                        'Lab Owner', 'Laboratory Owner', 'Equipment owner'],
    'equipment description': ['Equipment Description', 'Description', 'Instrument Description',
                              'Equipment Name', 'Equipment Type', 'Instrument Type',
                              'Equipment Name', 'Equipment Details'],
    'manufacturer': ['Manufacturer', 'Make', 'Brand', 'Mfg', 'manufacturer'],
    'model number': ['Model Number', 'Model No', 'Model No.', 'Model', 'ModelNo', 'Model #'],
    'serial/tag number': ['Serial/Tag Number', 'Serial Number', 'Serial No', 'Serial No.', 'Serial',
                          'Asset Number', 'Asset No', 'Asset ID', 'S/N', 'Tag Number', 'Tag No',
                          'Serial Tag', 'serial/tag number'],
    'range/size': ['Range/Size', 'Range', 'Size', 'Capacity', 'Measuring Range', 'Range Size',
                   'Range (V)', 'Range (A)', 'Range (Hz)'],
    'env. conditions': ['Env. Conditions', 'Environmental Conditions', 'Environment', 'Room Conditions',
                        'Ambient Conditions', 'Environmental', 'Environment Conditions'],
    'tested at': ['Tested at', 'Test Site', 'Test Location', 'Location', 'Calibrated at',
                  'Calibration Location', 'Calibrated At', 'Calibrated Location'],
    'test date': ['Test Date', 'Date of Test', 'Calibration Date', 'Date of Calibration',
                  'Date of calibration', 'Test date', 'Date'],
    'tested by': ['Tested By', 'Calibrated By', 'Technician', 'Test Technician',
                  'Performed By', 'Operator', 'Tested by'],
}


def _normalize(value):
    return re.sub(r'[^a-z0-9]+', '', str(value).lower())


def _label_candidates(label):
    """Every plausible spelling of this template field (raw words)."""
    base = str(label).strip()
    candidates = {base, base.lower()}
    norm_base = _normalize(base)
    for key, synonyms in _SYNONYMS.items():
        if _normalize(key) == norm_base:
            candidates.update(synonyms)
            break
    return sorted({candidate for candidate in candidates if candidate.strip()},
                  key=len, reverse=True)


def _all_label_candidates(labels):
    phrases = set()
    for label in labels:
        phrases.update(_label_candidates(label))
    stems = set()
    for phrase in list(phrases):
        parts = phrase.strip().split()
        if len(parts) >= 2:
            stems.add(parts[0].lower())
    return list(phrases) + sorted(stems)


def _pattern_for(candidate):
    """Convert a raw label into a separator-tolerant regex (surveys: spaces,
    slashes, hyphens, parens, pipes, newlines — any non-word characters)."""
    words = [word for word in re.split(r'[^A-Za-z0-9]+', candidate) if word]
    if not words:
        return None
    return r'[\s:.\-–/=()|.,;\n]*?'.join(re.escape(word) for word in words)


def _column_candidates(column):
    """Label spellings a certificate might use for this template column —
    with or without the trailing unit in parentheses."""
    base = str(column).strip()
    candidates = {base, base.lower()}
    stripped = re.sub(r'\s*\([^)]*\)\s*', ' ', base).strip()
    if stripped:
        candidates.add(stripped)
        candidates.add(stripped.lower())
    inner = re.sub(r'\s*\(([^)]+)\)\s*', '', base).strip()
    if inner:
        candidates.add(inner)
        candidates.add(inner.lower())
    return sorted(candidates, key=len, reverse=True)


def _inline_column_value(text, column):
    for candidate in _column_candidates(column):
        value = _find_value(text, candidate)
        if value:
            return value
    return ''


_SEPARATOR = r'[\s:.\-–/=()|.,;\n]*?'


def _reflow(text):
    """Flatten line breaks into a single searchable line (label + value often wrap)."""
    return re.sub(r'[ \t]*\n[ \t]*', ' ', text)


def _find_value(text, label, all_labels=None):
    """Direct line-anchored match: find a line starting with the label, take the
    value from that line (or the next line), stopping at a pipe or newline."""
    candidates = _label_candidates(label)
    if not candidates:
        return ''
    stops = _all_label_candidates(all_labels) if all_labels else candidates
    text = text or ''
    lines = text.split('\n')

    for idx, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        for _ in range(3):
            m = re.match(r'^\s*[\|=>*▪•\-]\s*', s)
            if not m:
                break
            s = s[m.end():].strip()
        for candidate in candidates:
            candidate_upper = candidate.strip().upper()
            if s.upper().startswith(candidate_upper):
                remainder = s[len(candidate):].lstrip(' :=|-')
                if remainder.strip():
                    return _cut_value(remainder, candidates, stops)
                for j in range(idx + 1, len(lines)):
                    nxt = lines[j].strip()
                    if not nxt:
                        continue
                    nxt = re.sub(r'^\s*[\|=>*▪•\-]\s*', '', nxt).strip()
                    if _has_separator(nxt):
                        return _cut_value(_next_value_token(nxt), candidates, stops)
                    return _cut_value(nxt, candidates, stops)
                return ''
    # reflowed single-line pass for labels wrapped across lines
    joined = re.sub(r'[ \t]*\n[ \t]*', ' ', text)
    for candidate in candidates:
        pattern = re.compile(re.escape(candidate.strip()), re.IGNORECASE)
        match = pattern.search(joined)
        if match:
            remainder = joined[match.end():].lstrip(' :=|-')
            return _cut_value(remainder, candidates, stops)
    return ''


def _has_separator(line):
    return '|' in line or (':' in line and not line.startswith(':'))


def _next_value_token(line):
    if '|' in line:
        return line.split('|', 1)[1]
    return line.split(':', 1)[1] if ':' in line else line


def _cut_value(value, own_candidates=(), stop_phrases=()):
    end = len(value)
    for sep in ('|', '\n'):
        pos = value.find(sep)
        if 0 < pos < end:
            end = pos
    own = {c.strip().lower() for c in own_candidates}
    for phrase in stop_phrases:
        p = phrase.strip().lower()
        if not p or p == value.strip().lower() or p in own:
            continue
        pos = value.lower().find(' ' + p)
        if pos > 0 and pos < end:
            end = pos
    return value[:end].strip(' :=|-,')


def _line_alone_value(text, label):
    """Handle the 'LABEL alone on its line' pattern found in many lab certificates."""
    escaped = _pattern_for(label)
    if not escaped:
        return ''
    alone = re.compile(r'^\s*%s\s*[:#\-–/]?\s*$' % escaped, re.IGNORECASE | re.MULTILINE)
    match = alone.search(text or '')
    if match:
        end = match.end()
    else:
        # second chance: the line is exactly the label separated by non-word remnants
        end = None
        for line in (text or '').split('\n'):
            if line.strip() and _normalize(line.strip()) == _normalize(label):
                end = (text or '').find(line) + len(line)
                break
        if end is None:
            return ''
    tail = (text or '')[end:]
    for rest in tail.split('\n'):
        rest = rest.strip()
        if not rest:
            continue
        rest = re.sub(r'^[A-Za-z][A-Za-z0-9 .&-]*:\s*\|?\s*', '', rest)
        return rest.strip()
    return ''


def _find_label_value(text, label):
    flat = re.sub(r'[ \t]+', ' ', text or '')
    for candidate in _label_candidates(label):
        pattern = _pattern_for(candidate)
        if not pattern:
            continue
        match = re.search(r'(?:%s)(?:[\s:.\-–/()|]|$)%s([^\n|]{2,140})' % (pattern, _SEPARATOR),
                          flat, flags=re.IGNORECASE)
        if match:
            value = re.sub(r'\s+', ' ', match.group(1)).lstrip(' .,;:-–=').strip()
            if value and value.lower() not in {'no', 'number', 'the', 'of', 'date'}:
                return value
    return ''


_DATE_PATTERNS = [
    (r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})', 'dmy'),
    (r'(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})', 'ymd'),
    (r'(\d{1,2})(?:st|nd|rd|th)?\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*[\s,.\-]*(\d{4}|\d{2})', 'dmy_name'),
    (r'(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s*(\d{1,2})(?:st|nd|rd|th)?[\s,.\-]*(\d{4})', 'mdy_name'),
]
_MONTHS = {name: index + 1 for index, name in enumerate(
    ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'])}


def _parse_date(value):
    value = (value or '').strip()
    for pattern, kind in _DATE_PATTERNS:
        match = re.search(pattern, value, flags=re.IGNORECASE)
        if not match:
            continue
        groups = match.groups()
        try:
            if kind == 'dmy':
                day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
            elif kind == 'ymd':
                year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
            elif kind == 'dmy_name':
                day = int(groups[0]); month = _MONTHS[groups[1][:3].lower()]; year = int(groups[2])
            else:
                month = _MONTHS[groups[0][:3].lower()]; day = int(groups[1]); year = int(groups[2])
            if year < 100:
                year += 2000
            return date(year, month, day).isoformat()
        except (ValueError, KeyError):
            continue
    return ''


def _find_temperature_humidity(text):
    temperature = humidity = ''
    match = re.search(r'([-+]?\d{1,2}(?:[.,]\d+)?)\s*°\s?C\b', text)
    if match:
        temperature = match.group(1).replace(',', '.')
    match = re.search(r'(\d{1,3}(?:[.,]\d+)?)\s*%\s*RH', text, flags=re.IGNORECASE)
    if not match:
        match = re.search(r'(?:humidity|rh)\D{0,12}(\d{1,3}(?:[.,]\d+)?)\s*%', text, flags=re.IGNORECASE)
    if match:
        humidity = match.group(1).replace(',', '.')
    if temperature and humidity:
        return '%s °C · %s %%RH' % (temperature, humidity)
    if temperature:
        return '%s °C' % temperature
    if humidity:
        return '%s %%RH' % humidity
    return ''


def _find_conclusion(text):
    window = (text or '')[-2000:]
    match = re.search(
        r'(?:conclusion|result|verdict|conformity|disposition)\s*[:\-–]?\s*([^\n|]{0,60})',
        window, flags=re.IGNORECASE)
    scope = match.group(1) if match else window
    verdicts = re.findall(r'\b(pass|fail)\b', scope, flags=re.IGNORECASE)
    if not verdicts:
        verdicts = re.findall(r'\b(pass(?:ed|ing)?|fail(?:ed)?)\b', window, flags=re.IGNORECASE)
    lowered = {verdict.lower()[:4] for verdict in verdicts}
    if 'pass' in lowered and 'fail' not in lowered:
        return 'pass'
    if 'fail' in lowered and 'pass' not in lowered:
        return 'fail'
    if verdicts:
        return verdicts[-1].lower()[:4]
    return ''


def extract_fields(text, template_activities=None, labels=None):
    text = text or ''
    template_activities = template_activities or []
    flat = re.sub(r'[ \t]+', ' ', text)
    if template_activities:
        return _derive_flat_fields(_extract_activities(flat, template_activities),
                                   template_activities, text)
    fields = {
        'serial_no': _find_label_value(flat, 'Serial/Tag Number'),
        'model': _find_label_value(flat, 'Model Number'),
        'certificate_no': _find_label_value(flat, 'Certificate Number') or _find_label_value(flat, 'Certificate No'),
        'test_date': _parse_date(_find_label_value(flat, 'Test Date') or _find_label_value(flat, 'Date of Calibration')),
        'due_date': _parse_date(_find_label_value(flat, 'Due Date') or _find_label_value(flat, 'Calibration Due')),
        'environment': _find_temperature_humidity(flat),
        'conclusion': _find_conclusion(flat),
    }
    return fields


def _slugify(label):
    import re as _re
    slug = _re.sub(r'[^a-z0-9]+', '_', str(label).lower()).strip('_')
    return slug or 'field'


def _extract_activities(text, labels):
    all_candidates = _all_label_candidates(labels)
    out = {}
    for label in labels:
        value = _find_value(text, label, all_candidates)
        if value and _normalize(value) in {_normalize(l) for l in labels if l != label}:
            value = ''
        out[_slugify(label)] = value
    return out


def _derive_flat_fields(activities, labels, text):
    def find(matcher):
        for label in labels:
            if matcher(label.lower()):
                return activities.get(_slugify(label), '')
        return ''

    return {
        'serial_no': find(lambda s: 'serial' in s or 'tag' in s or 'asset' in s),
        'model': find(lambda s: s.startswith('model') or 'instrument' in s),
        'certificate_no': find(lambda s: 'certificate' in s or s.startswith('cert')),
        'test_date': _parse_date(find(lambda s: 'test date' in s or 'calibration date' in s) or find(lambda s: 'date' in s)),
        'due_date': _parse_date(find(lambda s: 'due' in s or 'expir' in s)),
        'environment': find(lambda s: 'env' in s and 'cond' in s) or find(lambda s: 'temperature' in s or 'humidity' in s or 'ambient' in s),
        'conclusion': _find_conclusion(text or ''),
    }


def _normalize_row(value):
    return re.sub(r'[^a-z0-9]+', '', str(value).lower())


def _find_test_data_block(text, columns):
    """Anchor on the 'TEST DATA' banner and read the value row(s) that follow the header.

    Certificates that print TEST DATA mid-document followed by a column-header
    line and a value line land in this branch.
    """
    if not columns:
        return None
    flat = re.sub(r'[ \t]+', ' ', text or '')
    lines = flat.split('\n')
    # locate the marker line ("TEST DATA", "TEST" / "DATA" variants, or a line holding the header)
    anchor = None
    for index, line in enumerate(lines):
        if re.search(r'\bTEST\s*DATA\b|(?:result|test)\s*(?:data|results)', line, re.IGNORECASE):
            anchor = index
            break
    norm_cols = [_normalize_row(column) for column in columns]
    order = [index for index, line in enumerate(lines)]
    if anchor is None:
        order = list(range(len(lines)))
    else:
        order = list(range(anchor, len(lines)))
    for i in order:
        line = lines[i]
        line_norm = _normalize_row(line)
        hits = [position for position, norm in enumerate(norm_cols) if norm and norm in line_norm]
        if len(hits) < max(2, (len(columns) + 1) // 2):
            continue
        # candidate table starts at this line; the first dense line after it is the value row
        for k in range(i + 1, min(i + 6, len(lines))):
            candidate = lines[k].strip()
            if not candidate:
                continue
            cells = _split_cells(candidate, len(columns))
            if cells is None or not any(cells):
                continue
            row = [''] * len(columns)
            if len(cells) <= len(hits):
                for column_index, cell in zip(hits, cells):
                    row[column_index] = cell
                return row
            # trust the order of the cells in the matched line itself
            ordered = sorted(hits)
            for column_index, cell in zip(ordered, cells):
                row[column_index] = cell
            return row
    return None


def _split_cells(line, expected):
    parts = re.split(r'\s{2,}|\t|\|', line)
    parts = [part.strip() for part in parts if part.strip()]
    if len(parts) == expected:
        return parts

    tokens = re.findall(r'\S+', line)
    if not tokens:
        return None
    if len(tokens) <= expected:
        if len(tokens) == expected - 1 and any(token in {'-', '–', '—'} for token in tokens):
            tokens = ['-'] + tokens if False else tokens
        result = list(tokens)
        while len(result) < expected:
            result.append('')
        if len(result) > expected:
            result = result[:expected]
        return result
    chunk = max(1, len(tokens) // expected)
    result = []
    for index in range(expected):
        start = index * chunk
        end = start + chunk if index < expected - 1 else None
        result.append(' '.join(tokens[start:end]).strip(' .,;'))
    return result


def _token_set(text):
    return set(re.findall(r'[a-z0-9]{2,}', (text or '').lower()))


def match_template(text, templates):
    """Score how well each stored template can be filled by this certificate.

    Returns (best_template, score, detail) — never a fabricated choice.
    A template with no label fingerprint at all scores 0; if nothing clears
    the confidence bar, best_template is None and the caller must stop.
    """
    cert_tokens = _token_set(text or '')
    scored = []
    for template in templates:
        activities = list(template.activities or [])
        columns = list(template.columns or [])
        if not activities and not columns:
            scored.append((template, 0.0, {'field_hits': 0, 'col_hits': 0}))
            continue
        field_hits = sum(1 for label in activities if (_token_set(label) and _token_set(label) <= cert_tokens))
        col_hits = sum(1 for col in columns if (_token_set(col) and _token_set(col) <= cert_tokens))
        n_field = max(1, len(activities))
        n_col = max(1, len(columns))
        score = (2 * field_hits / n_field + col_hits / n_col) / 3 if activities else col_hits / n_col
        scored.append((template, score, {'field_hits': field_hits, 'col_hits': col_hits,
                                         'field_total': len(activities), 'col_total': len(columns)}))
    scored.sort(key=lambda item: item[1], reverse=True)
    if not scored:
        return None, 0.0, {'field_hits': 0, 'col_hits': 0}
    best_template, best_score, best_detail = scored[0]
    return best_template, best_score, best_detail


# ------------------------------------------------------------- tables

def _score_row(row, columns):
    """How many of the expected columns appear as this row's cells."""
    hit = 0
    mapping = {}
    for column in columns:
        wanted = _normalize(column)
        for cell_index, cell in enumerate(row):
            cell_norm = _normalize(cell)
            if cell_norm and (cell_norm == wanted or wanted in cell_norm or cell_norm in wanted):
                mapping.setdefault(column, cell_index)
                hit += 1
                break
    return hit, mapping


def _table_size(table):
    return len(table) * max((len(row) for row in table), default=0)


def _group_by_width(rows):
    """Split rows into tables by consecutive equal non-empty widths."""
    groups = []
    current = []
    current_width = None
    for row in rows:
        width = len([cell for cell in row if str(cell).strip()])
        if width == 0:
            if current:
                groups.append(current)
                current = []
                current_width = None
            continue
        if current_width in (None, width):
            current.append(list(row))
            current_width = width
        else:
            if current:
                groups.append(current)
            current = [list(row)]
            current_width = width
    if current:
        groups.append(current)
    return groups


def extract_table(tables, template_columns, text=''):
    template_columns = list(template_columns or [])
    all_tables = list(tables)
    for table in list(tables):
        all_tables.extend(_group_by_width(table))
    if all_tables:
        best_score, best_row_index, best_mapping, best_table = 0, 0, {}, None
        for table in all_tables:
            for index, row in enumerate(table):
                score, mapping = _score_row(row, template_columns)
                if score > best_score:
                    best_score, best_row_index, best_mapping, best_table = score, index, mapping, table
        required = max(1, (len(template_columns) + 1) // 2) if template_columns else 1
        if best_table is not None and best_score >= required:
            rows = []
            for raw in best_table[best_row_index + 1:]:
                if not any(str(cell).strip() for cell in raw):
                    continue
                row = []
                for column in template_columns:
                    index = best_mapping.get(column)
                    cell = str(raw[index]).replace('\n', ' ').strip() if (index is not None and index < len(raw)) else ''
                    row.append(cell)
                rows.append(row)
            return template_columns, rows, best_score
    if text:
        anchored = _find_test_data_block(text, template_columns)
        if anchored:
            return template_columns, [anchored], sum(1 for cell in anchored if cell)
        row = [_inline_column_value(text, col) for col in template_columns]
        if any(row):
            return template_columns, [row], sum(1 for cell in row if cell)
    return template_columns, [], 0


# ------------------------------------------------------------- top-level

def extract_certificate(path, filename, template_columns, template_activities=None):
    template_activities = list(template_activities or [])
    text, tables, provider = read_document(path, filename)
    activities = _extract_activities(re.sub(r'[ \t]+', ' ', text or ''), template_activities) if template_activities else {}
    fields = extract_fields(text, template_activities, template_activities)
    columns, rows, matched = extract_table(tables, template_columns, text=text)
    missing = [key for key, value in fields.items() if not value]
    missing += [key for key, value in activities.items() if not value]
    if not rows and (template_columns or tables):
        missing.append('table')
    return {
        'provider': provider,
        'fields': fields,
        'activities': activities,
        'columns': columns,
        'rows': rows,
        'missing': missing,
        'text_length': len(text or ''),
        'table_columns_matched': matched,
    }
