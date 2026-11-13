"""Faithful HTML replica of the laboratory's equipment-log Excel sheet.

Every surface that shows a certificate shows the sheet itself — the logo, the
border grid, the LAB GENERAL ACTIVITIES LOG block, the TEST DATA table — never
plain form cards. Values from the certificate (or a saved record) are written
into the same cells the sheet prints.

Public API:
    render_sheet(ws, editable=False, values=None) -> html string
    values = {
        'activities': {slug: value},   # prefill field inputs (act_<slug>)
        'rows': [[cell, …], …],        # prefill TEST DATA rows, column order
    }
"""
from __future__ import annotations

import base64
import html
import re


def _mark_safe(value):
    try:
        from django.utils.safestring import mark_safe
        return mark_safe(value)
    except Exception:
        return value


def label_slug(label):
    slug = re.sub(r'[^a-z0-9]+', '_', str(label).lower()).strip('_')
    return slug or 'field'


def load_sheet(file_or_path, sheet_name=None):
    from openpyxl import load_workbook
    workbook = load_workbook(file_or_path, data_only=True)
    name = sheet_name if sheet_name in workbook.sheetnames else workbook.sheetnames[0]
    return workbook[name]


def _text(value):
    return re.sub(r'\s+', ' ', str(value if value is not None else '')).strip()


# ----------------------------------------------------------- merged cells

def merged_map(ws):
    """Map (row, col) -> True for covered cells; (row, col) -> (colspan, rowspan)
    for the top-left cell of each merged range."""
    spans = {}
    covered = set()
    for mr in (ws.merged_cells.ranges if hasattr(ws, 'merged_cells') else []):
        top = (mr.min_row, mr.min_col)
        span = (mr.max_col - mr.min_col + 1, mr.max_row - mr.min_row + 1)
        spans[top] = span
        for r in range(mr.min_row, mr.max_row + 1):
            for c in range(mr.min_col, mr.max_col + 1):
                if (r, c) != top:
                    covered.add((r, c))
    return spans, covered


def _row_cells(ws, r, max_col):
    return [_text(ws.cell(row=r, column=c).value) for c in range(1, max_col + 1)]


def _is_section_title(cells):
    filled = [i for i, cell in enumerate(cells) if cell]
    if len(filled) != 1:
        return False
    text = cells[filled[0]]
    letters = [ch for ch in text if ch.isalpha()]
    if len(letters) < 4:
        return False
    caps = sum(1 for ch in letters if ch.isupper())
    return caps >= len(letters) * 0.6


# ----------------------------------------------------------------- image

def _image_uri(ws):
    try:
        images = list(getattr(ws, '_images', []) or [])
    except Exception:
        images = []
    if not images:
        return None
    try:
        payload = images[0]._data()
    except Exception:
        return None
    return 'data:image/png;base64,%s' % base64.b64encode(payload).decode('ascii')


def _col_group(ws):
    letters = [chr(ord('A') + i) for i in range(ws.max_column or 1)]
    widths = {}
    for letter, dimension in ws.column_dimensions.items():
        if dimension.width:
            widths[letter] = dimension.width
    total = sum(widths.get(letter, 9.5) for letter in letters) or 1.0
    cols = ''.join('<col style="width:%.2f%%">' % (100.0 * widths.get(letter, 9.5) / total)
                   for letter in letters)
    return '<colgroup>' + cols + '</colgroup>'


def _table_config(ws):
    """Find the TEST DATA header row: all-filled row where every cell is bold."""
    for r in range(1, (ws.max_row or 1) + 1):
        row = ws[r]
        cells = [_text(c.value) for c in row]
        filled = [c for c in cells if c]
        if len(filled) < 3:
            continue
        if all(bool(c.font.bold) for c in row if _text(c.value)):
            return r
    return None


# ----------------------------------------------------------------- render

def render_sheet(ws, editable=False, values=None):
    values = values or {}
    activity_values = values.get('activities') or {}
    data_rows = values.get('rows') or []
    headers = values.get('columns') or []
    spans, covered = merged_map(ws)
    table_header_row = _table_config(ws)
    max_col = ws.max_column or 1
    image_uri = _image_uri(ws)
    parts = ['<div class="cert-sheet-wrap">']
    if image_uri:
        parts.append('<div class="cert-logo"><img src="%s" alt="Company logo"></div>' % image_uri)
    parts.append('<table class="cert-sheet">')
    parts.append(_col_group(ws))
    parts.append('<tbody>')
    data_index = 0
    for r in range(1, (ws.max_row or 1) + 1):
        raw = _row_cells(ws, r, max_col)
        if not any(raw):
            continue
        row = ws[r]
        filled_count = sum(1 for cell in raw if cell)
        kind_title = _is_section_title(raw)
        kind_table_header = table_header_row == r
        # the table run ends at the first sparse/blank row after the header
        kind_data = bool(table_header_row) and r > table_header_row and filled_count >= 3
        cells_html = []
        c = 1
        while c <= max_col:
            key = (r, c)
            if key in covered:
                c += 1
                continue
            span = spans.get(key, (1, 1))[0]
            cell = row[c - 1]
            value = _text(cell.value)
            classes = []
            bold = bool(cell.font.bold)
            if kind_title:
                classes.append('sv-title')
            elif kind_table_header:
                classes.append('sv-head')
            else:
                classes.append('sv-plain')
            if bold and kind_table_header is not True and kind_title is not True:
                classes.append('sv-bold')
            # --- field row: label + input in the adjacent value cell      ---
            if editable and any(_is_field_label(v) for v in raw):
                if bold and not kind_title and not kind_table_header and value:
                    slug = label_slug(value)
                    if slug in activity_values:
                        # label cell stays text; value cell becomes an input
                        target = _next_text_cell(raw, c)
                        value_cell = '' if span == 1 else ''
                        cells_html.append('<th class="sv-label" colspan="%d">%s</th>' % (span, html.escape(value)))
                        input_html = ('<input class="qinput" name="act_%s" value="%s">'
                                      % (html.escape(slug), html.escape(str(activity_values.get(slug, '')))))
                        # the remaining spanned columns become one input cell
                        covered_span = 1 + (target - c - 1)
                        cells_html.append('<td class="sv-input" colspan="%d">%s</td>' % (covered_span, input_html))
                        c = target + 1
                        continue
            if editable and kind_data and headers:
                # data row: every cell is an input, aligned to the header columns
                text = ''
                if data_index < len(data_rows) and (c - 1) < len(data_rows[data_index]):
                    text = str(data_rows[data_index][c - 1])
                cells_html.append('<td class="sv-input sv-td"><input class="qinput cell" name="cell_%d_%d" value="%s"></td>'
                                  % (data_index, c - 1, html.escape(text)))
                c += 1
                continue
            tag = 'th' if kind_title else 'td'
            cells_html.append('<%s class="%s" colspan="%d">%s</%s>'
                              % (tag, ' '.join(classes), span, html.escape(value), tag))
            c += span
        if kind_data:
            data_index += 1
        parts.append('<tr>' + ''.join(cells_html) + '</tr>')
    parts.append('</tbody>')
    parts.append('</table></div>')
    return _mark_safe(''.join(parts))


def _is_field_label(text):
    return bool(text) and not text.upper() == text  # not ALL CAPS (those are titles)


def _next_text_cell(raw, from_index):
    for j in range(from_index + 1, len(raw)):
        if raw[j]:
            return j
    return from_index + 1
