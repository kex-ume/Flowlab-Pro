"""OCR Microservice using PaddleOCR.

Endpoints:
  POST /ocr/          — Extract text from an image/PDF
  GET  /health/       — Health check
"""

import logging
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

try:
    from paddleocr import PaddleOCR

    ocr_engine = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    ocr_engine = None
    logger.warning('PaddleOCR not available — running in mock mode')

app = FastAPI(title='E&I Lab OCR Service', version='1.0.0')

ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.pdf'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@app.get('/health')
def health():
    return {
        'status': 'ok',
        'ocr_available': OCR_AVAILABLE,
    }


@app.post('/ocr/')
async def ocr_extract(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower() if file.filename else '.png'
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f'Unsupported file type: {ext}. Supported: {ALLOWED_EXTENSIONS}',
        )

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f'File too large. Max {MAX_FILE_SIZE // (1024*1024)} MB.',
        )

    if not OCR_AVAILABLE:
        return {
            'filename': file.filename,
            'text': 'OCR engine not available — running in mock mode.',
            'lines': [],
            'mock': True,
        }

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        result = ocr_engine.ocr(tmp_path, cls=True)
        lines = []
        full_text = []
        if result:
            for page in result:
                for line in page:
                    text = line[1][0]
                    confidence = line[1][1]
                    bbox = line[0]
                    lines.append({
                        'text': text,
                        'confidence': round(confidence, 4),
                        'bbox': [round(c, 1) for coord in bbox for c in coord],
                    })
                    full_text.append(text)
        return {
            'filename': file.filename,
            'text': '\n'.join(full_text),
            'lines': lines,
            'mock': False,
        }
    except Exception as e:
        logger.exception('OCR processing failed')
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        Path(tmp_path).unlink(missing_ok=True)
