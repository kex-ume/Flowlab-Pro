"""Create a verified, private deployment snapshot without changing PostgreSQL."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    destination = args.destination.resolve()
    if destination.exists():
        raise SystemExit('Refusing to overwrite an existing snapshot directory.')
    source_url = os.environ.get('FLOWLAB_DATABASE_URL') or os.environ.get('DATABASE_URL', '')
    if not source_url.startswith(('postgresql://', 'postgres://')):
        raise SystemExit('The source PostgreSQL URL is not configured.')
    other_url = os.environ.get('EI_LAB_DATABASE_URL', '')
    if other_url and other_url != source_url:
        raise SystemExit('Separate PostgreSQL sources need a separate verified export; no data was changed.')
    destination.mkdir(parents=True)
    data = destination / 'data'
    data.mkdir()
    database_path = data / 'eatl.sqlite3'
    os.environ.update(FLOWLAB_DATABASE_URL='', EI_LAB_DATABASE_URL='', DATABASE_URL='', EI_LAB_FORCE_SQLITE='1', DJANGO_DB_PATH=str(database_path), EATL_DATA_ROOT=str(data), DJANGO_SETTINGS_MODULE='jobrec.settings')
    from app.database import database
    database.DATABASE_PATH = database_path
    from integrated_app import application
    from app.database.init_db import initialize_database
    from django.core.management import call_command
    from django.db import connections
    from app.database.sqlite_snapshot import copy_postgres
    initialize_database()
    call_command('migrate', interactive=False, verbosity=0)
    connections.close_all()
    report = copy_postgres(source_url, database_path)
    for folder in ('documents', 'shared_files', 'private', 'templates'):
        source = ROOT / 'data' / folder
        if source.is_dir():
            shutil.copytree(source, data / folder, dirs_exist_ok=True)
    report['snapshot_time'] = datetime.now().astimezone().isoformat(timespec='seconds')
    report['uploaded_files'] = sum(1 for path in data.rglob('*') if path.is_file() and path != database_path)
    (destination / 'migration-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'status': report['status'], 'tables': len(report['tables']), 'rows': report['total_rows'], 'uploaded_files': report['uploaded_files'], 'destination': str(destination)}))


if __name__ == '__main__':
    main()
