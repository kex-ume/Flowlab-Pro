"""Private E&I files are served only through permission checked Django views."""
from pathlib import Path
import uuid
from django.conf import settings
from django.core.files.storage import FileSystemStorage


def private_storage():
    return FileSystemStorage(location=settings.EI_PRIVATE_STORAGE_ROOT)


def private_upload(instance, filename):
    return f'{uuid.uuid4().hex}{Path(filename).suffix.lower()}'
