"""Deterministic structure detection for equipment-log Excel templates.

Reads the sheet produced by the laboratory (and its family of variants) and
finds three kinds of blocks, preserving order:

* section titles   — e.g. "LAB GENERAL ACTIVITIES LOG", "TEST DATA"
* field blocks     — label/value pairs (label repeated in ONE column,
                     value in the next non-empty cell), e.g. the activities log
* table blocks     — a header row followed by consistently-wide data rows

Nothing is taken on faith: the upload wizard shows what was detected and the
user includes/excludes each block before the template is stored.
"""
from __future__ import annotations

import re
from pathlib import Path
from openpyxl import load_workbook

MAX_PREVIEW = 15
MAX_COLS = 40


def _text(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def _row_cells(row, limit=MAX_COLS):
    return [_text(cell) for cell in row[:limit]]


def _non_empty(cells):
    return [index for index, cell in enumerate(cells) if cell]


def _is_section_title(cells):
    filled = _non_empty(cells)
    if len(filled) != 1:
        return False
    text = cells[filled[0]]
    if not (4 <= len(text) <= 60):
        return False
    letters = [ch for ch in text if ch.isalpha()]
    if len(letters) < 4 or len(text.split()) > 8 or not text[0].isalpha():
        return False
    caps = sum(1 for ch in letters if ch.isupper())
    return caps / len(letters) >= 0.6


def _looks_like_signature_block(labels):
    lowered = [label.lower() for label in labels]
    hits = sum(1 for label in lowered if label.startswith(('reviewed by', 'designation', 'signature', 'date')))
    return hits >= 2


def parse_sheet(path, sheet_name=None):
    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet_name = sheet_name if sheet_name in workbook.sheetnames else workbook.sheetnames[0]
    worksheet = workbook[sheet_name]
    raw_rows = list(worksheet.iter_rows(values_only=True))
    rows = [_row_cells(list(row)) for row in raw_rows]
    rows = [row for row in rows]  # keep layout positions; empty rows are meaningful separators

    # ---- index rows by section title --------------------------------------
    section_at = {}
    for index, row in enumerate(rows):
        if _is_section_title(row):
            section_at[index] = rows[index][_non_empty(row)[0]]

    boundaries = sorted(section_at)

    def classify_block(first, last):
        segment = rows[first:last]
        filled_rows = [(i, r) for i, r in enumerate(segment) if any(r)]
        # width histogram to split field-blocks from table blocks
        blocks = []
        cursor = 0
        while cursor < len(filled_rows):
            _, probe = filled_rows[cursor]
            width = len(_non_empty(probe))
            if width >= 3:
                # possible table start: header row, then >=1 equally-wide rows
                end = cursor
                rows_here = []
                while end < len(filled_rows):
                    _, candidate = filled_rows[end]
                    if len(_non_empty(candidate)) != width:
                        break
                    rows_here.append(candidate)
                    end += 1
                if len(rows_here) >= 2:
                    blocks.append({'type': 'table', 'rows': rows_here})
                    cursor = end
                    continue
            # otherwise start a field block
            end = cursor
            rows_here = []
            while end < len(filled_rows):
                _, candidate = filled_rows[end]
                w = len(_non_empty(candidate))
                if w >= 3:
                    break
                rows_here.append(candidate)
                end += 1
            if rows_here:
                blocks.append({'type': 'fields', 'rows': rows_here})
            cursor = end
        return blocks

    # ---- split the sheet into sections (or one implicit section) ---------
    segments = []
    if boundaries:
        start = None
        for position, boundary in enumerate(boundaries):
            if start is not None:
                segments.append((start, boundary))
            # section content ends at the next section title
            start = boundary + 1
        segments.append((start, len(rows)))
        section_map = list(zip([section_at[b] for b in boundaries], segments))
    else:
        section_map = [(None, (0, len(rows)))]

    candidates = []
    for title, (first, last) in section_map:
        if first >= last:
            continue
        for block in classify_block(first, last):
            if block['type'] == 'fields':
                fields = []
                for row in block['rows']:
                    filled = _non_empty(row)
                    label = row[filled[0]]
                    value = row[filled[1]] if len(filled) > 1 else ''
                    fields.append({'label': label, 'sample': value})
                if fields:
                    candidates.append({
                        'type': 'fields',
                        'section': title,
                        'labels': [f['label'] for f in fields],
                        'samples': [f['sample'] for f in fields],
                        'default': not _looks_like_signature_block([f['label'] for f in fields]),
                    })
            else:
                header = block['rows'][0]
                columns = [cell for cell in header if cell]
                data_rows = [[cell for cell in row] for row in block['rows'][1:]]
                candidates.append({
                    'type': 'table',
                    'section': title,
                    'columns': columns,
                    'samples': data_rows[0] if data_rows else [],
                    'default': True,
                })
    # ---- keep only plausible template content ------------------------------
    preview = [_row_cells(list(row))[:12] for row in rows][:MAX_PREVIEW]
    return {
        'sheet': sheet_name,
        'sheets': list(workbook.sheetnames),
        'sections': [title for title, _ in section_map if title],
        'candidates': candidates,
        'preview_rows': preview,
        'total_rows': len(rows),
    }


def slugify(label):
    slug = re.sub(r'[^a-z0-9]+', '_', str(label).lower()).strip('_')
    return slug or 'field'
