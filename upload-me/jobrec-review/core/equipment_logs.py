"""Equipment Certificate Logs — Administrator-only certificate log.

RECORDS → Equipment Logs

No AI, no external service: text PDFs/DOCX are parsed locally, scanned PDFs are
read with the local RapidOCR engine. Values are extracted (never invented), the
operator verifies them in Review, a Preview step re-shows everything, and
"Yes, Done" saves the record and deletes the uploaded file.

Templates are uploaded Excel sheets (one per equipment group). The upload
wizard auto-detects the sheet structure — activities-log fields, a test-data
table and an optional signature block — and preserves it. A certificate is
later read against its template's own labels.
"""
import functools
import json
import re
import uuid
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook
from django.db.models import Count

from . import ei_workflow as service
from .auth_utils import is_administrator
from .cert_extract import extract_certificate, _derive_flat_fields, match_template, read_document
from .cert_sheet import render_sheet, load_sheet
from .models import EquipmentCertificateRecord, EquipmentCertificateTemplate, Primary
from .template_parser import parse_sheet, slugify

TMP_DIR = Path(settings.EI_PRIVATE_STORAGE_ROOT) / 'tmp' / 'cert_upload'
SESSION_KEY = 'equipment_log_upload'
MAX_ROWS = 500
MAX_COLS = 60
ALLOWED_SUFFIXES = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.csv'}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


# ----------------------------------------------------------------- helpers

def _admin_required(view):
    @login_required
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        if not is_administrator(request.user):
            raise PermissionDenied('Equipment Logs is restricted to administrators.')
        return view(request, *args, **kwargs)
    return wrapper


def _session_upload(request, key=None):
    data = request.session.get(SESSION_KEY) or {}
    if key is None:
        return data
    return data.get(key)


def _stash_upload(request, **payload):
    data = request.session.get(SESSION_KEY) or {}
    data.update(payload)
    request.session[SESSION_KEY] = data
    request.session.modified = True
    return data


def _clear_upload(request):
    data = request.session.pop(SESSION_KEY, None) or {}
    token = data.get('token')
    template_token = data.get('template_token')
    for candidate in (token, template_token):
        if not candidate:
            continue
        safe = re.sub(r'[^a-f0-9]', '', str(candidate).lower())
        for suffix in ('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.csv', '.html', '.json'):
            try:
                (TMP_DIR / (safe + suffix)).unlink(missing_ok=True)
            except OSError:
                pass


def _extraction_path(token):
    return TMP_DIR / (re.sub(r'[^a-f0-9]', '', str(token).lower()) + '.json')


def _upload_path(request):
    data = _session_upload(request)
    if not data.get('token'):
        return None, None
    safe = re.sub(r'[^a-f0-9]', '', str(data['token']).lower())
    for suffix in ('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.csv'):
        candidate = TMP_DIR / (safe + suffix)
        if candidate.is_file():
            return candidate, data
    return None, data


_CONTENT_TYPES = {
    '.pdf': 'application/pdf',
    '.doc': 'application/msword',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.xls': 'application/vnd.ms-excel',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.csv': 'text/csv',
}


def _content_type(filename):
    suffix = Path(filename).suffix.lower()
    return _CONTENT_TYPES.get(suffix, 'application/octet-stream')


def _is_office_type(suffix):
    return suffix in ('.doc', '.docx', '.xls', '.xlsx', '.csv')


def _toast(request, level, text):
    getattr(messages, level)(request, text)


def _activity_pairs(labels, values):
    values = values or {}
    return [(label, slugify(label), values.get(slugify(label), '')) for label in labels]


# ----------------------------------------------------------------- home

@_admin_required
def home(request):
    records = EquipmentCertificateRecord.objects.all()
    years = list(records.values_list('year', flat=True).distinct().order_by('-year'))
    current_year = timezone.localdate().year
    if current_year not in years:
        years = sorted({*years, current_year}, reverse=True)
    year_cards = []
    for year in years:
        year_records = records.filter(year=year)
        year_cards.append({
            'year': year,
            'types': year_records.values('template').distinct().count(),
            'serials': year_records.values('serial_no').distinct().count(),
        })
    return render(request, 'core/equipment_logs/home.html', {
        'year_cards': year_cards,
        'template_count': EquipmentCertificateTemplate.objects.count(),
        'page_title': 'Equipment Logs',
    })


# ------------------------------------------------------- step 1: upload

@_admin_required
def upload(request):
    if request.method == 'POST':
        file = request.FILES.get('certificate')
        if not file:
            _toast(request, 'error', 'Choose a certificate file (PDF, Word, Excel or CSV).')
            return redirect('equipment_log_upload')
        suffix = Path(file.name or '').suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            _toast(request, 'error', 'Supported file types: PDF, DOC, DOCX, XLS, XLSX, CSV.')
            return redirect('equipment_log_upload')
        if file.size > MAX_UPLOAD_BYTES:
            _toast(request, 'error', 'File is larger than 20 MB.')
            return redirect('equipment_log_upload')
        _clear_upload(request)
        token = uuid.uuid4().hex
        TMP_DIR.mkdir(parents=True, exist_ok=True)
        staged = TMP_DIR / (token + suffix)
        with staged.open('wb') as handle:
            for chunk in file.chunks():
                handle.write(chunk)
        # Read the raw text first, then pick the template automatically.
        text, _tables, provider = read_document(str(staged), file.name or f'certificate{suffix}')
        candidates = list(EquipmentCertificateTemplate.objects.all())
        template, score, detail = match_template(text, candidates)
        if template is None or score < 0.5:
            _toast(request, 'error',
                   'This certificate did not match any stored template. Upload and confirm a template '
                   'for this certificate type first.')
            return redirect('equipment_log_upload')
        extraction = extract_certificate(
            str(staged), file.name or f'certificate{suffix}',
            list(template.columns or []), list(template.activities or []),
        )
        _extraction_path(token).write_text(json.dumps(extraction), encoding='utf-8')
        _stash_upload(request, token=token, filename=Path(file.name or f'certificate{suffix}').name,
                      template_id=template.pk, match_score=round(score * 100),
                      match_hits=detail.get('field_hits'), match_fields=detail.get('field_total'))
        return redirect('equipment_log_review')
    templates = EquipmentCertificateTemplate.objects.all().order_by('name')
    return render(request, 'core/equipment_logs/upload_step1.html', {
        'templates': templates,
        'page_title': 'Upload Certificate',
    })


def _load_extraction(token):
    path = _extraction_path(token)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding='utf-8'))


# ----------------------------------------------------- step 2: review

@_admin_required
def review(request):
    staged, data = _upload_path(request)
    if staged is None or not data.get('token'):
        _toast(request, 'error', 'Start by uploading a certificate.')
        return redirect('equipment_log_upload')
    template = get_object_or_404(EquipmentCertificateTemplate, pk=data.get('template_id'))
    activities = list(template.activities or [])
    extraction = _load_extraction(data['token']) or {'fields': {}, 'activities': {}, 'columns': template.columns, 'rows': [], 'missing': [], 'provider': 'unknown'}

    def _render(values, mode):
        activity_map = values.get('field_values') or {}
        if staged.suffix.lower() != '.pdf':
            _preview_html(staged, data['token'])
        from .cert_extract import read_document
        preview_text, _t, _p = read_document(str(staged), data.get('filename') or staged.name)
        with template.original_file.open('rb') as handle:
            ws = load_sheet(handle, None)
            sheet_html = render_sheet(ws, editable=(mode != 'preview'),
                                      values={'activities': activity_map,
                                              'rows': values.get('rows') or [],
                                              'columns': values.get('columns') or list(template.columns or [])})
        return render(request, 'core/equipment_logs/review.html', {
            'template': template,
            'data': values,
            'mode': mode,
            'filename': data.get('filename'),
            'missing': extraction.get('missing') or [],
            'provider': extraction.get('provider'),
            'viewer_url': _viewer_url(data['token']),
            'preview_text': preview_text or '(No readable text found in this file.)',
            'sheet_html': sheet_html,
            'match_score': data.get('match_score'),
            'match_hits': data.get('match_hits'),
            'match_fields': data.get('match_fields'),
            'page_title': 'Review & fix' if mode != 'preview' else 'Preview record',
        })

    if request.method == 'POST':
        mode = request.POST.get('mode', 'preview')
        values = _values_from_post(request, template)
        # Test-date validation is enforced on save, not on preview.
        return _render(values, mode)

    fields = dict(extraction.get('fields') or {})
    raw_activities = dict(extraction.get('activities') or {})
    field_values = {slugify(label): raw_activities.get(slugify(label), '') for label in activities} if activities else {}
    rows = list(extraction.get('rows') or [])
    values = {
        'serial_no': fields.get('serial_no', ''),
        'model': fields.get('model', ''),
        'certificate_no': fields.get('certificate_no', ''),
        'test_date': fields.get('test_date', ''),
        'due_date': fields.get('due_date', ''),
        'environment': fields.get('environment', ''),
        'conclusion': fields.get('conclusion', ''),
        'columns': list(template.columns or []),
        'rows': rows,
        'field_values': field_values,
    }
    return _render(values, 'review')


def _values_from_post(request, template):
    activities = list(template.activities or [])
    rows_raw = request.POST.get('rows_json') or '[]'
    try:
        rows = [[str(cell)[:200] for cell in row][:MAX_COLS] for row in json.loads(rows_raw)][:MAX_ROWS]
    except (ValueError, TypeError):
        rows = []
    conclusion = request.POST.get('conclusion', '').strip().lower()
    conclusion = conclusion if conclusion in ('pass', 'fail') else ''
    field_values = {}
    for label in activities:
        field_values[slugify(label)] = request.POST.get(f'act_{slugify(label)}', '').strip()
    if activities:
        flat = _derive_flat_fields(field_values, activities, text='')
    else:
        flat = {
            'serial_no': request.POST.get('serial_no', '').strip(),
            'model': request.POST.get('model', '').strip(),
            'certificate_no': request.POST.get('certificate_no', '').strip(),
            'test_date': request.POST.get('test_date', '').strip(),
            'due_date': request.POST.get('due_date', '').strip(),
            'environment': request.POST.get('environment', '').strip(),
        }
    flat['conclusion'] = conclusion
    return {
        'conclusion': conclusion,
        'columns': list(template.columns or []),
        'rows': rows,
        'field_values': field_values,
        **flat,
    }


def _preview_html(staged, token):
    """Read-only HTML preview of a staged certificate (Word / Excel / CSV),
    so the operator can compare values against the replica beside it."""
    target = TMP_DIR / (re.sub(r'[^a-f0-9]', '', str(token).lower()) + '.html')
    if target.is_file():
        return target
    suffix = staged.suffix.lower()
    parts = ['<!doctype html><html><head><meta charset="utf-8"><style>'
             'body{font:13px/1.6 Calibri,Arial,sans-serif;padding:14px;color:#111;background:#fff}'
             'pre{font:11px/1.4 Consolas,monospace;white-space:pre-wrap;background:#f7fafc;padding:10px;border:1px solid #dce4ea;border-radius:6px}'
             'table{border-collapse:collapse;width:100%;margin:8px 0}'
             'td,th{border:1px solid #999;padding:4px 8px;font-size:11px}'
             'h3{font-family:Calibri,Arial,sans-serif}'
             '</style></head><body>']
    if suffix == '.docx':
        from docx import Document
        document = Document(str(staged))
        for paragraph in document.paragraphs:
            if paragraph.text.strip():
                parts.append('<p>%s</p>' % _escape(paragraph.text))
        for table in document.tables:
            parts.append('<table>')
            for row in table.rows:
                parts.append('<tr>')
                for cell in row.cells:
                    parts.append('<td>%s</td>' % _escape(cell.text))
                parts.append('</tr>')
            parts.append('</table>')
    else:
        from .cert_extract import read_document
        text, _tables, _provider = read_document(str(staged), staged.name)
        parts.append('<pre>%s</pre>' % _escape(text))
    parts.append('</body></html>')
    target.write_text(''.join(parts), encoding='utf-8')
    return target


def _escape(text):
    return (str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def _viewer_url(token):
    return reverse('equipment_log_tmp', kwargs={'token': token})


@_admin_required
def serve_tmp(request, token):
    data = _session_upload(request)
    if not data.get('token') or data['token'] != token:
        raise Http404()
    safe = re.sub(r'[^a-f0-9]', '', str(token).lower())
    rendered = TMP_DIR / (safe + '.html')
    if rendered.is_file():
        return FileResponse(rendered.open('rb'), content_type='text/html')
    for suffix in ('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.csv'):
        candidate = TMP_DIR / (safe + suffix)
        if candidate.is_file():
            response = FileResponse(candidate.open('rb'), content_type=_content_type(candidate.name))
            response['X-Content-Type-Options'] = 'nosniff'
            return response
    raise Http404()


@_admin_required
def cancel(request):
    _clear_upload(request)
    _toast(request, 'info', 'Certificate upload cancelled. Nothing was saved.')
    return redirect('equipment_log_upload')


# ----------------------------------------------------- step 4: save

def _parse_iso_date(value):
    value = (value or '').strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return None


def _equipment_match(serial):
    return Primary.objects.filter(serial_no__iexact=(serial or '').strip()).first()


def add_months(day, months):
    import calendar
    index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12)
    month += 1
    return day.replace(year=year, month=month, day=min(day.day, calendar.monthrange(year, month)[1]))


def _save_record(request, template, values, *, reason):
    activities = list(template.activities or [])
    serial = (values.get('serial_no') or '').strip()
    test_date = _parse_iso_date(values.get('test_date'))
    if test_date is None:
        return None, 'A valid test date is required — check the field labelled like a date in the certificate.'
    year = test_date.year
    serial_key = serial.upper()
    record, created = EquipmentCertificateRecord.objects.get_or_create(
        template=template, serial_no=serial_key, year=year,
        defaults={
            'template_name': template.name,
            'test_date': test_date,
            **service.actor_fields(request.user),
        },
    )
    record.template_name = template.name
    record.test_date = test_date
    record.due_date = _parse_iso_date(values.get('due_date'))
    record.model = values.get('model', '')
    record.certificate_no = values.get('certificate_no', '')
    record.environment = values.get('environment', '')
    record.conclusion = values.get('conclusion', '') or ''
    record.columns = values.get('columns', [])
    record.rows = values.get('rows', [])
    record.field_values = values.get('field_values') or {}
    history_entry = {
        'when': timezone.now().isoformat(timespec='seconds'),
        'who': request.user.username,
        'reason': reason if not created else 'Certificate uploaded',
    }
    record.change_history = list(record.change_history or []) + [history_entry]
    record.save()
    return record, None


@_admin_required
def save_certificate(request):
    if request.method != 'POST':
        return redirect('equipment_log_upload')
    staged, data = _upload_path(request)
    if staged is None or not data.get('token'):
        _toast(request, 'error', 'No certificate is staged. Start again.')
        return redirect('equipment_log_upload')
    template = get_object_or_404(EquipmentCertificateTemplate, pk=data.get('template_id'))
    values = _values_from_post(request, template)
    serial = (values.get('serial_no') or '').strip()
    record, error = _save_record(request, template, values,
                                 reason='Certificate re-uploaded (overwrote previous record)')
    if error:
        _toast(request, 'error', error)
        return redirect('equipment_log_review')
    asset = _equipment_match(serial) if serial else None
    updated_asset = False
    if asset is not None:
        test_date = record.test_date
        due_date = record.due_date or add_months(test_date, asset.calibration_frequency)
        asset.last_calibrated = test_date
        asset.calibration_due_date = due_date
        if record.certificate_no:
            asset.certificate_no = record.certificate_no
        if asset.status != 'inactive':
            asset.status = 'active'
        asset.save()
        updated_asset = True
    service.audit(request.user, None, 'equipment_certificate_saved',
                  after={'record': record.pk, 'equipment': getattr(asset, 'pk', None),
                         'serial': record.serial_no, 'year': record.year})
    _clear_upload(request)
    if updated_asset:
        _toast(request, 'success', f'Saved to the log and Lab Equipment updated for {serial}.')
    else:
        _toast(request, 'success', f'Saved to the log. No Lab Equipment row matches {serial}; it was left unchanged.')
    return redirect('%s?serial=%s' % (
        reverse('equipment_log_type', kwargs={'year': record.year, 'template_pk': template.pk}),
        record.serial_no))


# ----------------------------------------------------- log: years, types

@_admin_required
def year_view(request, year):
    year = int(year)
    records = EquipmentCertificateRecord.objects.filter(year=year)
    types = list(records.values('template', 'template_name')
                 .annotate(serials=Count('serial_no', distinct=True))
                 .order_by('template_name'))
    return render(request, 'core/equipment_logs/year.html', {
        'year': year,
        'types': types,
        'page_title': f'Equipment Logs {year}',
    })


@_admin_required
def type_view(request, year, template_pk):
    year = int(year)
    template = get_object_or_404(EquipmentCertificateTemplate, pk=template_pk)
    records = list(EquipmentCertificateRecord.objects.filter(year=year, template=template).order_by('serial_no'))
    selected_serial = request.GET.get('serial')
    selected = None
    for record in records:
        if record.serial_no == (selected_serial or '').upper() or (selected is None and not selected_serial):
            selected = record
            break
    unlock_flag = f'equipment_log_unlock_{template.pk}_{year}_{selected.pk}' if selected else None
    unlock = bool(request.session.get(unlock_flag)) if selected else False
    sheet_html = ''
    if selected:
        with template.original_file.open('rb') as handle:
            ws = load_sheet(handle, None)
            sheet_html = render_sheet(
                ws, editable=unlock,
                values={'activities': selected.field_values or {},
                        'rows': selected.rows or [],
                        'columns': list(template.columns or [])},
            )
    return render(request, 'core/equipment_logs/type.html', {
        'year': year,
        'template': template,
        'records': records,
        'selected': selected,
        'unlock': unlock,
        'activity_pairs': _activity_pairs(list(template.activities or []), selected.field_values) if selected else [],
        'sheet_html': sheet_html,
        'page_title': f'{template.name} · {year}',
    })


@_admin_required
def unlock_record(request, record_pk):
    if request.method != 'POST':
        raise Http404()
    record = get_object_or_404(EquipmentCertificateRecord, pk=record_pk)
    reason = (request.POST.get('reason') or '').strip()
    if not reason:
        _toast(request, 'error', 'A reason is required to edit a saved record.')
    else:
        request.session[f'equipment_log_unlock_{record.template_id}_{record.year}_{record.pk}'] = True
        request.session[f'equipment_log_reason_{record.pk}'] = reason
        request.session.modified = True
        _toast(request, 'info', 'Editing unlocked. Remember: every change is recorded.')
    return redirect('%s?serial=%s' % (
        reverse('equipment_log_type', kwargs={'year': record.year, 'template_pk': record.template_id}),
        record.serial_no))


@_admin_required
def update_record(request, record_pk):
    if request.method != 'POST':
        raise Http404()
    record = get_object_or_404(EquipmentCertificateRecord, pk=record_pk)
    flag = f'equipment_log_unlock_{record.template_id}_{record.year}_{record.pk}'
    if not request.session.get(flag):
        _toast(request, 'error', 'The record is locked. State a reason to edit it.')
        return redirect('equipment_log_type', year=record.year, template_pk=record.template_id)
    template = record.template
    values = _values_from_post(request, template)
    reason = request.session.get(f'equipment_log_reason_{record.pk}', 'Edited')
    record.model = values.get('model', '')
    record.certificate_no = values.get('certificate_no', '')
    record.environment = values.get('environment', '')
    test_date = _parse_iso_date(values.get('test_date'))
    if test_date:
        record.test_date = test_date
    record.due_date = _parse_iso_date(values.get('due_date'))
    if values.get('conclusion') in ('pass', 'fail', ''):
        record.conclusion = values['conclusion']
    record.columns = values.get('columns', record.columns)
    record.rows = values.get('rows', record.rows)
    record.field_values = values.get('field_values', record.field_values)
    record.change_history = list(record.change_history or []) + [{
        'when': timezone.now().isoformat(timespec='seconds'),
        'who': request.user.username,
        'reason': reason,
    }]
    record.save()
    request.session.pop(flag, None)
    request.session.pop(f'equipment_log_reason_{record.pk}', None)
    service.audit(request.user, None, 'equipment_certificate_edited',
                  after={'record': record.pk, 'reason': reason})
    _toast(request, 'success', 'Record updated and history logged.')
    return redirect('%s?serial=%s' % (
        reverse('equipment_log_type', kwargs={'year': record.year, 'template_pk': record.template_id}),
        record.serial_no))


# ----------------------------------------------------- downloads

def _safe_filename(name):
    return re.sub(r'[\\/:*?"<>|]+', ' ', str(name)).strip() or 'download'


def _sheet_title(workbook, name):
    clean = re.sub(r'[\[\]:*?/\\]', ' ', str(name))[:31].strip() or 'Sheet'
    title, index = clean, 2
    while title in workbook.sheetnames:
        suffix = f' ({index})'
        title = (clean[:31 - len(suffix)] + suffix).strip()
        index += 1
    return title


def _record_sheet(workbook, record):
    template = record.template
    sheet = workbook.create_sheet(_sheet_title(workbook, record.serial_no or 'serial'))
    sheet.append(['Equipment Log — certificate record'])
    sheet.append([])
    if record.field_values and (template and template.activities):
        sheet.append(['LAB GENERAL ACTIVITIES LOG'])
        for label in template.activities:
            sheet.append([label, record.field_values.get(slugify(label), '')])
        sheet.append([])
    sheet.append(['TEST DATA'])
    if record.columns:
        sheet.append(list(record.columns))
        for row in record.rows or []:
            sheet.append(list(row))
    sheet.append([])
    sheet.append(['Conclusion', record.get_conclusion_display() if record.conclusion else ''])
    for col in sheet.columns:
        width = max(len(str(cell.value or '')) for cell in col) + 2
        sheet.column_dimensions[col[0].column_letter].width = min(width, 60)
    return sheet


def _xlsx_response(workbook, filename):
    from django.http import HttpResponse
    import io
    buffer = io.BytesIO()
    workbook.save(buffer)
    response = HttpResponse(buffer.getvalue(),
                            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="%s"' % _safe_filename(filename)
    return response


@_admin_required
def download_record(request, record_pk):
    record = get_object_or_404(EquipmentCertificateRecord, pk=record_pk)
    workbook = Workbook()
    workbook.remove(workbook.active)
    _record_sheet(workbook, record)
    return _xlsx_response(workbook, f'{record.template_name} {record.year} {record.serial_no}.xlsx')


@_admin_required
def download_type(request, year, template_pk):
    year = int(year)
    template = get_object_or_404(EquipmentCertificateTemplate, pk=template_pk)
    workbook = Workbook()
    workbook.remove(workbook.active)
    records = EquipmentCertificateRecord.objects.filter(year=year, template=template).order_by('serial_no')
    if not records:
        sheet = workbook.create_sheet('Empty')
        sheet.append(['No certificates recorded for', template.name, year])
    for record in records:
        _record_sheet(workbook, record)
    return _xlsx_response(workbook, f'{template.name} Certificates Log {year}.xlsx')


@_admin_required
def download_year(request, year):
    year = int(year)
    workbook = Workbook()
    workbook.remove(workbook.active)
    records = EquipmentCertificateRecord.objects.filter(year=year).order_by('template_name', 'serial_no')
    if not records:
        sheet = workbook.create_sheet('Empty')
        sheet.append(['No certificates recorded for', year])
    for record in records:
        _record_sheet(workbook, record)
    return _xlsx_response(workbook, f'Equipment Certificates Log {year}.xlsx')


# ----------------------------------------------------- templates folder

@_admin_required
def templates_folder(request):
    templates = EquipmentCertificateTemplate.objects.annotate(
        records_count=Count('records')).order_by('name')
    return render(request, 'core/equipment_logs/templates.html', {
        'templates': templates,
        'page_title': 'Certificate Templates',
    })


@_admin_required
def upload_template(request):
    if request.method == 'POST':
        file = request.FILES.get('template')
        name = (request.POST.get('name') or '').strip()
        if not file or not (file.name or '').lower().endswith('.xlsx'):
            _toast(request, 'error', 'Choose an .xlsx template file.')
            return redirect('equipment_log_template_upload')
        if file.size > MAX_UPLOAD_BYTES:
            _toast(request, 'error', 'File is larger than 20 MB.')
            return redirect('equipment_log_template_upload')
        if not name:
            name = Path(file.name).stem
        _clear_upload(request)
        token = uuid.uuid4().hex
        TMP_DIR.mkdir(parents=True, exist_ok=True)
        staged_path = TMP_DIR / (token + '.xlsx')
        with staged_path.open('wb') as handle:
            for chunk in file.chunks():
                handle.write(chunk)
        _stash_upload(request, template_token=token, template_name=name, filename=file.name)
        return redirect('equipment_log_template_confirm')
    return render(request, 'core/equipment_logs/template_upload.html', {
        'page_title': 'Upload template',
    })


def _template_staged(request):
    data = request.session.get(SESSION_KEY) or {}
    token = data.get('template_token')
    if not token:
        return None, data
    staged = TMP_DIR / (re.sub(r'[^a-f0-9]', '', str(token).lower()) + '.xlsx')
    if not staged.is_file():
        return None, data
    return staged, data


@_admin_required
def template_confirm(request):
    staged, data = _template_staged(request)
    if staged is None or not data.get('template_token'):
        _toast(request, 'error', 'Upload a template first.')
        return redirect('equipment_log_template_upload')

    if request.method == 'POST':
        name = (request.POST.get('name') or data.get('template_name') or '').strip()
        selected = set(request.POST.getlist('include'))
        parse = parse_sheet(str(staged), request.POST.get('sheet') or None)
        activities, columns = [], []
        for index, candidate in enumerate(parse['candidates']):
            if str(index) not in selected:
                continue
            if candidate['type'] == 'fields':
                activities.extend(candidate['labels'])
            elif candidate['type'] == 'table':
                columns = candidate['columns']
        if not activities and not columns:
            _toast(request, 'error', 'Include at least one activities block or the test-data table.')
            return redirect('equipment_log_template_confirm')
        if EquipmentCertificateTemplate.objects.filter(name__iexact=name).exists():
            _toast(request, 'error', f'A template named "{name}" already exists.')
            return redirect('equipment_log_template_confirm')
        template = EquipmentCertificateTemplate(
            name=name,
            activities=activities,
            columns=columns,
            original_name=data.get('filename') or 'template.xlsx',
            **service.actor_fields(request.user),
        )
        with staged.open('rb') as handle:
            from django.core.files import File
            template.original_file.save(data.get('filename') or 'template.xlsx', File(handle), save=True)
        service.audit(request.user, None, 'equipment_template_uploaded',
                      after={'template': template.pk, 'name': template.name,
                             'activities': activities, 'columns': columns})
        sheet, activities_count = parse['sheet'], len(activities)
        _clear_upload(request)
        _toast(request, 'success', f'Template "{name}" saved: {activities_count} activity fields, {len(columns)} test-data columns.')
        return redirect('equipment_log_templates')

    sheet_name = request.GET.get('sheet')
    parse = parse_sheet(str(staged), sheet_name)
    with staged.open('rb') as handle:
        ws = load_sheet(handle, None)
        sheet_html = render_sheet(ws, editable=False)
    return render(request, 'core/equipment_logs/template_confirm.html', {
        'sheets': parse['sheets'],
        'sheet': parse['sheet'],
        'candidates': parse['candidates'],
        'preview_rows': parse['preview_rows'],
        'sheet_html': sheet_html,
        'default_name': data.get('template_name') or Path(data.get('filename') or 'template').stem,
        'page_title': 'Review what was detected',
    })


@_admin_required
def template_delete(request, template_pk):
    if request.method != 'POST':
        raise Http404()
    template = get_object_or_404(EquipmentCertificateTemplate, pk=template_pk)
    record_count = template.records.count()
    if template.original_file:
        template.original_file.delete(save=False)
    template.records.all().delete()
    name = template.name
    template.delete()
    service.audit(request.user, None, 'equipment_template_deleted',
                  after={'name': name, 'records_deleted': record_count})
    _toast(request, 'info', f'Deleted template "{name}" with {record_count} log record(s).')
    return redirect('equipment_log_templates')
