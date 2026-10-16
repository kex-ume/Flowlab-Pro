"""Windows launcher for the packaged FlowLab Pro application."""

from __future__ import annotations

import os
import argparse
import json
import hashlib
import logging
from pathlib import Path
import socket
import shutil
import sys
import threading
import time
import traceback
import webbrowser


HOST = "127.0.0.1"
FLOWLAB_PORT = 5050
BUILD_ID = '20261016-monitoring-analytics-ei-authority-r2'


def load_configuration(root: Path) -> None:
    """Load deployment values without requiring a Python environment."""
    config = root / "configuration.env"
    if not config.is_file():
        return
    for raw_line in config.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def install_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def runtime_directory() -> Path:
    configured = os.environ.get('EATL_RUNTIME_ROOT')
    if configured:
        return Path(configured).resolve()
    if getattr(sys, 'frozen', False):
        return Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'EATL-Integrated-Lab'
    return install_directory()


def seed_sqlite_data(data_root: Path) -> None:
    """Install embedded records once; never replace an existing user's DB."""
    if (data_root / 'eatl.sqlite3').is_file():
        return
    embedded = Path(getattr(sys, '_MEIPASS', install_directory())) / 'seed-data'
    if not (embedded / 'eatl.sqlite3').is_file():
        return
    if data_root.exists() and any(data_root.iterdir()):
        raise RuntimeError('The data folder contains files but its eatl.sqlite3 database is missing. Restore the database or choose a new empty EATL_RUNTIME_ROOT; existing files were not overwritten.')
    import sqlite3
    import uuid
    staging = data_root.with_name(data_root.name + '-initializing-' + uuid.uuid4().hex[:8])
    shutil.copytree(embedded, staging)
    connection = sqlite3.connect(staging / 'eatl.sqlite3')
    try:
        if connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('The embedded SQLite database failed its integrity check.')
    finally:
        connection.close()  # SQLite context managers do not close handles on Windows.
    if data_root.exists():
        data_root.rmdir()  # Verified empty above; do not overwrite existing data.
    staging.rename(data_root)


def wait_for_port(port: int, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((HOST, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def open_application() -> None:
    if os.environ.get("EATL_NO_BROWSER", "").strip().lower() in {"1", "true", "yes"}:
        return
    if wait_for_port(FLOWLAB_PORT):
        webbrowser.open(f"http://{HOST}:{FLOWLAB_PORT}/")


def show_message(message: str, error: bool = True) -> None:
    if os.environ.get('EATL_NO_DIALOG') == '1':
        return
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, 'EATL Integrated Lab', 0x10 if error else 0x40)
    except Exception:
        pass


def acquire_instance(root: Path) -> bool:
    """A second double-click opens this installation's existing server."""
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.windll.kernel32
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    identity = hashlib.sha256(str(root).lower().encode()).hexdigest()[:24]
    handle = kernel.CreateMutexW(None, True, 'Local\\EATL-' + identity)
    if not handle:
        raise OSError('Could not create the application startup lock.')
    if kernel.GetLastError() == 183:
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle(handle)
        status = root / 'runtime-status.json'
        if status.is_file():
            saved = json.loads(status.read_text(encoding='utf-8'))
            if wait_for_port(int(saved['port']), timeout=2):
                if saved.get('build') != BUILD_ID:
                    show_message('An older EATL version is still running. Save your open work, end EATL-Integrated-Lab in Task Manager, then open this updated file again. Your database and uploaded files will be retained. The older app was not reopened.', error=False)
                    return False
                if os.environ.get('EATL_NO_BROWSER') != '1':
                    webbrowser.open(saved['url'])
                return False
        show_message('This installation is already starting. Please wait a moment and try again.', error=False)
        return False
    return True


def create_local_server(application, port):
    """Reserve an exclusive Windows listener; never reuse an older app's port."""
    from waitress import create_server
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):
            listener.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        else:
            listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        listener.bind((HOST,port))
        return create_server(application,sockets=[listener],threads=8)
    except Exception:
        listener.close()
        raise


def main() -> None:
    global FLOWLAB_PORT
    parser = argparse.ArgumentParser(description='EATL integrated laboratory deployment')
    parser.add_argument('--port', type=int, default=None)
    parser.add_argument('--prepare-database', action='store_true', help='Explicitly initialize FlowLab tables and apply E&I migrations; back up existing data first.')
    parser.add_argument('--check-deployment', action='store_true', help='Check packaged dependencies, resources and database migrations without starting the server.')
    args = parser.parse_args()
    if args.port is not None and not 1 <= args.port <= 65535:
        raise ValueError('Port must be between 1 and 65535.')
    FLOWLAB_PORT = args.port or 5050
    root = runtime_directory()
    root.mkdir(parents=True, exist_ok=True)
    os.chdir(root)
    # Windowed executables have no console streams; Django management commands
    # and some report libraries still write to stdout/stderr.
    if sys.stdout is None:
        sys.stdout = (root / 'runtime-console.log').open('a', encoding='utf-8', buffering=1)
    if sys.stderr is None:
        sys.stderr = sys.stdout
    logging.basicConfig(
        filename=root / "runtime.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )
    load_configuration(install_directory())
    # This deployment is deliberately SQLite-only, including on computers that
    # still have PostgreSQL URLs in their environment from the source app.
    os.environ.update(FLOWLAB_DATABASE_URL='', EI_LAB_DATABASE_URL='', DATABASE_URL='', EI_LAB_FORCE_SQLITE='1')
    os.environ['EATL_DATA_ROOT'] = str(root / 'data')
    data_root = Path(os.environ['EATL_DATA_ROOT']).resolve()
    if not args.check_deployment and not acquire_instance(root):
        return
    seed_sqlite_data(data_root)
    data_root.mkdir(parents=True, exist_ok=True)
    os.environ['DJANGO_DB_PATH'] = str(data_root / 'eatl.sqlite3')
    os.environ['DJANGO_MEDIA_ROOT'] = str(data_root / 'shared_files' / 'ei-lab')
    os.environ['EI_PRIVATE_STORAGE_ROOT'] = str(data_root / 'private' / 'ei-lab')
    os.environ.setdefault('DJANGO_DEBUG', '0')
    os.environ.setdefault('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost')
    os.environ.setdefault('DJANGO_SECURE_COOKIES', '0')
    # Stable, installation-specific secrets; never ship credentials in the bundle.
    import secrets
    secret_file = data_root / 'installation-secrets.json'
    if not secret_file.exists():
        with secret_file.open('x', encoding='utf-8') as handle:
            json.dump({'django': secrets.token_urlsafe(48), 'flask': secrets.token_urlsafe(48)}, handle)
    installation_secrets = json.loads(secret_file.read_text(encoding='utf-8'))
    os.environ.setdefault('DJANGO_SECRET_KEY', installation_secrets['django'])
    os.environ.setdefault('FLOWLAB_SECRET_KEY', installation_secrets['flask'])

    from app.database import database
    database.DATABASE_PATH = data_root / 'eatl.sqlite3'

    from app.database.init_db import initialize_database
    from integrated_app import application
    from integrated_app import flowlab_app
    from django.conf import settings
    flowlab_app.config['SESSION_COOKIE_NAME'] = 'eatl_portable_flowlab_session'
    settings.SESSION_COOKIE_NAME = 'eatl_portable_ei_session'
    settings.CSRF_COOKIE_NAME = 'eatl_portable_ei_csrf'
    from waitress import create_server
    from core.workflow_worker import start_worker
    from django.core.management import call_command
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connection)
    pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
    if pending and args.check_deployment and not args.prepare_database:
        raise RuntimeError('Database migrations are pending. Start the application normally to create a local backup and apply them.')
    if not args.check_deployment or args.prepare_database:
        if pending and database.DATABASE_PATH.exists():
            import sqlite3
            from datetime import datetime
            backup = data_root / 'backups' / ('before-upgrade-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.sqlite3')
            backup.parent.mkdir(exist_ok=True)
            from contextlib import closing
            with closing(sqlite3.connect(database.DATABASE_PATH)) as source, closing(sqlite3.connect(backup)) as destination:
                source.backup(destination)
        initialize_database()
        if pending:
            call_command('migrate', interactive=False, verbosity=0)
        connection.cursor().execute('PRAGMA journal_mode=WAL')
    if args.check_deployment or args.prepare_database:
        call_command('check', verbosity=0)
        from django.template.loader import get_template
        get_template('core/dashboard.html')
        get_template('core/equipment/assets.html')
        from integrated_app import ROOT
        for resource in ('templates/login.html', 'jobrec-review/core/static/core/ei-module-theme.css'):
            if not (ROOT / resource).is_file():
                raise RuntimeError('Missing packaged resource: ' + resource)
        (root / 'deployment-check.json').write_text(json.dumps({'status':'passed', 'database_vendor':connection.vendor, 'pending_migrations':0, 'port':FLOWLAB_PORT}, indent=2), encoding='utf-8')
        return

    if args.port is None:
        for port in range(5050, 5071):
            try:
                server = create_local_server(application,port)
                FLOWLAB_PORT = port
                break
            except OSError:
                continue
        else:
            raise RuntimeError('No free local port is available between 5050 and 5070.')
    else:
        server = create_local_server(application,FLOWLAB_PORT)
    (root / 'runtime-status.json').write_text(json.dumps({'port':FLOWLAB_PORT, 'url':f'http://{HOST}:{FLOWLAB_PORT}/', 'database':'SQLite','build':BUILD_ID,'pid':os.getpid()}), encoding='utf-8')
    threading.Thread(target=open_application, daemon=True).start()
    stop = start_worker()
    try:
        server.run()
    finally:
        stop.set()
        server.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        root = runtime_directory()
        error_text = traceback.format_exc()
        log_path = root / 'startup-error.log'
        try:
            log_path.write_text(error_text, encoding='utf-8')
        except OSError:
            log_path = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'EATL-Lab' / 'startup-error.log'
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(error_text, encoding='utf-8')
        show_message('The application could not start.\n\n' + str(sys.exc_info()[1]) + '\n\nError details: ' + str(log_path) + '\n\nCheck that your Windows user data folder is writable and there is enough free disk space. If a runtime file was quarantined, ask your IT administrator to review it.')
        sys.exit(1)
