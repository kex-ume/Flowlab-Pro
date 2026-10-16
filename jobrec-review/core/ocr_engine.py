"""OCR provider abstraction for E&I Lab.

Three tiers, chosen by ``OCR_PROVIDER`` (or auto-detection when ``auto``):

* ``paddle``  — HTTP client to the PaddleOCR FastAPI microservice
              (``ocr_service/app.py``). Use this on a host that can run the
              always-on service (VPS, local docker-compose, …). Unchanged.
* ``rapid``   — in-process RapidOCR via onnxruntime (same PP-OCR models), used
              on resource-constrained hosts like the PythonAnywhere free tier.
* ``mock``    — graceful no-crash fallback returning empty results.

The Django app never hard-imports the heavy engines at import time; each
backend is imported lazily only when selected / actually used, so the main
process stays light even when no engine is installed.
"""

import logging
from urllib.parse import urljoin

from django.conf import settings

from .ocr_client import ocr_extract, check_ocr_health

logger = logging.getLogger(__name__)


# ── helpers ───────────────────────────────────────────────────────────────────

def _norm_bbox(bbox):
    """Normalise a bbox from either engine into 4 [x, y] corner points."""
    if not bbox:
        return None
    pts = []
    if isinstance(bbox[0], (list, tuple)):
        pts = [list(p[:2]) for p in bbox[:4]]
    else:
        flat = list(bbox)
        if len(flat) >= 8:
            pts = [[flat[i], flat[i + 1]] for i in range(0, 8, 2)]
        else:
            return None
    if len(pts) != 4:
        return None
    return pts


def _x_center(bbox):
    pts = _norm_bbox(bbox)
    if not pts:
        return None
    return sum(p[0] for p in pts) / 4.0


def _y_top(bbox):
    pts = _norm_bbox(bbox)
    if not pts:
        return None
    return min(p[1] for p in pts)


# ── RapidOCR (in-process) ────────────────────────────────────────────────────

_rapid_engine = None


def _rapid_available():
    try:
        import rapidocr_onnxruntime  # noqa: F401
        return True
    except ImportError:
        return False


def _rapid_extract(file_path):
    """Run RapidOCR in-process. Returns a normalised result dict."""
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        return None

    global _rapid_engine
    if _rapid_engine is None:
        _rapid_engine = RapidOCR()

    try:
        lines, _elapse = _rapid_engine(file_path)
    except Exception as exc:  # model load / runtime failure
        logger.exception('RapidOCR extraction failed')
        return {'text': '', 'lines': [], 'provider': 'rapid',
                'mock': True, 'error': str(exc)}

    out_lines = []
    for ln in lines or []:
        bbox = ln[0] if len(ln) > 0 else None
        text = ln[1] if len(ln) > 1 else ''
        conf = float(ln[2]) if len(ln) > 2 else 0.0
        out_lines.append({
            'text': text,
            'confidence': conf,
            'bbox': _norm_bbox(bbox),
        })

    text = ' '.join(l['text'] for l in out_lines)
    return {'text': text, 'lines': out_lines, 'provider': 'rapid',
            'mock': False, 'error': None}


# ── PaddleOCR microservice (remote) ───────────────────────────────────────────

def _paddle_extract(file_path):
    """Forward to the PaddleOCR microservice via the existing HTTP client."""
    result = ocr_extract(file_path)
    result = dict(result)
    result.setdefault('provider', 'paddle')
    # Normalise line bboxes so the parser sees a single shape.
    lines = result.get('lines', []) or []
    norm = []
    for ln in lines:
        if isinstance(ln, dict):
            norm.append({
                'text': ln.get('text', ''),
                'confidence': float(ln.get('confidence', 0.0)),
                'bbox': _norm_bbox(ln.get('bbox')),
            })
    result['lines'] = norm
    return result


# ── Mock fallback ─�────────────────────────────────────────────────────────────

def _mock_extract(file_path):
    return {'text': '', 'lines': [], 'provider': 'mock',
            'mock': True, 'error': 'OCR service unreachable'}


# ── Engine ────────────────────────────────────────────────────────────────────

def provider_name():
    return getattr(settings, 'OCR_PROVIDER', 'auto')


def _paddle_reachable(timeout=3):
    if provider_name() not in ('paddle', 'auto'):
        return False
    try:
        health = check_ocr_health()
    except Exception:
        return False
    return getattr(health, 'get', lambda *a: False)('ocr_available', False) and not health.get('mock')


def available_engines():
    engines = []
    if provider_name() in ('paddle', 'auto') and _paddle_reachable():
        engines.append('paddle')
    if provider_name() in ('rapid', 'auto') and _rapid_available():
        engines.append('rapid')
    if provider_name() == 'mock' or not engines:
        engines.append('mock')
    return engines


def pick_provider():
    """Return the live provider: paddle > rapid > mock."""
    if provider_name() == 'paddle':
        return 'paddle' if _paddle_reachable() else 'mock'
    if provider_name() == 'rapid':
        return 'rapid' if _rapid_available() else 'mock'
    if provider_name() == 'mock':
        return 'mock'
    # auto
    if _paddle_reachable():
        return 'paddle'
    if _rapid_available():
        return 'rapid'
    return 'mock'


def extract(file_path):
    provider = pick_provider()
    if provider == 'paddle':
        return _paddle_extract(file_path)
    if provider == 'rapid':
        res = _rapid_extract(file_path)
        if res is not None:
            return res
    return _mock_extract(file_path)


def extract_upload(uploaded_file):
    """Accept a Django ``UploadedFile`` and run OCR on it (temp file)."""
    import os
    import tempfile
    suffix = os.path.splitext(uploaded_file.name or '')[1] or '.png'
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        for chunk in uploaded_file.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name
    try:
        return extract(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def health():
    provider = pick_provider()
    available = provider in ('paddle', 'rapid')
    return {
        'status': 'ok' if available else 'mock',
        'ocr_available': available,
        'provider': provider,
    }


def is_available():
    return health()['ocr_available']
