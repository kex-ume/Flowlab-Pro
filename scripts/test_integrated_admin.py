"""End-to-end admin/password/archive checks on one disposable shared SQLite DB."""
from contextlib import closing
import os
from pathlib import Path
import sys
import tempfile
import time

root = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
class IsolatedDirectory(tempfile.TemporaryDirectory):
    def __exit__(self,*args):
        try:
            from django.db import connections
            connections.close_all()
        except ImportError:
            pass
        return super().__exit__(*args)

with IsolatedDirectory(prefix='eatl-admin-tests-') as temporary:
    target = Path(temporary)
    os.environ.update(FLOWLAB_DATABASE_URL='',EI_LAB_DATABASE_URL='',DATABASE_URL='',EI_LAB_FORCE_SQLITE='1',DJANGO_DB_PATH=str(target/'eatl.sqlite3'),EATL_DATA_ROOT=str(target/'data'),DJANGO_SETTINGS_MODULE='jobrec.settings',DJANGO_ALLOWED_HOSTS='127.0.0.1,localhost,testserver')
    from app.database import database
    database.DATABASE_PATH = target/'eatl.sqlite3'
    from integrated_app import application
    from django.core.management import call_command
    call_command('migrate',interactive=False,verbosity=0)
    from app.database.init_db import initialize_database
    initialize_database()
    from web_app import app
    from app.modules.auth.service import AuthService
    from django.test import Client as DjangoClient
    from django.urls import reverse
    from django.db import connections
    from core.models import Role,User,Personnel,AdminAccountLink,Client,AdministrativeArchive
    from core import ei_workflow
    checks = []
    def check(value, label):
        assert value, label
        checks.append(label)
    with closing(database.get_connection()) as connection:
        admin_role = connection.execute("SELECT id FROM roles WHERE name='Administrator'").fetchone()[0]
        connection.execute("INSERT INTO users(username,password_hash,full_name,email,role_id,is_active,must_change_password) VALUES(?,?,?,?,?,1,0)",('primaryadmin',AuthService.hash_password('Original-Strong-Secret-2026!'),'Primary Admin','admin@example.test',admin_role))
        connection.commit()
    browser = app.test_client()
    response = browser.post('/login',data={'username':'primaryadmin','password':'Original-Strong-Secret-2026!'})
    check(response.status_code==302,'FlowLab administrator login')
    check(AdminAccountLink.objects.count()==1,'Existing FlowLab administrator receives an explicit E&I link')
    def post(data):
        with browser.session_transaction() as session:
            token = session.get('_admin_csrf')
        response = browser.post('/settings/users',data={**data,'_admin_csrf':token})
        check(response.status_code==302,'Account action '+data['action']+' returns without a server error')
        return response
    response = browser.get('/settings/users')
    check(response.status_code==200,'User management renders in Settings')
    check(b'data-close-details' in response.data and b'_admin_csrf' in response.data,'Edit/reset forms include Close and CSRF controls')
    check(browser.post('/settings/users',data={'action':'create'}).status_code==400,'Account mutation rejects missing CSRF token')
    check(browser.get('/settings').status_code==200,'Settings administration links render')
    technician = Role.objects.create(name='Test Technician')
    started = time.perf_counter()
    post({'action':'ei_create','username':'technicalstaff','full_name':'Technical Staff','email':'staff@example.test','role_id':technician.pk,'password':'Temporary-Staff-2026!'})
    check(time.perf_counter()-started<5,'Shared SQLite account create does not wait for a competing writer')
    staff = User.objects.filter(username='technicalstaff').first()
    check(staff is not None,'E&I user and FlowLab audit commit together')
    post({'action':'ei_update','user_id':staff.pk,'full_name':'Updated Staff','email':'staff@example.test','role_id':technician.pk})
    staff.refresh_from_db()
    check(staff.get_full_name()=='Updated Staff','E&I edit saved')
    post({'action':'ei_reset_password','user_id':staff.pk,'password':'Updated-Staff-2026!'})
    staff.refresh_from_db()
    check(staff.check_password('Updated-Staff-2026!'),'E&I reset password saved')
    post({'action':'create','username':'sharedadmin','full_name':'Shared Admin','email':'shared@example.test','role_id':admin_role,'password':'Temporary-Shared-2026!'})
    linked = User.objects.get(username='sharedadmin')
    check(not linked.is_superuser,'Administrator assignment does not grant technical superuser privileges')
    person = Personnel.objects.get(user=linked)
    check(person.role.name=='Administrator' and person.authorizations.count()==0 and person.competencies.count()==0,'Admin role does not fabricate technical competence or authorization')
    ei = DjangoClient(HTTP_HOST='127.0.0.1')
    response = ei.post(reverse('login'),{'username':'sharedadmin','password':'Temporary-Shared-2026!'})
    check(response.status_code==302,'Same temporary admin password works in E&I')
    check('password/change' in ei.get(reverse('dashboard')).headers.get('Location',''),'Temporary shared password must be changed in E&I too')
    response = ei.post(reverse('password_change'),{'old_password':'Temporary-Shared-2026!','new_password1':'Fresh-Shared-Secret-2026!','new_password2':'Fresh-Shared-Secret-2026!'})
    check(response.status_code==302,'E&I password change succeeds')
    check(AuthService().authenticate('sharedadmin','Fresh-Shared-Secret-2026!') is not None,'E&I password change synchronizes FlowLab admin credentials')
    shared_browser = app.test_client()
    check(shared_browser.post('/login',data={'username':'sharedadmin','password':'Fresh-Shared-Secret-2026!'}).status_code==302,'Updated shared administrator login succeeds in FlowLab')
    shared_browser.get('/change-password')
    with shared_browser.session_transaction() as session:
        token = session['_admin_csrf']
    rejected = shared_browser.post('/change-password',data={'_admin_csrf':token,'current_password':'Incorrect-secret','password':'Rejected-Secret-2026!','password_confirmation':'Rejected-Secret-2026!','recovery_email':'shared@example.test'})
    check(b'Your current password is incorrect' in rejected.data,'Optional password change rejects an incorrect current password')
    response = shared_browser.post('/change-password',data={'_admin_csrf':token,'current_password':'Fresh-Shared-Secret-2026!','password':'FlowLab-Changed-Secret-2026!','password_confirmation':'FlowLab-Changed-Secret-2026!','recovery_email':'shared@example.test'})
    check(response.status_code==302 and response.headers['Location'].endswith('/login'),'FlowLab password change saves and requests new sign-in')
    linked.refresh_from_db()
    check(linked.check_password('FlowLab-Changed-Secret-2026!'),'FlowLab password change synchronizes E&I admin credentials')
    import hashlib
    recovery_token = 'disposable-recovery-token'
    with closing(database.get_connection()) as connection:
        flow_id = connection.execute('SELECT id FROM users WHERE username=?',('sharedadmin',)).fetchone()[0]
        connection.execute('INSERT INTO password_reset_tokens(user_id,token_hash,expires_at_epoch) VALUES(?,?,?)',(flow_id,hashlib.sha256(recovery_token.encode()).hexdigest(),int(time.time())+600))
        connection.commit()
    response = app.test_client().post('/reset-password/'+recovery_token,data={'password':'Recovered-Secret-2026!','password_confirmation':'Recovered-Secret-2026!'})
    check(response.status_code==302,'Email recovery works without a logged-in session')
    linked.refresh_from_db()
    check(linked.check_password('Recovered-Secret-2026!'),'Email recovery synchronizes linked E&I credentials')
    client = Client.objects.create(name='Placeholder Client')
    browser.get('/settings/records')
    with browser.session_transaction() as session:
        token = session['_admin_csrf']
    for action in ('archive','restore'):
        response = browser.post('/settings/records',data={'_admin_csrf':token,'kind':'ei_client','record_id':client.pk,'action':action,'reason':'Testing recoverable administrative cleanup'})
        check(response.status_code==302,'Administrative '+action+' succeeds')
        client.refresh_from_db()
        check(client.status==('inactive' if action=='archive' else 'active'),'Administrative '+action+' preserves the original record ID')
    from app.modules.record_maintenance import LABELS
    for kind in LABELS:
        check(browser.get('/settings/records?kind='+kind).status_code==200,'Maintenance list '+kind+' renders')
    check(AdministrativeArchive.objects.count()==1,'Cleanup retains archive history')
    legacy = User.objects.create_superuser(username='legacyreview',email='legacy@example.test',password='Legacy-Admin-Secret-2026!')
    Personnel.objects.create(user=legacy,name='Legacy Admin',role=technician,qualifications='',years_of_experience=0)
    check(AuthService().authenticate('legacyreview','Legacy-Admin-Secret-2026!') is not None,'Existing E&I administrator can sign into FlowLab with the same password')
    check(Personnel.objects.get(user=legacy).role_id==technician.pk,'Existing personnel role and technical records are not silently rebuilt')
    chief_role = Role.objects.create(name='Chief Meteorologist')
    chief = User.objects.create_user(username='chief-removal',password='Chief-Removal-2026!')
    Personnel.objects.create(user=chief,name='Chief Remover',role=chief_role,qualifications='',years_of_experience=0)
    chief_ei = DjangoClient(HTTP_HOST='127.0.0.1',enforce_csrf_checks=True)
    chief_ei.force_login(chief)
    from django.middleware.csrf import get_token
    from django.test import RequestFactory
    csrf_request=RequestFactory().get('/')
    csrf_token=get_token(csrf_request)
    chief_ei.cookies['eatl_ei_csrf']=csrf_request.META['CSRF_COOKIE']
    from django.conf import settings as django_settings
    chief_ei.cookies[django_settings.CSRF_COOKIE_NAME]=csrf_request.META['CSRF_COOKIE']
    from core.models import EnvironmentRecord
    environment=EnvironmentRecord.objects.create(date='2026-10-15',time='08',relative_humidity=50,temperature=23,recorded_by=chief)
    selection={'records':[{'kind':'ei_environment','id':environment.pk}],'reason':'Duplicate environmental observation'}
    import json
    check(chief_ei.post(reverse('ei_record_remove'),data=json.dumps(selection),content_type='application/json').status_code==403,'E&I removal requires CSRF protection')
    response=chief_ei.post(reverse('ei_record_remove'),data=json.dumps(selection),content_type='application/json',HTTP_X_CSRFTOKEN=csrf_token)
    check(response.status_code==200,'Chief can remove an environmental record')
    check(not EnvironmentRecord.objects.filter(pk=environment.pk).exists(),'Removed environmental record disappears from active queries')
    check(EnvironmentRecord._base_manager.filter(pk=environment.pk,temperature=23).exists(),'Original readings and identity remain stored')
    entry=AdministrativeArchive.objects.get(target_type='ei_environment',object_id=environment.pk)
    response=browser.get('/recycle-bin')
    check(response.status_code==200 and b'Master Recycle Bin' in response.data,'Administrator master recycle bin renders retained monthly records')
    with browser.session_transaction() as session: token=session['_admin_csrf']
    check(browser.post('/recycle-bin/retained/'+str(entry.pk)+'/restore',data={'_admin_csrf':token,'reason':'Restore verified original record'}).status_code==302,'Administrator can restore Chief removals')
    check(EnvironmentRecord.objects.filter(pk=environment.pk,temperature=23).exists(),'Restored record is active with the same ID and values')
    from core.models import PersonnelEvidence
    chief_person=Personnel.objects.get(user=chief)
    evidence=PersonnelEvidence.objects.create(personnel=chief_person,kind='qualification',title='Verified retained evidence',status='verified',details={'issuer':'Original issuer'},created_by=chief,actor_name='Original assessor')
    evidence_selection={'records':[{'kind':'ei_training','id':evidence.pk}],'reason':'Remove obsolete evidence from active use'}
    response=chief_ei.post(reverse('ei_record_remove'),data=json.dumps(evidence_selection),content_type='application/json',HTTP_X_CSRFTOKEN=csrf_token)
    check(response.status_code==200,'Chief removal works on verified evidence regardless of edit lock')
    check(not chief_person.evidence.filter(pk=evidence.pk).exists(),'Removed evidence is hidden in related personnel records')
    original=PersonnelEvidence._base_manager.get(pk=evidence.pk)
    check(original.status=='verified' and original.details=={'issuer':'Original issuer'} and original.actor_name=='Original assessor','Removal does not rewrite approval, evidence values or actual assessor identity')
    evidence_entry=AdministrativeArchive.objects.get(target_type='ei_training',object_id=evidence.pk)
    browser.post('/recycle-bin/retained/'+str(evidence_entry.pk)+'/restore',data={'_admin_csrf':token,'reason':'Reinstate preserved verified evidence'})
    check(chief_person.evidence.filter(pk=evidence.pk,status='verified').exists(),'Administrator restoration reinstates the original verified evidence')
    staff_ei=DjangoClient(HTTP_HOST='127.0.0.1');staff_ei.force_login(staff)
    check(staff_ei.post(reverse('ei_record_remove'),data=json.dumps(selection),content_type='application/json').status_code==403,'Non-Chief staff cannot remove records')
    from app.modules.auth.permissions import Permissions
    with closing(database.get_connection()) as connection:
        flow_chief_role=connection.execute("SELECT id FROM roles WHERE name='Chief Meteorologist'").fetchone()[0]
        chief_id=connection.execute('INSERT INTO users(username,password_hash,full_name,role_id,is_active,must_change_password) VALUES(?,?,?,?,1,0)',('flowchief',AuthService.hash_password('FlowChief-Removal-2026!'),'Flow Chief',flow_chief_role)).lastrowid
        customer=connection.execute("INSERT INTO customers(customer_name) VALUES('Removal Client')").lastrowid
        project=connection.execute("INSERT INTO projects(project_number,project_name,status,customer_id) VALUES('REMOVAL-PROJECT','Removal test','Planned',?)",(customer,)).lastrowid
        connection.commit()
    flow_chief=app.test_client();flow_chief.post('/login',data={'username':'flowchief','password':'FlowChief-Removal-2026!'})
    flow_chief.get('/projects/jobs')
    with flow_chief.session_transaction() as session: chief_token=session['_admin_csrf']
    payload={'records':[{'kind':'flow_project','id':project},{'kind':'flow_project','id':999999}],'reason':'Remove placeholder records safely'}
    check(flow_chief.post('/records/remove',json=payload,headers={'X-Record-CSRF':chief_token}).status_code==400,'Mixed invalid bulk selection fails without partial removal')
    with closing(database.get_connection()) as connection:
        check(connection.execute('SELECT is_deleted FROM projects WHERE id=?',(project,)).fetchone()[0]==0,'Failed bulk request rolls back earlier record changes')
    payload['records']=payload['records'][:1]
    check(flow_chief.post('/records/remove',json=payload).status_code==400,'FlowLab removal rejects missing CSRF token')
    check(flow_chief.post('/records/remove',json=payload,headers={'X-Record-CSRF':chief_token}).status_code==200,'FlowLab Chief can remove selected project')
    entry=AdministrativeArchive.objects.get(target_type='flow_project',object_id=project)
    check(flow_chief.post('/recycle-bin/retained/'+str(entry.pk)+'/restore',data={'_admin_csrf':chief_token,'reason':'Not allowed restore attempt'}).status_code==403,'Chief cannot restore from Administrator master recycle bin')
    check(flow_chief.get('/settings/users').status_code==403,'Chief deletion authority does not grant account administration')
    page=flow_chief.get('/iso17025/8.7')
    check('record-removal.js' in flow_chief.get('/projects/jobs').get_data(as_text=True),'Chief pages include the compact selection-control script')
    account_page=browser.get('/settings/users')
    check(b'data-module="accounts"' in account_page.data and b'data-record-kind="flow_user"' in account_page.data,'Administrator user registers include account removal checkboxes and controls')
    with browser.session_transaction() as session: account_token=session['_admin_csrf']; own_id=session['user_id']
    headers={'X-Record-CSRF':account_token}
    self_selection={'records':[{'kind':'flow_user','id':own_id}],'reason':'Attempt self removal safeguard'}
    check(browser.post('/settings/users/remove',json=self_selection,headers=headers).status_code==400,'Administrator cannot remove their own account')
    check(flow_chief.post('/settings/users/remove',json=self_selection,headers={'X-Record-CSRF':chief_token}).status_code==403,'Chief cannot use administrator account removal')
    staff.refresh_from_db()
    invalid_selection={'records':[{'kind':'ei_user','id':staff.pk},{'kind':'ei_user','id':999999}],'reason':'Atomic account removal test'}
    check(browser.post('/settings/users/remove',json=invalid_selection,headers=headers).status_code==400,'Invalid account batch is rejected')
    staff.refresh_from_db();check(staff.is_active,'Failed account batch preserves existing account access')
    with closing(database.get_connection()) as connection:
        shared_id=connection.execute('SELECT id FROM users WHERE username=?',('sharedadmin',)).fetchone()[0]
    account_selection={'records':[{'kind':'flow_user','id':shared_id}],'reason':'Remove temporary test administrator'}
    check(browser.post('/settings/users/remove',json=account_selection,headers=headers).status_code==200,'Administrator can remove another account')
    linked.refresh_from_db();check(not linked.is_active,'Linked account removal disables both module identities')
    check(AuthService().authenticate('sharedadmin','Recovered-Secret-2026!') is None,'Removed administrator cannot sign in')
    check(b'sharedadmin' not in browser.get('/settings/users').data,'Removed account disappears from user registers')
    account_entry=AdministrativeArchive.objects.get(target_type='flow_user',object_id=shared_id)
    response=browser.post('/recycle-bin/retained/'+str(account_entry.pk)+'/restore',data={'_admin_csrf':account_token,'reason':'Restore retained administrator identity'})
    check(response.status_code==302,'Master recycle bin restores removed account')
    linked.refresh_from_db();check(linked.is_active,'Restoration reinstates linked account access without replacing its identity')
    check(AuthService().authenticate('sharedadmin','Recovered-Secret-2026!') is not None,'Original password works again after authorized account restoration')
    # Chief registration uses the same SQLite transaction, without linking ordinary personnel identities.
    with closing(database.get_connection()) as connection:
        connection.execute("UPDATE users SET role_id=(SELECT id FROM roles WHERE name='Chief Metrologist') WHERE id=?",(chief_id,))
        connection.commit()
    check(flow_chief.get('/personnel/register').status_code==200,'Chief Metrologist can open cross-lab personnel registration')
    with flow_chief.session_transaction() as session: registration_token=session['_admin_csrf']
    payload={'lab':'ei','username':'chiefregistered','full_name':'Chief Registered Analyst','email':'analyst@example.test',
        'password':'Unique-Registration-947!','ei_role':technician.pk,'qualifications':'Unverified degree',
        'years_of_experience':'3','_admin_csrf':registration_token}
    check(flow_chief.post('/personnel/register',data=payload).status_code==302,'Chief creates E&I personnel through shared transaction')
    created=Personnel.objects.get(user__username='chiefregistered')
    check(not created.authorizations.exists() and not created.competencies.exists(),'Registration does not invent technical authorization or competency')
    check(not AdminAccountLink.objects.filter(user=created.user).exists(),'Ordinary E&I personnel identity is not merged with FlowLab')
    check(created.user.check_password(payload['password']),'Registered E&I personnel has the specified credentials')
    payload.update(username='chiefprivilegeattempt',ei_role=Role.objects.get(name='Administrator').pk)
    check(flow_chief.post('/personnel/register',data=payload).status_code==200,'Forbidden role is rejected without a broken transaction')
    check(not User.objects.filter(username='chiefprivilegeattempt').exists(),'Chief cannot appoint an Administrator')
    check(flow_chief.get('/settings/users').status_code==403,'Registration does not expose admin User Management')
    reading={'record_date':'2026-01-01','record_time':'08:00','location':'Flow Laboratory','temperature':'23','humidity':'50','instrument_used':'ENV-1','_admin_csrf':registration_token}
    check(flow_chief.post('/environment',data=reading).status_code==302,'Environmental reading saves on shared SQLite')
    with closing(database.get_connection()) as connection:
        reading_id=connection.execute('SELECT id FROM flow_environment_readings').fetchone()[0]
    selection={'records':[{'kind':'flow_environment','id':reading_id}],'reason':'Remove retained test environmental reading'}
    check(flow_chief.post('/records/remove',json=selection,headers={'X-Record-CSRF':registration_token}).status_code==200,'Chief can recoverably remove environmental reading')
    archived=AdministrativeArchive.objects.get(target_type='flow_environment',object_id=reading_id)
    check(browser.post('/recycle-bin/retained/'+str(archived.pk)+'/restore',data={'_admin_csrf':account_token,'reason':'Restore environmental test record'}).status_code==302,'Administrator restores environmental reading from master bin')
    # Crawl real navigation and record links in the disposable database, never live writes.
    from workspace_link_check import check_links
    ei_browser=DjangoClient(); ei_browser.force_login(linked)
    from django.test import override_settings
    from django.urls import set_script_prefix
    with override_settings(FORCE_SCRIPT_NAME='/ei-lab'):
        set_script_prefix('/ei-lab')
        navigation=check_links(browser,ei_browser,('/dashboard','/workspace/iso17025','/workspace/standards','/settings',
            '/settings/users','/environment','/personnel/register','/analytics/calibration','/recycle-bin',
            '/ei-lab/','/ei-lab/personnel/','/ei-lab/equipment/','/ei-lab/environment/','/ei-lab/settings/'))
        role_user=User.objects.create_user('navigation-chief',password='Disposable-Navigation-951!')
        Personnel.objects.create(user=role_user,name='Navigation Chief',role=Role.objects.get(name='Chief Metrologist'),qualifications='',years_of_experience=0)
        chief_browser=DjangoClient();chief_browser.force_login(role_user)
        chief_navigation=check_links(flow_chief,chief_browser,('/ei-lab/','/ei-lab/personnel/','/ei-lab/settings/'))
    print('Navigation checks:',navigation)
    check(not navigation['failures'],'All reachable authenticated navigation links return without HTTP errors')
    print('Chief navigation checks:',chief_navigation)
    check(not chief_navigation['failures'],'Chief-specific E&I navigation contains no forbidden global-admin shortcuts or broken pages')
    print('PASS:',len(checks),'shared-database administration checks')
    connections.close_all()
