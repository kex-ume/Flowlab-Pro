"""HTTP client for the OCR microservice."""

import logging
from urllib.parse import urljoin

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def get_ocr_url():
    return getattr(settings, 'OCR_SERVICE_URL', 'http://ocr:8000')


def ocr_extract(file_path):
    url = urljoin(get_ocr_url(), '/ocr/')
    try:
        with open(file_path, 'rb') as f:
            resp = requests.post(url, files={'file': f}, timeout=60)
        resp.raise_for_status()
        return resp.json()
    except requests.ConnectionError:
        logger.warning('OCR service unreachable at %s', url)
        return {'text': '', 'lines': [], 'error': 'OCR service unreachable', 'mock': True}
    except requests.Timeout:
        logger.warning('OCR service timed out')
        return {'text': '', 'lines': [], 'error': 'OCR service timed out', 'mock': True}
    except requests.RequestException as e:
        logger.exception('OCR request failed')
        return {'text': '', 'lines': [], 'error': str(e), 'mock': True}


def check_ocr_health():
    url = urljoin(get_ocr_url(), '/health/')
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return {'status': 'unreachable', 'ocr_available': False}
