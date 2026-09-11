import tempfile
import unittest
from pathlib import Path

import app.database.database as database
from app.database.init_db import initialize_database
from web_app import app


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

    def test_user_management_is_a_real_module(self):
        workspace = self.client.get("/workspace/database").get_data(as_text=True)
        users = self.client.get("/users").get_data(as_text=True)
        self.assertIn('href="/users"', workspace)
        self.assertIn("Add user", users)
        self.assertIn("User register", users)


if __name__ == "__main__":
    unittest.main()
