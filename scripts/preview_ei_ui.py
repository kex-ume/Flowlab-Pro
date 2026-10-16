"""Temporary, isolated copy of the same app for browser QA; never production data."""
import os
from pathlib import Path
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
temporary = tempfile.TemporaryDirectory(prefix='ei-ui-', dir=root / 'tmp')
os.chdir(temporary.name)
os.environ['FLOWLAB_DATABASE_URL'] = ''
os.environ['EI_LAB_DATABASE_URL'] = ''
os.environ['DATABASE_URL'] = ''
os.environ['EI_LAB_FORCE_SQLITE'] = '1'
os.environ['DJANGO_SETTINGS_MODULE'] = 'jobrec.test_settings'
os.environ['EI_TEST_DB_PATH'] = str(Path(temporary.name) / 'ei-test.db')
os.environ['EI_PRIVATE_STORAGE_ROOT'] = str(Path(temporary.name) / 'private')
os.environ['DJANGO_MEDIA_ROOT'] = str(Path(temporary.name) / 'media')
os.environ['EATL_DATA_ROOT'] = str(Path(temporary.name) / 'data')
from integrated_app import application
from django.conf import settings
settings.SESSION_COOKIE_NAME = 'ei_qa_sessionid'
settings.CSRF_COOKIE_NAME = 'ei_qa_csrftoken'
from django.core.management import call_command
from core.tests import IntegratedEIWorkflowTests
from core import ei_workflow as service
from waitress import serve

call_command('migrate', verbosity=0)
fixture = IntegratedEIWorkflowTests()
fixture.setUp()
fixture.draft()
fixture.approved_job()
lab = fixture.draft('lab', ('calibration', 'repair', 'calibration_repair'))
fixture.upload(lab, 'service_request'); fixture.upload(lab, 'waybill')
service.submit_job(fixture.user, lab)
print(f'Isolated UI instance: http://127.0.0.1:5051/ei-lab/jobs/ | Temporary data: {temporary.name}', flush=True)
try:
    serve(application, host='127.0.0.1', port=5051, threads=4)
finally:
    fixture.doCleanups()
    os.chdir(root)
    temporary.cleanup()
