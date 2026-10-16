"""Back up the active integrated database and uploaded records before upgrades."""
from datetime import datetime
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import integrated_app
from django.conf import settings


def main():
    root = Path(__file__).resolve().parents[1]
    target = root / 'data' / 'migration_backups' / ('ei_modernization_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    target.mkdir(parents=True, exist_ok=False)
    config = settings.DATABASES['default']
    if config['ENGINE'].endswith('postgresql'):
        dumper = Path(r'C:\Program Files\PostgreSQL\17\bin\pg_dump.exe')
        environment = os.environ.copy()
        environment['PGPASSWORD'] = config.get('PASSWORD', '')
        result = subprocess.run([str(dumper), '-h', config['HOST'], '-p', str(config['PORT'] or 5432),
                                 '-U', config['USER'], '-d', config['NAME'], '-Fc', '-f', str(target / 'integrated.pgdump')],
                                env=environment, capture_output=True)
        if result.returncode:
            raise RuntimeError('PostgreSQL backup failed; schema changes must not proceed.')
    paths = [root / 'data' / 'flowlab.db', root / 'jobrec-review' / 'db.sqlite3']
    for index, source in enumerate(paths):
        if source.exists():
            with sqlite3.connect(str(source)) as src, sqlite3.connect(str(target / f'sqlite_{index}.db')) as dest:
                src.backup(dest)
    directories = {root / 'data' / 'documents', root / 'data' / 'shared_files', Path(settings.MEDIA_ROOT), Path(settings.EI_PRIVATE_STORAGE_ROOT)}
    seen = set()
    with zipfile.ZipFile(target / 'uploaded_records.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for directory in directories:
            if directory.exists():
                for source in directory.rglob('*'):
                    if source.is_file() and source.resolve() not in seen:
                        seen.add(source.resolve())
                        archive.write(source, str(source.relative_to(root)))
    print(f'Backup saved: {target}')


if __name__ == '__main__':
    main()
