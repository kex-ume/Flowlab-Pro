"""Verify copied attachments and exercise E&I views against an isolated copy."""
import hashlib
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
snapshot = Path(sys.argv[1]).resolve()
data = snapshot / 'data'
verified_files = 0
for copied in data.rglob('*'):
    if not copied.is_file() or copied.name == 'eatl.sqlite3':
        continue
    original = root / 'data' / copied.relative_to(data)
    if not original.is_file() or hashlib.sha256(original.read_bytes()).digest() != hashlib.sha256(copied.read_bytes()).digest():
        raise RuntimeError('Attachment copy verification failed; no release should be distributed.')
    verified_files += 1
with sqlite3.connect(data / 'eatl.sqlite3') as connection:
    assert connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    assert not connection.execute('PRAGMA foreign_key_check').fetchall()
with tempfile.TemporaryDirectory(prefix='eatl-sqlite-views-') as temporary:
    target = Path(temporary)
    shutil.copy2(data / 'eatl.sqlite3', target / 'copy.sqlite3')
    os.environ.update(FLOWLAB_DATABASE_URL='', EI_LAB_DATABASE_URL='', DATABASE_URL='', EI_LAB_FORCE_SQLITE='1', DJANGO_DB_PATH=str(target / 'copy.sqlite3'), EATL_DATA_ROOT=str(target / 'data'), DJANGO_SETTINGS_MODULE='jobrec.settings')
    from app.database import database
    database.DATABASE_PATH = target / 'copy.sqlite3'
    from integrated_app import application
    from django.test import Client
    from django.db import connections
    from core.models import Personnel
    from django.urls import reverse
    person = Personnel.objects.select_related('user').filter(user__is_active=True).first()
    assert person and person.user
    client = Client(HTTP_HOST='127.0.0.1')
    client.force_login(person.user)
    checked = []
    for name in ('dashboard', 'job_list', 'personnel_list', 'equipment_list', 'ei_calibration_programme', 'environment_list', 'ei_capa_list', 'ei_retained_records'):
        response = client.get(reverse(name))
        assert response.status_code in (200, 302, 403), (name, response.status_code)
        checked.append({'view': name, 'status': response.status_code})
    from web_app import app
    with closing(sqlite3.connect(target / 'copy.sqlite3')) as local:
        user = local.execute("SELECT u.id,u.username,u.full_name,r.name FROM users u JOIN roles r ON r.id=u.role_id WHERE u.is_active=1 ORDER BY CASE WHEN r.name='Administrator' THEN 0 ELSE 1 END,u.id LIMIT 1").fetchone()
    assert user
    browser = app.test_client()
    with browser.session_transaction() as session:
        session.update(user_id=user[0], username=user[1], full_name=user[2], role_name=user[3], must_change_password=False)
    for path in ('/dashboard','/projects/jobs','/equipment','/uncertainty','/iso17025/clause-checklist','/recycle-bin'):
        response = browser.get(path)
        assert response.status_code in (200, 302, 403), (path, response.status_code)
        checked.append({'view':'FlowLab ' + path,'status':response.status_code})
    connections.close_all()
report_path = snapshot / 'migration-verification.json'
report = json.loads(report_path.read_text())
report.update(attachment_sha256_verified=verified_files, sqlite_integrity='ok', foreign_key_violations=0, actual_account_view_checks=checked)
report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps({'verified_files': verified_files, 'sqlite_integrity':'ok', 'views':checked}, indent=2))
