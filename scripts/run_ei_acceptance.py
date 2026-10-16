"""Use the integrated runtime while keeping Django acceptance tests isolated."""
import os
from pathlib import Path
import sys
root = Path(__file__).resolve().parents[1]
for path in (root,root/'jobrec-review',root/'jobrec-review/.venv-jobrec/Lib/site-packages'):
    sys.path.insert(0,str(path))
os.environ['DJANGO_SETTINGS_MODULE']='jobrec.test_settings'
from django.core.management import execute_from_command_line
execute_from_command_line(['manage.py','test','core','--settings=jobrec.test_settings','--noinput','--verbosity=1'])
