"""Single-port WSGI entry point for FlowLab Pro and the E&I Lab.

FlowLab Pro remains the root application. The existing Django E&I Lab
is mounted at ``/ei-lab`` and retains its own database and authentication.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys

from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.middleware.shared_data import SharedDataMiddleware


ROOT = Path(__file__).resolve().parent
EI_ROOT = ROOT / "jobrec-review"
INSTALL_ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else ROOT


def _add_ei_lab_environment() -> None:
    """Make the existing E&I virtualenv and project importable in this process."""
    site_packages = EI_ROOT / ".venv-jobrec" / "Lib" / "site-packages"
    for path in (site_packages, EI_ROOT):
        value = str(path)
        if value not in sys.path:
            sys.path.insert(0, value)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobrec.settings")
    os.environ.setdefault("DJANGO_URL_PREFIX", "/ei-lab")
    os.environ.setdefault("EI_LAB_RUNTIME_ROOT", str(EI_ROOT))
    os.environ.setdefault("EATL_DATA_ROOT", str(INSTALL_ROOT / "data"))


def _not_found(environ, start_response):
    start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
    return [b"Not found"]


_add_ei_lab_environment()

from django.core.wsgi import get_wsgi_application  # noqa: E402
from django.conf import settings as django_settings  # noqa: E402
from web_app import app as flowlab_app  # noqa: E402

# A Flask-only server may have used another database with the generic cookie.
# Do not carry those old session IDs into the integrated database after upgrade.
flowlab_app.config['SESSION_COOKIE_NAME'] = 'eatl_integrated_flowlab_session'


ei_lab_app = get_wsgi_application()
ei_static_app = SharedDataMiddleware(
    _not_found,
    {"/": str(EI_ROOT / "core" / "static")},
)
ei_media_app = SharedDataMiddleware(
    _not_found,
    {"/": str(django_settings.MEDIA_ROOT)},
)

# DispatcherMiddleware removes the matching prefix from PATH_INFO and puts it
# in SCRIPT_NAME. Django therefore reverses its named URLs below /ei-lab while
# Flask continues to own the landing page and all FlowLab routes.
application = DispatcherMiddleware(
    flowlab_app,
    {
        "/ei-lab/static": ei_static_app,
        "/ei-lab/media": ei_media_app,
        "/ei-lab": ei_lab_app,
    },
)
