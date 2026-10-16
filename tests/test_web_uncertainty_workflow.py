import tempfile
import unittest
from pathlib import Path

import app.database.database as database
from app.database.init_db import initialize_database
from web_app import app, automate_job_status


class WebUncertaintyWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.original_path = database.DATABASE_PATH
        self.tempdir = tempfile.TemporaryDirectory()
        database.DATABASE_PATH = Path(self.tempdir.name) / "test.db"
        initialize_database()
        connection = database.get_connection()
        role = connection.execute("SELECT id FROM roles WHERE name='Administrator'").fetchone()[0]
        connection.execute("INSERT INTO customers (customer_name) VALUES ('Test Client')")
        customer = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
        connection.execute("""INSERT INTO projects
            (project_number,customer_id,project_name,purchase_order,status)
            VALUES ('PRJ-TEST-001',?,'Shared calibration project','PO-100','In Progress')""", (customer,))
        project = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
        connection.execute("""INSERT INTO calibration_methods
            (meter_type,method_name,revision,status,is_active)
            VALUES ('Coriolis','Gravimetric Method','1','Approved',1)""")
        method = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
        for tag in ("P1", "T1", "DIV-1", "WS-1", "MM-1", "TT-1", "PT-1"):
            connection.execute("""INSERT INTO laboratory_equipment
                (asset_number,equipment_name,next_calibration_date,is_active)
                VALUES (?,?, '2099-01-01',1)""", (tag, tag))
            equipment_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
            connection.execute("""INSERT INTO uncertainty_profiles
                (equipment_id,version,certificate_number,standard_uncertainty,
                 coverage_factor,sensitivity,is_active)
                VALUES (?,'1','CERT',0.01,2,1,1)""", (equipment_id,))
        connection.commit(); connection.close()
        self.customer, self.method, self.project = customer, method, project
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def tearDown(self):
        database.DATABASE_PATH = self.original_path
        self.tempdir.cleanup()

    def test_shared_job_retains_required_flow_point_count(self):
        response = self.client.post("/projects/jobs", data={
            "action": "add_job", "job_number": "JOB-TEST-001",
            "job_title": "MUT flow calibration", "job_type": "Calibration",
            "project_id": str(self.project), "job_purchase_order": "PO-100-R1",
            "mut_description": "Test MUT", "mut_serial_number": "SN-1",
            "meter_type": "Coriolis", "method_id": str(self.method),
            "engineer_operator": "Engineer", "required_date": "2027-01-01",
            "flow_min": "0", "flow_max": "30", "flow_unit": "L/min",
            "flow_point_count": "4", "fluid_medium": "Water",
            "calibration_quantity": "volume", "status": "Draft",
        })
        self.assertEqual(response.status_code, 302)
        connection = database.get_connection()
        job_id = connection.execute("SELECT id FROM calibration_jobs WHERE job_number='JOB-TEST-001'").fetchone()[0]
        relation = connection.execute("SELECT project_id FROM project_jobs WHERE job_id=?", (job_id,)).fetchone()
        purchase_order = connection.execute("SELECT purchase_order_override FROM calibration_jobs WHERE id=?", (job_id,)).fetchone()
        flow_point_count = connection.execute("SELECT flow_point_count FROM calibration_jobs WHERE id=?", (job_id,)).fetchone()[0]
        connection.close()
        self.assertEqual(relation[0], self.project)
        self.assertEqual(purchase_order[0], "PO-100-R1")
        self.assertEqual(flow_point_count, 4)
        page = self.client.get(f"/uncertainty?job={job_id}").get_data(as_text=True)
        self.assertIn('data-flow-point-count="4"', page)
        self.client.post(f"/projects/{self.project}/delete")
        page = self.client.get("/uncertainty").get_data(as_text=True)
        self.assertNotIn('data-number="JOB-TEST-001"', page)
        connection = database.get_connection()
        recycled = connection.execute("SELECT id FROM recycle_bin WHERE entity_type='project' AND entity_id=?",
            (self.project,)).fetchone()[0]
        connection.close()
        self.client.post(f"/recycle-bin/{recycled}/restore")
        page = self.client.get("/uncertainty").get_data(as_text=True)
        self.assertIn('data-number="JOB-TEST-001"', page)

    def test_job_id_is_manual_and_previously_used_id_is_blocked(self):
        page = self.client.get(f"/projects/jobs?project={self.project}").get_data(as_text=True)
        job_id_tag = page.split('name="job_number"', 1)[1].split(">", 1)[0]
        self.assertIn("required", job_id_tag)
        self.assertNotIn("readonly", job_id_tag)
        payload = {
            "action": "add_job", "job_number": "MANUAL-001", "job_title": "First Job",
            "job_type": "Calibration", "project_id": str(self.project),
            "mut_description": "Test MUT", "meter_type": "Coriolis",
            "method_id": str(self.method), "required_date": "2027-01-01",
            "flow_min": "0", "flow_max": "30", "flow_unit": "L/min",
            "flow_point_count": "2", "fluid_medium": "Water",
            "calibration_quantity": "volume", "status": "Draft",
        }
        self.assertEqual(self.client.post(f"/projects/jobs?project={self.project}", data=payload).status_code, 302)
        payload["job_number"] = "manual-001"
        duplicate = self.client.post(f"/projects/jobs?project={self.project}", data=payload)
        self.assertEqual(duplicate.status_code, 200)
        self.assertIn("has already been used", duplicate.get_data(as_text=True))
        connection = database.get_connection()
        count = connection.execute("SELECT COUNT(*) FROM calibration_jobs WHERE LOWER(job_number)=LOWER('MANUAL-001')").fetchone()[0]
        connection.close()
        self.assertEqual(count, 1)

    def test_job_status_is_automated_from_assignment_activity_and_final_output(self):
        self.client.post("/projects/jobs", data={
            "action": "add_job", "job_number": "LIFE-001", "job_title": "Lifecycle Job",
            "job_type": "Calibration", "project_id": str(self.project),
            "mut_description": "Test MUT", "meter_type": "Coriolis",
            "method_id": str(self.method), "required_date": "2027-01-01",
            "flow_min": "0", "flow_max": "30", "flow_unit": "L/min",
            "flow_point_count": "2", "fluid_medium": "Water",
            "calibration_quantity": "volume", "status": "Draft",
        })
        connection = database.get_connection()
        try:
            job_id = connection.execute("SELECT id FROM calibration_jobs WHERE job_number='LIFE-001'").fetchone()[0]
            connection.execute("UPDATE calibration_jobs SET assigned_user_id=1 WHERE id=?", (job_id,))
            with app.test_request_context():
                self.assertEqual(automate_job_status(connection, job_id), "Planned")
                self.assertEqual(automate_job_status(connection, job_id, activity=True), "In Progress")
                connection.execute("""INSERT INTO uncertainty_calculations
                    (job_id,status,calculation_version,snapshot_json,approved_by,approved_at)
                    VALUES (?,'Approved','test','{}','Chief',CURRENT_TIMESTAMP)""", (job_id,))
                self.assertEqual(automate_job_status(connection, job_id, evaluate_completion=True), "Completed")
            connection.commit()
            status = connection.execute("SELECT status FROM calibration_jobs WHERE id=?", (job_id,)).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(status, "Completed")

    def test_project_and_job_forms_are_separated_and_collapsed_until_requested(self):
        page = self.client.get("/projects/jobs").get_data(as_text=True)
        self.assertIn('data-scroll-to="newProject" aria-controls="newProject" aria-expanded="false"', page)
        self.assertIn('id="newProject" data-collapsible-form hidden', page)
        self.assertIn('data-close-form aria-label="Close Add Project form"', page)
        self.assertNotIn('id="newJob"', page)
        jobs_page = self.client.get(f"/projects/jobs?project={self.project}").get_data(as_text=True)
        self.assertIn('data-scroll-to="newJob" aria-controls="newJob" aria-expanded="false"', jobs_page)
        self.assertIn('id="newJob" data-collapsible-form hidden', jobs_page)
        self.assertIn('data-close-form aria-label="Close Create Job form"', jobs_page)

    def test_project_creation_shows_add_job_button_and_ignores_stale_job_action(self):
        response = self.client.post("/projects/jobs", data={
            "action": "add_job",
            "project_number": "PRJ-NEW-001",
            "project_name": "New calibration project",
            "project_client_name": "New Client",
            "project_status": "Draft",
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn("project=", response.headers["Location"])
        self.assertNotIn("create_job=1", response.headers["Location"])
        page = self.client.get(response.headers["Location"]).get_data(as_text=True)
        new_job_tag = page.split('id="newJob"', 1)[1].split(">", 1)[0]
        self.assertIn("data-collapsible-form", new_job_tag)
        self.assertIn("hidden", new_job_tag)
        self.assertIn('data-scroll-to="newJob" aria-controls="newJob"', page)
        self.assertIn("Add Job", page)
        self.assertNotIn("Required: Job Title", page)
        connection = database.get_connection()
        saved = connection.execute("""SELECT p.project_number,p.project_name,c.customer_name
            FROM projects p JOIN customers c ON c.id=p.customer_id
            WHERE p.project_number='PRJ-NEW-001'""").fetchone()
        connection.close()
        self.assertEqual(tuple(saved), ("PRJ-NEW-001", "NEW CALIBRATION PROJECT", "NEW CLIENT"))
        self.assertIn("Edit Project", page)
        self.assertNotIn(">EDIT PROJECT<", page)

    def test_project_delete_is_recoverable(self):
        response = self.client.post(f"/projects/{self.project}/delete")
        self.assertEqual(response.status_code, 302)
        connection = database.get_connection()
        self.assertEqual(connection.execute("SELECT is_deleted FROM projects WHERE id=?",
            (self.project,)).fetchone()[0], 1)
        recycled = connection.execute("SELECT id FROM recycle_bin WHERE entity_type='project' AND entity_id=?",
            (self.project,)).fetchone()
        connection.close()
        self.assertIsNotNone(recycled)
        response = self.client.post(f"/recycle-bin/{recycled[0]}/restore")
        self.assertEqual(response.status_code, 302)
        connection = database.get_connection()
        self.assertEqual(connection.execute("SELECT is_deleted FROM projects WHERE id=?",
            (self.project,)).fetchone()[0], 0)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM recycle_bin WHERE id=?",
            (recycled[0],)).fetchone()[0], 0)
        connection.close()

    def test_recycle_removal_is_retained_in_monthly_admin_archive(self):
        self.client.post(f"/projects/{self.project}/delete")
        connection = database.get_connection()
        recycled = connection.execute("SELECT id FROM recycle_bin WHERE entity_type='project' AND entity_id=?",
            (self.project,)).fetchone()[0]
        connection.close()
        self.client.post(f"/recycle-bin/{recycled}/purge")
        connection = database.get_connection()
        archived = connection.execute("SELECT id,archive_month FROM deletion_archive WHERE entity_type='project' AND entity_id=?",
            (self.project,)).fetchone()
        self.assertIsNotNone(archived)
        self.assertEqual(len(archived[1]), 7)
        self.assertEqual(connection.execute("SELECT is_deleted FROM projects WHERE id=?",(self.project,)).fetchone()[0],1)
        connection.close()
        self.client.post(f"/deletion-archive/{archived[0]}/restore")
        connection = database.get_connection()
        self.assertEqual(connection.execute("SELECT is_deleted FROM projects WHERE id=?",(self.project,)).fetchone()[0],0)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM deletion_archive WHERE id=?",(archived[0],)).fetchone()[0],0)
        connection.close()

    def test_user_management_is_a_real_module(self):
        with self.client.session_transaction() as session:
            session['role_name'] = 'Administrator'
        workspace = self.client.get("/workspace/database").get_data(as_text=True)
        users = self.client.get("/users").get_data(as_text=True)
        self.assertNotIn('href="/users"', workspace)
        settings = self.client.get("/settings").get_data(as_text=True)
        self.assertIn('href="/settings/users"', settings)
        self.assertIn("Add user", users)
        self.assertIn("User register", users)

    def test_user_management_is_administrator_only(self):
        for role in ('Chief Meteorologist', 'HOD', 'Supervisor', 'Engineer', 'Technician', 'Guest'):
            with self.client.session_transaction() as session:
                session['role_name'] = role
            self.assertEqual(self.client.get('/settings/users').status_code, 403)
            self.assertEqual(self.client.get('/users').status_code, 403)
            self.assertEqual(self.client.post('/settings/users', data={'action':'create'}).status_code, 403)
            settings = self.client.get('/settings').get_data(as_text=True)
            self.assertNotIn('href="/settings/users"', settings)


if __name__ == "__main__":
    unittest.main()
