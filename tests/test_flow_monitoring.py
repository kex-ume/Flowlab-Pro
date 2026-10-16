import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from app.database import database
from app.database.init_db import initialize_database
from app.modules.flow_environment import save, records
from app.modules.flow_analytics import report
from app.modules.auth.permissions import Permissions
from web_app import app


class FlowMonitoringTests(unittest.TestCase):
    def setUp(self):
        self.previous=database.DATABASE_PATH
        self.temp=tempfile.TemporaryDirectory()
        database.DATABASE_PATH=Path(self.temp.name)/'monitoring.db'
        initialize_database()
        self.conn=database.get_connection()
        self.uid=self.conn.execute("INSERT INTO users(username,password_hash,full_name,role_id) SELECT 'chief','hash','Test Chief',id FROM roles WHERE name='Chief Metrologist'").lastrowid
        self.conn.commit()
        self.previous_testing=app.config.get('TESTING',False)
        app.config['TESTING']=True
        self.client=app.test_client()
        self.login('Chief Metrologist')

    def login(self,role):
        with self.client.session_transaction() as session:
            session.update(user_id=self.uid,role_name=role,full_name='Test Chief',_admin_csrf='token')

    def tearDown(self):
        app.config['TESTING']=self.previous_testing
        self.conn.close(); database.DATABASE_PATH=self.previous; self.temp.cleanup()

    def reading(self,**extra):
        return dict(record_date=date.today().isoformat(),record_time='08:00',location='Flow Laboratory',temperature='23.5',humidity='50',pressure='101.3',instrument_used='ENV-01',_admin_csrf='token')|extra

    def test_environment_hidden_form_dark_charts_and_navigation(self):
        response=self.client.get('/environment')
        self.assertEqual(response.status_code,200)
        html=response.get_data(as_text=True)
        self.assertIn('Temperature &amp; Humidity Trends',html)
        self.assertIn('data-collapsible-form hidden',html)
        self.assertIn('08:00',html)

    def test_multiple_daily_readings_retained_with_actor(self):
        for slot in ('08:00','12:00','17:00'):
            self.assertEqual(self.client.post('/environment',data=self.reading(record_time=slot)).status_code,302)
        data=records(self.conn,{})
        self.assertEqual(len(data),3)
        self.assertEqual({r['recorder'] for r in data},{'Test Chief'})
        self.assertIn('23.5',self.client.get('/environment').get_data(as_text=True))

    def test_duplicate_rejected_without_overwriting(self):
        self.client.post('/environment',data=self.reading())
        response=self.client.post('/environment',data=self.reading(temperature='99'))
        self.assertIn('not overwritten',response.get_data(as_text=True))
        self.assertEqual(records(self.conn,{})[0]['temperature'],23.5)

    def test_invalid_reading_retains_form(self):
        response=self.client.post('/environment',data=self.reading(humidity='101'))
        self.assertIn('0–100%',response.get_data(as_text=True))
        self.assertEqual(len(records(self.conn,{})),0)

    def test_guest_cannot_record_and_csrf_enforced(self):
        self.login('Guest')
        self.assertEqual(self.client.post('/environment',data=self.reading()).status_code,403)
        self.login('Chief Metrologist')
        self.assertEqual(self.client.post('/environment',data=self.reading(_admin_csrf='bad')).status_code,400)

    def test_concurrent_environment_save_returns_a_recoverable_message(self):
        import sqlite3
        with patch('app.modules.flow_environment.save',side_effect=sqlite3.OperationalError('database is locked')):
            response=self.client.post('/environment',data=self.reading())
        self.assertEqual(response.status_code,200)
        self.assertIn('Reload before trying again',response.get_data(as_text=True))

    def test_legacy_environment_preserved_and_filtered(self):
        self.conn.execute("INSERT INTO environmental_records(record_date,ambient_temperature,recorded_by) VALUES ('2020-01-01',21,'Legacy Analyst')")
        self.conn.commit()
        data=records(self.conn,{})
        self.assertEqual(data[0]['kind'],'flow_environment_legacy')
        self.assertEqual(records(self.conn,{'from_date':'2025-01-01'}),[])

    def test_archive_hides_environment_without_deleting(self):
        pk=save(self.conn,self.reading(),self.uid,'Test Chief')
        self.conn.execute('UPDATE flow_environment_readings SET is_deleted=1 WHERE id=?',(pk,)); self.conn.commit()
        self.assertEqual(records(self.conn,{}),[])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM flow_environment_readings').fetchone()[0],1)

    def test_export_spreadsheet_formula_safety(self):
        self.client.post('/environment',data=self.reading(notes='=HYPERLINK("bad")'))
        response=self.client.get('/environment?export=csv')
        self.assertEqual(response.status_code,200)
        self.assertIn("'=HYPERLINK",response.get_data(as_text=True))

    def test_invalid_filters_rejected(self):
        self.assertEqual(self.client.get('/environment?from_date=2026-12-01&to_date=2026-01-01').status_code,400)
        self.assertEqual(self.client.get('/analytics/calibration?from_date=oops').status_code,400)

    def test_all_analytics_pages_and_legacy_links(self):
        for category in ('calibration','uncertainty','cmc','equipment','capa','audit-pt'):
            response=self.client.get('/analytics/'+category)
            self.assertEqual(response.status_code,200,category)
            self.assertNotIn('name="title"',response.get_data(as_text=True))
        self.assertEqual(self.client.post('/workspace/analytics/calibration',data={'title':'Fake'}).status_code,405)
        self.assertEqual(self.client.get('/workspace/analytics').status_code,302)

    def test_equipment_metrics_are_live_and_ignore_inactive(self):
        self.conn.executemany('INSERT INTO laboratory_equipment(asset_number,equipment_name,is_active,next_calibration_date) VALUES (?,?,?,?)',[
            ('EQ1','Lab Meter',1,'2020-01-01'),('EQ2','Archived',0,'2020-01-01')])
        self.conn.commit()
        result=report(self.conn,'equipment')
        self.assertEqual(dict(result['metrics'])['Lab equipment'],1)
        self.assertEqual(dict(result['metrics'])['Overdue'],1)

    def test_personnel_registration_is_chief_only_not_user_management(self):
        self.assertTrue(Permissions.can('Chief Metrologist','equipment_edit'))
        self.assertFalse(Permissions.can('Chief Metrologist','user_management'))
        self.login('Engineer')
        self.assertEqual(self.client.get('/personnel/register').status_code,403)
        self.login('Chief Metrologist')
        self.assertEqual(self.client.get('/personnel/register').status_code,200)

    def test_chief_creates_flow_personnel_without_admin_privilege(self):
        payload=dict(lab='flow',username='newanalyst',full_name='New Analyst',password='Test-Strong-Key-941!',flow_role='Engineer',_admin_csrf='token')
        self.assertEqual(self.client.post('/personnel/register',data=payload).status_code,302)
        row=self.conn.execute("SELECT r.name,u.must_change_password FROM users u JOIN roles r ON r.id=u.role_id WHERE username='newanalyst'").fetchone()
        self.assertEqual(row,('Engineer',1))
        response=self.client.post('/personnel/register',data=payload|dict(username='badadmin',flow_role='Administrator'))
        self.assertEqual(response.status_code,200)
        self.assertIsNone(self.conn.execute("SELECT id FROM users WHERE username='badadmin'").fetchone())

    def test_supervisor_registration_reaches_chief_and_completes_once(self):
        supervisor=self.conn.execute("INSERT INTO users(username,password_hash,full_name,role_id) SELECT 'supervisor','hash','Test Supervisor',id FROM roles WHERE name='Supervisor'").lastrowid
        self.conn.commit()
        clause=self.conn.execute("SELECT id FROM iso_clauses WHERE clause_code='6.2'").fetchone()[0]
        with self.client.session_transaction() as state:
            state.update(user_id=supervisor,role_name='Supervisor',full_name='Test Supervisor')
        self.assertEqual(self.client.post(f'/iso17025/clause-checklist/{clause}/personnel/register',data={
            'full_name':'Requested Analyst','requested_role':'Engineer'}).status_code,302)
        request_id=self.conn.execute("SELECT id FROM personnel_registrations WHERE status='Pending'").fetchone()[0]
        self.login('Chief Metrologist')
        page=self.client.get(f'/personnel/register?registration_id={request_id}')
        self.assertEqual(page.status_code,200);self.assertIn('Requested Analyst',page.get_data(as_text=True))
        payload=dict(lab='flow',username='requestedanalyst',full_name='Requested Analyst',password='Test-Strong-Key-941!',flow_role='Engineer',registration_id=request_id,_admin_csrf='token')
        self.assertEqual(self.client.post('/personnel/register',data=payload).status_code,302)
        self.assertEqual(self.conn.execute('SELECT status FROM personnel_registrations WHERE id=?',(request_id,)).fetchone()[0],'Approved')
        self.assertEqual(self.client.post('/personnel/register',data=payload|dict(username='duplicateanalyst')).status_code,302)
        self.assertIsNone(self.conn.execute("SELECT id FROM users WHERE username='duplicateanalyst'").fetchone())
