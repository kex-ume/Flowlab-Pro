"""Parser for EATL uncertainty-budget workbooks (EATL/LAB/UNC/xx format).

Extracts the workbook's header info (doc ref / revision / date / title), the
Type-B uncertainty component table (Symbol / Source / Value / Distribution /
Divisor / Std uncertainty / Method) and the per-point calibration grid so a
budget can be uploaded, stored and re-used across calibration logs of the same
scope. The layout is located by scanning cell contents rather than hard-coded
coordinates, so minor spreadsheet tweaks (new rows/columns/merges) do not break
parsing.
"""
import math
import re
from datetime import date, datetime

import openpyxl

_TITLE_RE = re.compile(r'uncertainty\s*budget', re.I)
_DOC_REF_RE = re.compile(r'\b([A-Z][A-Z0-9/._-]{6,})\b')
_REV_RE = re.compile(r'\brev(?:ision)?\s*[.:=]?\s*(\S+)', re.I)
_DATE_RE = re.compile(r'(\d{1,2})[./-](\d{1,2})[./-](\d{4})')


def _fmt(v):
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return v


def _as_number(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip().replace(',', '')
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _cell(row, idx):
    try:
        return row[idx].value
    except IndexError:
        return None


def parse_budget_file(path):
    """Parse an EATL uncertainty-budget workbook file.

    Returns a dict: header, components, points, warnings.
    """
    header = {'doc_ref': '', 'revision': '', 'revised_on': None, 'title': '', 'sheet': ''}
    components = []
    points = []
    warnings = []

    wb = openpyxl.load_workbook(path, data_only=True)
    for ws in wb.worksheets:
        rows = list(ws.iter_rows())
        doc_ref_slash = ''     # preferred: a real document reference EATL/LAB/UNC/xx
        doc_ref_unc = ''       # fallback: any 'UNC…' tag found (e.g. 'UNC 01')
        # ── Header scan (title, doc ref, revision, date) ──────────────────
        for r in rows:
            for cell in r:
                v = cell.value
                if v is None:
                    continue
                s = str(v).strip()
                if not header['title'] and s and _TITLE_RE.search(s):
                    header['title'] = s
                    header['sheet'] = ws.title
                if s:
                    m = _DOC_REF_RE.search(s)
                    if m and len(m.group(1)) > 8:
                        if '/' in m.group(1) and not doc_ref_slash:
                            doc_ref_slash = m.group(1)
                        elif 'UNC' in m.group(1) and not doc_ref_unc:
                            doc_ref_unc = m.group(1)
                if not header['revision'] and s.lower().startswith('rev'):
                    m = _REV_RE.match(s)
                    if m:
                        header['revision'] = m.group(1).rstrip(',;')
                if header['revised_on'] is None:
                    if isinstance(v, (datetime, date)):
                        header['revised_on'] = v.date() if isinstance(v, datetime) else v
                    elif isinstance(v, str):
                        dm = _DATE_RE.search(v)
                        if dm and int(dm.group(3)) > 1990:
                            header['revised_on'] = date(int(dm.group(3)), int(dm.group(2)), int(dm.group(1)))
                if header['revision'] and header['revised_on'] is not None and header['title']:
                    break
            if header['revision'] and header['revised_on'] is not None and header['title']:
                break
        header['doc_ref'] = doc_ref_slash or doc_ref_unc

        # ── Component table: locate the header row (Symbol/Source/Value/…) ─
        comp_header_row = None
        for i, r in enumerate(rows):
            texts = {str(c.value).strip().lower() for c in r if c.value is not None}
            if texts >= {'symbol', 'source', 'value'} and any('distribution' in t or 'divisor' in t for t in texts):
                comp_header_row = i
                break

        if comp_header_row is not None:
            cols = rows[comp_header_row]
            def col_of(label, default):
                for j, c in enumerate(cols):
                    if c.value is not None and label in str(c.value).strip().lower():
                        return j
                return default

            c_symbol = col_of('symbol', 13)
            c_source = col_of('source', 14)
            c_value = col_of('value', 15)
            c_dist = col_of('distribution', 16)
            c_div = col_of('divisor', 17)
            c_std = col_of('std', 18)
            c_method = col_of('method', 20)
            method_seq = []   # methods are often shifted one row up from their
            # component (author habit in the EATL template); collect in order
            # and pair positionally so the description follows its symbol.
            for r in rows[comp_header_row + 1:]:
                sym = (_cell(r, c_symbol) or '').strip()
                src = (_cell(r, c_source) or '').strip()
                method_txt = (_cell(r, c_method) or '').strip()
                if method_txt:
                    method_seq.append(method_txt[:200])
                if not sym and not src:
                    if components:
                        break
                    continue
                if sym.lower().startswith(('ucomb', 'uexp')):
                    continue
                value_raw = _cell(r, c_value)
                divisor = _as_number(_cell(r, c_div))
                std = _as_number(_cell(r, c_std))
                if std is None and divisor:
                    value_num = _as_number(value_raw)
                    if value_num is not None:
                        std = value_num / divisor
                if len(src) > 100:
                    src = src[:100]
                components.append({
                    'position': len(components) + 1,
                    'symbol': sym[:40],
                    'source': src,
                    'method': '',
                    'value': (str(value_raw)[:60] if value_raw is not None else ''),
                    'distribution': (_cell(r, c_dist) or '')[:30],
                    'divisor': round(divisor, 6) if divisor else None,
                    'std_uncertainty': round(std, 6) if std is not None else None,
                })
            for i, comp in enumerate(components):
                comp['method'] = method_seq[i] if i < len(method_seq) else comp['method']

        # ── Per-point grid: rows with a numeric reference in col B ─────────
        for r in rows:
            ref = _as_number(_cell(r, 1))
            if ref is None:
                continue
            g = _as_number(_cell(r, 6))      # correction (Pind-ref)
            q = _as_number(_cell(r, 16))     # expanded U
            if g is None and q is None:
                continue
            points.append({
                'ref': ref,
                'correction': g,
                'expanded': q,
            })

    if not components:
        warnings.append('No Type-B uncertainty table found — the workbook may not be an EATL uncertainty budget.')

    return {
        'header': header,
        'components': components,
        'points': points,
        'warnings': warnings,
    }