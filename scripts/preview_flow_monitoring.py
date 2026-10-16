"""Read-only UI preview using disposable records, never the live database."""
import os
from pathlib import Path
import sys
import tempfile
from datetime import date,timedelta

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
temporary=tempfile.TemporaryDirectory(prefix='flow-monitoring-ui-',dir=root/'tmp')
os.chdir(temporary.name)
os.environ.update(FLOWLAB_DATABASE_URL='',EI_LAB_DATABASE_URL='',DATABASE_URL='',EI_LAB_FORCE_SQLITE='1',
    DJANGO_SETTINGS_MODULE='jobrec.test_settings',EI_TEST_DB_PATH=str(Path(temporary.name)/'preview.db'))
import integrated_app
from django.core.management import call_command
call_command('migrate',verbosity=0)
from app.database import database
database.DATABASE_PATH=Path(temporary.name)/'preview.db'
from app.database.init_db import initialize_database
initialize_database()
from app.modules.flow_environment import save
connection=database.get_connection()
uid=connection.execute("INSERT INTO users(username,password_hash,full_name,role_id) SELECT 'previewchief','not-a-login','Preview Chief',id FROM roles WHERE name='Chief Metrologist'").lastrowid
for day in range(7):
    for slot,index in (('08:00',0),('12:00',1),('17:00',2)):
        save(connection,dict(record_date=(date.today()-timedelta(days=day)).isoformat(),record_time=slot,location='Flow Laboratory',
            temperature=str(23+(day%3)*.15+index*.1),humidity=str(48+(day%3)+index),instrument_used='ENV-PREVIEW'),uid,'Preview Chief')
for number,status in enumerate(('Planned','Planned','Ongoing','Completed','Completed','Draft'),1):
    connection.execute('INSERT INTO calibration_jobs(job_number,status,started_at,completed_at) VALUES (?,?,?,?)',
        (f'DEMO-JOB-{number:03}',status,'2026-10-01','2026-10-05' if status=='Completed' else None))
connection.commit(); connection.close()
from web_app import app
from flask import session,request,abort
app.config.update(TESTING=True,SESSION_COOKIE_NAME='flow_monitoring_preview_only')


@app.before_request
def preview_only():
    if request.method not in ('GET','HEAD'): abort(405)
    session.update(user_id=uid,role_name='Chief Metrologist',full_name='Preview Chief')


from waitress import serve
print('Read-only disposable preview: http://127.0.0.1:5353/environment',flush=True)
try: serve(app,host='127.0.0.1',port=5353,threads=2)
finally:
    os.chdir(root)
    from django.db import connections
    connections.close_all()
    temporary.cleanup()
