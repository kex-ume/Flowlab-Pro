"""Windows service launcher for the packaged E&I Lab application."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys


HOST = "127.0.0.1"
PORT = 8000


def install_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1] / "jobrec-review"


def bundled_directory() -> Path:
    return Path(getattr(sys, "_MEIPASS", install_directory()))


def main() -> None:
    root = install_directory()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    data = root / "data"
    media = data / "media"
    data.mkdir(parents=True, exist_ok=True)
    media.mkdir(parents=True, exist_ok=True)

    database = data / "jobrec.db"
    seed = bundled_directory() / "seed" / "jobrec.db"
    if not database.exists() and seed.exists():
        shutil.copy2(seed, database)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobrec.settings")
    os.environ["DJANGO_DB_PATH"] = str(database)
    os.environ["DJANGO_MEDIA_ROOT"] = str(media)
    os.environ.setdefault("DJANGO_DEBUG", "True")
    os.chdir(root)

    import django
    django.setup()

    from django.contrib.staticfiles.handlers import StaticFilesHandler
    from jobrec.wsgi import application
    from waitress import serve

    serve(StaticFilesHandler(application), host=HOST, port=PORT, threads=8)


if __name__ == "__main__":
    main()
