"""Serve the preserved original JobRec app locally on port 8000."""

import os
from pathlib import Path
import sys


project_root = Path(__file__).resolve().parents[1] / "jobrec-original"
os.chdir(project_root)
sys.path.insert(0, str(project_root))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobrec.settings")

from django.contrib.staticfiles.handlers import StaticFilesHandler  # noqa: E402
from jobrec.wsgi import application  # noqa: E402
from waitress import serve  # noqa: E402


if __name__ == "__main__":
    serve(StaticFilesHandler(application), host="127.0.0.1", port=8000, threads=8)
