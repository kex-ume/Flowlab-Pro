"""Smoke-test a frozen bundle using disposable databases, never production data."""
import json
from contextlib import closing
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

bundle = Path(sys.argv[1]).resolve()
exe = bundle / 'EATL-Integrated-Lab.exe'
if not exe.is_file():
    raise SystemExit('Executable not found: ' + str(exe))
environment = dict(os.environ)
for key in ('FLOWLAB_DATABASE_URL', 'EI_LAB_DATABASE_URL', 'DATABASE_URL', 'PYTHONPATH', 'PYTHONHOME'):
    environment[key] = ''
environment.update(EI_LAB_FORCE_SQLITE='1', EATL_NO_BROWSER='1', EATL_NO_DIALOG='1', DJANGO_SETTINGS_MODULE='jobrec.settings')
with tempfile.TemporaryDirectory(prefix='eatl-frozen-check-') as temporary:
    data = Path(temporary) / 'data'
    environment['EATL_RUNTIME_ROOT'] = temporary
    import socket
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0))
        test_port=probe.getsockname()[1]
    process = subprocess.Popen([str(exe),'--port',str(test_port)], env=environment, cwd=bundle)
    try:
        deadline = time.monotonic() + 60
        while True:
            if process.poll() is not None:
                error = Path(temporary) / 'startup-error.log'
                raise RuntimeError('Frozen server stopped: ' + str(process.returncode) + ('\n' + error.read_text() if error.exists() else ''))
            try:
                status = json.loads((Path(temporary) / 'runtime-status.json').read_text())
                server_url = status['url'].rstrip('/')
                with urlopen(server_url + '/', timeout=2) as response:
                    assert response.status == 200
                break
            except (OSError, json.JSONDecodeError):
                if time.monotonic() > deadline:
                    raise RuntimeError('Frozen server did not become ready.')
                time.sleep(.5)
        checked_routes = []
        for path, expected in (
            ('/', b'EATL'), ('/login', b'<form'), ('/ei-lab/login/', b'<form'),
            ('/ei-lab/static/core/ei-module-theme.css', b'ei-env-trends'),
            ('/ei-lab/static/core/ei-workflow.js', b'function'),
        ):
            with urlopen(server_url + path, timeout=15) as response:
                content = response.read()
                assert response.status == 200 and expected in content, path
            checked_routes.append(path)
        # A second launch must not replace the already-installed database.
        import sqlite3
        # Authenticated Settings smoke checks use a synthetic identity in this
        # disposable copy only; no deployed account/password is modified.
        import hashlib
        import uuid
        import http.cookiejar
        import re
        from urllib.parse import urlencode
        from urllib.request import build_opener, HTTPCookieProcessor, Request
        username='bundlecheck_'+uuid.uuid4().hex[:12]
        password=uuid.uuid4().hex+'Aa!'
        with closing(sqlite3.connect(data / 'eatl.sqlite3')) as connection:
            role=connection.execute("SELECT id FROM roles WHERE name='Administrator'").fetchone()[0]
            connection.execute('INSERT INTO users(username,password_hash,full_name,role_id,is_active,must_change_password) VALUES(?,?,?,?,1,0)',(username,hashlib.sha256(password.encode()).hexdigest(),'Disposable Bundle Check',role))
            connection.commit()
        jar=http.cookiejar.CookieJar()
        browser=build_opener(HTTPCookieProcessor(jar))
        with browser.open(server_url+'/login',data=urlencode({'username':username,'password':password}).encode(),timeout=30) as response:
            content=response.read().decode(errors='replace')
            assert response.status==200 and '/login' not in response.url, 'Flow login redirected to '+response.url+'; invalid credentials='+str('Username or password is invalid' in content)+'; cookie names='+str([cookie.name for cookie in jar])
        for path in ('/settings','/workspace/settings','/settings/users','/settings/records','/recycle-bin',
                     '/environment','/personnel/register','/analytics/calibration','/analytics/uncertainty',
                     '/analytics/cmc','/analytics/equipment','/analytics/capa','/analytics/audit-pt',
                     '/tools/decision-rule','/tools/generate-cover'):
            with browser.open(server_url+path,timeout=30) as response:
                markup=response.read().lower()
                assert response.status==200 and b'<!doctype' in markup,path
                assert b'aria-label="breadcrumb"' in markup,path
                assert b'aria-current="page"' in markup,path
            checked_routes.append(path)
        with browser.open(server_url+'/settings',data=urlencode({'equipment_due_soon_days':'30','admin_recovery_email':'disposable@example.test'}).encode(),timeout=30) as response:
            assert response.status==200 and b'Settings saved' in response.read()
        with browser.open(server_url+'/ei-lab/login/',timeout=30) as response:
            html=response.read().decode()
        csrf=re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"',html).group(1)
        form=urlencode({'username':username,'password':password,'csrfmiddlewaretoken':csrf}).encode()
        with browser.open(Request(server_url+'/ei-lab/login/',data=form,headers={'Referer':server_url+'/ei-lab/login/'}),timeout=30) as response:
            assert response.status==200 and '/login' not in response.url
        for path in ('/ei-lab/','/ei-lab/jobs/','/ei-lab/personnel/','/ei-lab/equipment/',
                     '/ei-lab/equipment/programme/','/ei-lab/environment/','/ei-lab/capa/',
                     '/ei-lab/records/retained/','/ei-lab/procedures/','/ei-lab/settings/',
                     '/ei-lab/settings/company/','/ei-lab/settings/scopes/','/ei-lab/settings/roles/','/ei-lab/settings/permissions/'):
            with browser.open(server_url+path,timeout=30) as response:
                assert response.status==200,path
                markup=response.read()
                assert b'aria-label="Breadcrumb"' in markup and b'aria-current="page"' in markup,path
            checked_routes.append(path)
        # A Chief must receive E&I management controls, not dead-end global-admin links.
        with browser.open(server_url+'/settings/users',timeout=30) as response:
            users_page=response.read().decode()
        admin_token=re.search(r'name="_admin_csrf" value="([^"]+)"',users_page).group(1)
        with closing(sqlite3.connect(data/'eatl.sqlite3')) as local:
            chief_role=local.execute("SELECT id FROM core_role WHERE name='Chief Metrologist'").fetchone()[0]
        chief_username='chiefcheck_'+uuid.uuid4().hex[:10]
        chief_password=uuid.uuid4().hex+'Aa!'
        with browser.open(server_url+'/settings/users',data=urlencode({'action':'ei_create','_admin_csrf':admin_token,
            'username':chief_username,'full_name':'Disposable Chief Check','email':'chief@example.test',
            'role_id':chief_role,'password':chief_password}).encode(),timeout=30) as response:
            assert response.status==200 and chief_username.encode() in response.read(),'Chief account creation failed'
        chief_browser=build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
        with chief_browser.open(server_url+'/ei-lab/login/',timeout=30) as response:
            login_page=response.read().decode()
        chief_csrf=re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"',login_page).group(1)
        with chief_browser.open(Request(server_url+'/ei-lab/login/',data=urlencode({'username':chief_username,
            'password':chief_password,'csrfmiddlewaretoken':chief_csrf}).encode(),
            headers={'Referer':server_url+'/ei-lab/login/'}),timeout=30) as response:
            assert response.status==200 and '/login' not in response.url
        for path in ('/ei-lab/','/ei-lab/settings/','/ei-lab/settings/roles/','/ei-lab/personnel/'):
            with chief_browser.open(server_url+path,timeout=30) as response:
                chief_page=response.read()
                assert response.status==200 and b'href="/settings/users"' not in chief_page,path
                assert b'href="/settings/records"' not in chief_page,path
            checked_routes.append('Chief '+path)
        with closing(sqlite3.connect(data/'eatl.sqlite3')) as local:
            existing_job=local.execute('SELECT id FROM core_job WHERE workflow_managed=1 AND administratively_archived=0 ORDER BY id LIMIT 1').fetchone()
        if existing_job:
            path=f'/ei-lab/jobs/{existing_job[0]}/'
            with chief_browser.open(server_url+path,timeout=30) as response: assert response.status==200
            checked_routes.append('Chief job record '+path)
        with closing(sqlite3.connect(data / 'eatl.sqlite3')) as connection:
            connection.execute('CREATE TABLE portable_smoke_marker(value TEXT)')
            connection.execute("INSERT INTO portable_smoke_marker VALUES ('retained')")
            connection.commit()
        duplicate = subprocess.run([str(exe)], env=environment, cwd=bundle, timeout=60)
        assert duplicate.returncode == 0
        with closing(sqlite3.connect(data / 'eatl.sqlite3')) as connection:
            assert connection.execute('SELECT value FROM portable_smoke_marker').fetchone()[0] == 'retained'
            assert connection.execute('SELECT COUNT(*) FROM auth_user').fetchone()[0] > 0
            assert connection.execute('SELECT COUNT(*) FROM users').fetchone()[0] > 0
        checked = subprocess.run([str(exe), '--check-deployment'], env=environment, cwd=bundle, timeout=60)
        assert checked.returncode == 0
        report = json.loads((Path(temporary) / 'deployment-check.json').read_text())
        assert report['database_vendor'] == 'sqlite'
        # Exercise update-in-place from the previous deployed schema, not only first install.
        previous = Path(__file__).resolve().parents[1] / 'release' / 'SQLite-Snapshot-20261015' / 'data' / 'eatl.sqlite3'
        if previous.is_file():
            upgrade_root=Path(temporary)/'previous-installation'
            upgrade_data=upgrade_root/'data'; upgrade_data.mkdir(parents=True)
            upgrade_db=upgrade_data/'eatl.sqlite3'
            with closing(sqlite3.connect(previous)) as old, closing(sqlite3.connect(upgrade_db)) as target:
                old.backup(target)
                before_accounts=target.execute('SELECT id,username,password_hash FROM users ORDER BY id').fetchall()
                target.execute('CREATE TABLE update_preservation_marker(value TEXT)')
                target.execute("INSERT INTO update_preservation_marker VALUES ('keep-existing-data')")
                target.commit()
            upgraded_env=dict(environment,EATL_RUNTIME_ROOT=str(upgrade_root))
            upgraded=subprocess.run([str(exe),'--prepare-database'],env=upgraded_env,cwd=bundle,timeout=120)
            if upgraded.returncode:
                problem=upgrade_root/'startup-error.log'
                if problem.is_file(): print('Upgrade startup details:\n'+problem.read_text(encoding='utf8',errors='replace'))
            assert upgraded.returncode==0,'Previous-installation schema update failed'
            assert subprocess.run([str(exe),'--check-deployment'],env=upgraded_env,cwd=bundle,timeout=120).returncode==0
            with closing(sqlite3.connect(upgrade_db)) as upgraded_db:
                assert upgraded_db.execute('SELECT id,username,password_hash FROM users ORDER BY id').fetchall()==before_accounts
                assert upgraded_db.execute('SELECT value FROM update_preservation_marker').fetchone()[0]=='keep-existing-data'
                assert upgraded_db.execute("SELECT name FROM django_migrations WHERE app='core' AND name='0056_job_supervisor_review'").fetchone()
                assert upgraded_db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='flow_environment_readings'").fetchone()
            checked_routes.append('previous-installation upgrade: accounts, passwords and data retained')
        verification={'status':'passed','executable':str(exe),'sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),
            'routes':checked_routes,'database':'embedded SQLite snapshot installed in disposable runtime; repeated launch preserves data; previous-schema upgrade preserves accounts, passwords and custom data'}
        (bundle/'executable-verification.json').write_text(json.dumps(verification,indent=2),encoding='utf8')
        import zipfile
        with zipfile.ZipFile(bundle/'EATL-SQLite-Windows.zip','a',zipfile.ZIP_DEFLATED) as archive:
            archive.write(bundle/'executable-verification.json','executable-verification.json')
        print(json.dumps(verification,indent=2))
    except Exception:
        for filename in ('runtime.log','runtime-console.log','startup-error.log'):
            log=Path(temporary)/filename
            if log.is_file():
                print(filename+':\n'+log.read_text(encoding='utf-8',errors='replace')[-12000:])
        raise
    finally:
        if process.poll() is None:
            # One-file executables have an extraction parent and server child.
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
        process.wait(timeout=15)
