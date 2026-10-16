"""Run both-lab regression tests without connecting to production databases/files."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
import shutil


root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
with tempfile.TemporaryDirectory(prefix='eatl-regressions-') as temporary:
    shutil.copytree(root / 'static', Path(temporary) / 'static')
    shutil.copytree(root / 'data' / 'templates', Path(temporary) / 'data' / 'templates')
    os.chdir(temporary)
    os.environ['FLOWLAB_DATABASE_URL'] = ''
    os.environ['EI_LAB_DATABASE_URL'] = ''
    os.environ['DATABASE_URL'] = ''
    os.environ['EI_LAB_FORCE_SQLITE'] = '1'
    os.environ['DJANGO_SETTINGS_MODULE'] = 'jobrec.test_settings'
    os.environ['EI_PRIVATE_STORAGE_ROOT'] = str(Path(temporary) / 'private')
    os.environ['DJANGO_MEDIA_ROOT'] = str(Path(temporary) / 'media')
    import integrated_app
    from django.core.management import call_command
    call_command('migrate', verbosity=0)
    import app.database.database as database
    database.DATABASE_PATH = Path(temporary) / 'flowlab.db'
    suite = unittest.TestSuite()
    for pattern in (sys.argv[1:] or ['test_flow_monitoring.py', 'test_breadcrumbs.py', 'test_integrated_platform.py', 'test_uncertainty_engine.py', 'test_gum_uncertainty.py', 'test_web_uncertainty_workflow.py', 'test_equipment_web.py']):
        suite.addTests(unittest.defaultTestLoader.discover(str(root / 'tests'), pattern=pattern))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    os.chdir(root)
    sys.exit(0 if result.wasSuccessful() else 1)
