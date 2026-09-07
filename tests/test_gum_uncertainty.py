import json
from math import sqrt
from pathlib import Path
import tempfile
import unittest

import app.database.database as database
from app.database.init_db import initialize_database
from app.modules.auth.permissions import Permissions
from app.modules.uncertainty.engine import GUMEngine, UncertaintyInput
from web_app import app


class GUMEngineTests(unittest.TestCase):
    def component(self, name, value, dof=None):
        return UncertaintyInput(name, "B", "Test", value, "%", "Standard",
            "Normal", 1, 1, degrees_of_freedom=dof)

    def test_gravimetric_mass_reference_and_error(self):
        result = GUMEngine.gravimetric_run(10, 2, 5.1)
        self.assertAlmostEqual(result["reference_flow"], 5)
        self.assertAlmostEqual(result["error_percent"], 2)

    def test_gravimetric_volume_reference(self):
        result = GUMEngine.gravimetric_run(10, 2, 5.1, "volume", 2)
        self.assertAlmostEqual(result["reference_flow"], 2.5)

    def test_gravimetric_units_are_converted_before_error_evaluation(self):
        specific_volume = GUMEngine.gravimetric_run(
            10, 2, 300, "volume", 0.001, "m³/kg", "L/min")
        density = GUMEngine.gravimetric_run(
            10, 2, 18, "volume", 1000, "kg/m³", "m³/h")
        mass = GUMEngine.gravimetric_run(10, 2, 300, "mass", flow_unit="kg/min")
        self.assertAlmostEqual(specific_volume["reference_flow"], 300)
        self.assertAlmostEqual(specific_volume["error_percent"], 0)
        self.assertAlmostEqual(density["reference_flow"], 18)
        self.assertAlmostEqual(mass["reference_flow"], 300)

    def test_master_meter_correction_and_missing_correction(self):
        result = GUMEngine.coriolis_run(100, 0.01, 102)
        self.assertAlmostEqual(result["reference_flow"], 101)
        factor_result = GUMEngine.coriolis_run(26241, 1, 26240, "factor")
        self.assertAlmostEqual(factor_result["reference_flow"], 26241)
        self.assertAlmostEqual(factor_result["error_percent"], -1 / 26241 * 100)
        with self.assertRaisesRegex(ValueError, "correction is required"):
            GUMEngine.coriolis_run(100, None, 102)

    def test_correlation_changes_rss(self):
        components = (self.component("A", 3), self.component("B", 4))
        independent = GUMEngine.calculate(components, coverage_mode="manual", coverage_factor=2)
        correlated = GUMEngine.calculate(components,
            ({"source_i":"A","source_j":"B","coefficient":0.5,"justification":"Shared timing"},),
            "manual", 2)
        self.assertAlmostEqual(independent.combined_standard_uncertainty, 5)
        self.assertGreater(correlated.combined_standard_uncertainty, 5)

    def test_invalid_correlation_and_missing_justification_are_blocked(self):
        components = (self.component("A", 1), self.component("B", 1))
        with self.assertRaisesRegex(ValueError, r"between -1 and \+1"):
            GUMEngine.calculate(components, ({"source_i":"A","source_j":"B","coefficient":2,"justification":"x"},))
        with self.assertRaisesRegex(ValueError, "requires a justification"):
            GUMEngine.calculate(components, ({"source_i":"A","source_j":"B","coefficient":.2},))

    def test_welch_satterthwaite_auto_coverage_and_expanded_result(self):
        result = GUMEngine.calculate((self.component("A", 1, 4), self.component("B", 1, 9)))
        expected_dof = sqrt(2) ** 4 / (1 / 4 + 1 / 9)
        self.assertAlmostEqual(result.effective_degrees_of_freedom, expected_dof)
        self.assertGreater(result.coverage_factor, 2)
        self.assertAlmostEqual(result.expanded_uncertainty,
            result.coverage_factor * result.combined_standard_uncertainty)


class GUMWebWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.original_path = database.DATABASE_PATH
        self.tempdir = tempfile.TemporaryDirectory()
        database.DATABASE_PATH = Path(self.tempdir.name) / "gum.db"
        initialize_database()
        connection = database.get_connection()
        connection.execute("INSERT INTO customers(customer_name) VALUES ('GUM Client')")
        customer = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
        connection.execute("""INSERT INTO calibration_methods
            (meter_type,method_name,revision,status,is_active)
            VALUES ('Coriolis','Gravimetric Method','1','Approved',1)""")
        method = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
        connection.execute("""INSERT INTO laboratory_equipment
            (asset_number,equipment_name,manufacturer,model,serial_number,last_calibration_date,
             next_calibration_date,status,certificate_path,is_reference_standard,record_status,is_active)
             VALUES ('WS-100','Weighing Scale','Maker','Scale 1','S-1','2026-01-01',
             '2099-01-01','Active','certificate.pdf',1,'Approved',1)""")
        equipment = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
        connection.execute("""INSERT INTO equipment_capabilities
            (equipment_id,operating_range_min,operating_range_max,operating_unit,resolution,
             accuracy_value,tolerance) VALUES (?,0,200,'L/min',0.02,0.03,0.04)""", (equipment,))
        connection.execute("""INSERT INTO uncertainty_profiles
            (equipment_id,version,certificate_number,coverage_factor,expanded_uncertainty,
             standard_uncertainty,resolution,drift,certificate_path,source_name,uncertainty_unit,
             evaluation_basis,distribution,divisor,sensitivity,degrees_of_freedom,is_active)
             VALUES (?,'1','CERT-WS',2,0.1,0.05,0.02,0.01,'certificate.pdf',
             'Weighing scale calibration uncertainty','%','expanded','Normal',2,1,50,1)""", (equipment,))
        connection.execute("""INSERT INTO calibration_jobs
            (job_number,customer_id,equipment_id,method_id,status,mut_description,
             mut_serial_number,meter_type,flow_min,flow_max,flow_unit,flow_point_count,is_deleted)
             VALUES ('JOB-GUM-1',?,?,?,'Draft','Flow meter','MUT-1','Coriolis',0,100,'kg/s',1,0)""",
             (customer, equipment, method))
        self.job_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
        engineer_role = connection.execute("SELECT id FROM roles WHERE name='Engineer'").fetchone()[0]
        hod_role = connection.execute("SELECT id FROM roles WHERE name='HOD'").fetchone()[0]
        self.reviewer_id = connection.execute("""INSERT INTO users
            (username,password_hash,full_name,role_id) VALUES ('technical-reviewer','x','Technical Reviewer',?)""",
            (engineer_role,)).lastrowid
        self.approver_id = connection.execute("""INSERT INTO users
            (username,password_hash,full_name,role_id) VALUES ('hod-reviewer','x','HOD Reviewer',?)""",
            (hod_role,)).lastrowid
        self.equipment_id = equipment
        connection.commit(); connection.close()
        app.config.update(TESTING=True)
        self.client = app.test_client()
        self.sign_in_as("Analyst", "Technician")

    def sign_in_as(self, full_name, role_name):
        with self.client.session_transaction() as login:
            login["full_name"] = full_name
            login["role_name"] = role_name

    def review_and_approve(self, record_id, record_type="calculation"):
        self.sign_in_as("Technical Reviewer", "Engineer")
        response = self.client.post(
            f"/uncertainty/api/records/{record_type}/{record_id}/workflow", json={"action":"review"})
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(response.get_json()["status"], "HOD Review")
        self.sign_in_as("HOD Reviewer", "HOD")
        response = self.client.post(
            f"/uncertainty/api/records/{record_type}/{record_id}/workflow", json={"action":"approve"})
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response

    def submit_for_review(self, record_id, record_type="calculation"):
        return self.client.post(f"/uncertainty/api/records/{record_type}/{record_id}/workflow",
            json={"action":"submit", "reviewerUserId":self.reviewer_id,
                  "approverUserId":self.approver_id})

    def tearDown(self):
        database.DATABASE_PATH = self.original_path
        self.tempdir.cleanup()

    def point(self, sources=None, correlations=None):
        return {"label":"50 kg/s","nominalFlow":50,"flowUnit":"kg/s",
            "refTemp":"","refPressure":"","runs":[
                {"mass":100,"time":2,"density":"","mut":50.1},
                {"mass":100.2,"time":2,"density":"","mut":50.0},
                {"mass":99.8,"time":2,"density":"","mut":49.9}],
            "sources":sources or [],"correlations":correlations or [],
            "coverageMode":"auto","manualK":"","coverageProb":95,
            "cmcExpression":"point","cmcA":"","cmcB":""}

    def payload(self, calculation_type="mutGrav", points=None):
        return {"recordId":None,"calculationType":calculation_type,"jobId":self.job_id,
            "jobNumber":"JOB-GUM-1","customer":"GUM Client","mut":"Flow meter",
            "serialNumber":"MUT-1","model":"Scale 1","analyst":"Analyst",
            "calcDate":"2026-08-20","fluid":"Water","quantity":"mass",
            "points":points or [self.point()]}

    def calculate(self, payload=None):
        response = self.client.post("/uncertainty/api/calculate", json=payload or self.payload())
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()["result"]

    def test_new_page_replaces_v61_and_has_no_local_storage(self):
        text = self.client.get("/uncertainty").get_data(as_text=True)
        self.assertIn("Measurement Uncertainty Budget", text)
        self.assertNotIn("<h2>GUM Uncertainty Budget</h2>", text)
        self.assertIn("Budget Calculator", text)
        self.assertIn("CMC Comparison", text)
        self.assertNotIn("Uncertainty V6.1", text)
        self.assertNotIn("localStorage", text)
        self.assertIn("Weighing scale calibration uncertainty", text)
        self.assertIn("uncertainty-equipment-autofill.js", text)
        script = Path("static/uncertainty.js").read_text(encoding="utf-8")
        self.assertIn("backendResult?.observations?.[index]", script)
        self.assertIn("Density / specific volume", script)
        self.assertIn("refreshObservationPreview", script)
        self.assertIn("standardDeviation/Math.sqrt(n)", script)
        self.assertIn("navigator.sendBeacon('/uncertainty/api/autosave'", script)
        self.assertIn("Assign and Submit for Review", script)

    def test_standalone_tool_calculates_but_cannot_create_a_record(self):
        page=self.client.get("/uncertainty?standalone=1").get_data(as_text=True)
        self.assertIn("Standalone Uncertainty Calculator",page)
        self.assertIn("Not retained",page)
        standalone=self.payload();standalone["jobId"]="";standalone["standalone"]=True
        response=self.client.post("/uncertainty/api/calculate",json=standalone)
        self.assertEqual(response.status_code,200,response.get_data(as_text=True))
        response=self.client.post("/uncertainty/api/save",json=standalone)
        self.assertEqual(response.status_code,422)
        connection=database.get_connection()
        count=connection.execute("SELECT COUNT(*) FROM uncertainty_calculations").fetchone()[0]
        connection.close();self.assertEqual(count,0)

    def test_partial_draft_autosaves_and_can_be_discarded(self):
        partial = self.payload(); partial["points"][0]["runs"] = partial["points"][0]["runs"][:1]
        saved = self.client.post("/uncertainty/api/autosave", json=partial)
        self.assertEqual(saved.status_code, 200, saved.get_data(as_text=True))
        record_id = saved.get_json()["record"]["id"]
        loaded = self.client.get(f"/uncertainty/api/records/calculation/{record_id}").get_json()["record"]
        self.assertEqual(len(loaded["points"][0]["runs"]), 1)
        discarded = self.client.post(f"/uncertainty/api/records/calculation/{record_id}/discard", json={})
        self.assertEqual(discarded.status_code, 200, discarded.get_data(as_text=True))
        connection = database.get_connection()
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM uncertainty_calculations WHERE id=?",
            (record_id,)).fetchone()[0], 0)
        connection.close()

    def test_type_a_statistics_are_derived_from_retained_runs(self):
        point = self.calculate()["points"][0]
        self.assertEqual(point["statistics"]["n"], 3)
        self.assertAlmostEqual(point["statistics"]["standard_uncertainty"],
            point["statistics"]["standard_deviation"] / sqrt(3))
        self.assertEqual(point["result"]["components"][0]["input"]["degrees_of_freedom"], 2)
        self.assertEqual(point["result"]["components"][0]["input"]["source"],
            "Repeatability of calibration result")
        diagnostics = {item["quantity"]: item for item in point["repeatabilityDiagnostics"]}
        self.assertIn("Collected mass", diagnostics)
        self.assertIn("Collection time", diagnostics)
        self.assertIn("Reference flow", diagnostics)
        self.assertIn("MUT indication", diagnostics)
        self.assertEqual(diagnostics["Calibration error"]["treatment"],
            "Included as the Type A budget source")
        self.assertIn("Diagnostic only", diagnostics["Reference flow"]["treatment"])

    def test_expanded_rectangular_triangular_and_resolution_conversion(self):
        sources = [
            {"name":"Certificate","sourceType":"B","value":0.2,"unit":"%","basis":"expanded","distribution":"","certK":2,"sensitivity":1,"included":True},
            {"name":"Rectangular","sourceType":"B","value":0.3,"unit":"%","basis":"limit","distribution":"rectangular","certK":"","sensitivity":1,"included":True},
            {"name":"Triangular","sourceType":"B","value":0.6,"unit":"%","basis":"limit","distribution":"triangular","certK":"","sensitivity":1,"included":True},
            {"name":"Resolution","sourceType":"B","value":0.12,"unit":"%","basis":"resolution","distribution":"","certK":"","sensitivity":1,"included":True}]
        result = self.calculate(self.payload(points=[self.point(sources)]))["points"][0]["result"]
        rows = {item["input"]["source"]:item for item in result["components"]}
        self.assertAlmostEqual(rows["Certificate"]["standard_uncertainty"], .1)
        self.assertAlmostEqual(rows["Rectangular"]["standard_uncertainty"], .3/sqrt(3))
        self.assertAlmostEqual(rows["Triangular"]["standard_uncertainty"], .6/sqrt(6))
        self.assertAlmostEqual(rows["Resolution"]["standard_uncertainty"], .12/sqrt(12))

    def test_equipment_retrieval_uses_actual_profile(self):
        source = {"name":"Weighing calibration","sourceType":"B","value":"","unit":"%",
            "basis":"","distribution":"","certK":"","sensitivity":1,"included":True,
            "equipmentId":self.equipment_id,"equipmentProperty":"calibration_uncertainty"}
        point = self.calculate(self.payload(points=[self.point([source])]))["points"][0]
        row = next(item for item in point["result"]["components"]
            if item["input"]["source"]=="Weighing scale calibration uncertainty")
        self.assertAlmostEqual(row["standard_uncertainty"], .05)
        self.assertEqual(row["input"]["evidence"], "CERT-WS")

    def test_expired_equipment_blocks_calculation(self):
        connection = database.get_connection(); connection.execute(
            "UPDATE laboratory_equipment SET next_calibration_date='2020-01-01' WHERE id=?", (self.equipment_id,)); connection.commit(); connection.close()
        source = {"name":"Scale","sourceType":"B","value":"","unit":"%","basis":"",
            "distribution":"","certK":"","sensitivity":1,"included":True,
            "equipmentId":self.equipment_id,"equipmentProperty":"calibration_uncertainty"}
        response = self.client.post("/uncertainty/api/calculate", json=self.payload(points=[self.point([source])]))
        self.assertEqual(response.status_code, 422)
        self.assertIn("calibration expired", response.get_json()["error"])

    def test_save_reload_relations_and_pdf_export(self):
        saved = self.client.post("/uncertainty/api/save", json=self.payload()).get_json()["record"]
        loaded = self.client.get(f"/uncertainty/api/records/calculation/{saved['id']}").get_json()["record"]
        self.assertEqual(loaded["jobNumber"], "JOB-GUM-1")
        connection = database.get_connection()
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM uncertainty_flow_points WHERE calculation_id=?", (saved["id"],)).fetchone()[0], 1)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM uncertainty_observations").fetchone()[0], 3)
        connection.close()
        pdf = self.client.get(f"/uncertainty/records/{saved['id']}/pdf")
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.data.startswith(b"%PDF"))

    def test_approval_lock_and_revision_creation(self):
        saved = self.client.post("/uncertainty/api/save", json=self.payload()).get_json()["record"]
        record_id = saved["id"]
        response = self.submit_for_review(record_id)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.review_and_approve(record_id)
        rendered = self.client.get(f"/uncertainty/records/{record_id}/report")
        self.assertEqual(rendered.status_code, 200)
        self.assertIn(b"Measurement Uncertainty Report", rendered.data)
        self.assertIn(b"ISO/IEC 17025:2017", rendered.data)
        self.assertIn(b"Approving officer", rendered.data)
        self.assertNotIn(b'id="calcId"', rendered.data)
        self.assertNotIn(b'data-workflow=', rendered.data)
        exported_csv = self.client.get(f"/uncertainty/records/{record_id}/csv")
        self.assertEqual(exported_csv.status_code, 200)
        self.assertIn(b"Combined standard uncertainty", exported_csv.data)
        locked = self.payload(); locked["recordId"] = record_id
        self.assertEqual(self.client.post("/uncertainty/api/save", json=locked).status_code, 422)
        revision = self.client.post(f"/uncertainty/api/records/calculation/{record_id}/revision",
            json={"reason":"Updated calibration evidence"})
        self.assertEqual(revision.status_code, 200, revision.get_data(as_text=True))
        self.assertNotEqual(revision.get_json()["record"]["id"], record_id)

    def test_revert_requires_comment(self):
        saved = self.client.post("/uncertainty/api/save", json=self.payload()).get_json()["record"]
        self.submit_for_review(saved["id"])
        response = self.client.post(f"/uncertainty/api/records/calculation/{saved['id']}/workflow", json={"action":"revert","comment":""})
        self.assertEqual(response.status_code, 422)

    def test_job_and_uncertainty_statuses_remain_independent(self):
        saved = self.client.post("/uncertainty/api/save", json=self.payload()).get_json()["record"]
        self.submit_for_review(saved["id"])
        connection = database.get_connection()
        statuses = connection.execute("""SELECT j.status,u.status,u.assigned_reviewer,u.assigned_approver
            FROM calibration_jobs j
            JOIN uncertainty_calculations u ON u.job_id=j.id WHERE u.id=?""", (saved["id"],)).fetchone()
        tasks = connection.execute("""SELECT task_type,assigned_to,status FROM workflow_tasks
            WHERE entity_type='uncertainty_calculation' AND entity_id=? ORDER BY id""", (saved["id"],)).fetchall()
        connection.close()
        self.assertEqual(tuple(statuses), ("Draft", "Submitted for Review", "Technical Reviewer", "HOD Reviewer"))
        self.assertEqual(tuple(tasks[0]), ("Technical Review", "Technical Reviewer", "Pending"))

    def test_creator_cannot_approve_own_uncertainty_record(self):
        saved = self.client.post("/uncertainty/api/save", json=self.payload()).get_json()["record"]
        self.submit_for_review(saved["id"])
        response = self.client.post(f"/uncertainty/api/records/calculation/{saved['id']}/workflow", json={"action":"approve"})
        self.assertEqual(response.status_code, 422)
        self.assertIn("own uncertainty record", response.get_json()["error"])

    def test_chief_submission_is_approved_automatically(self):
        self.sign_in_as("Chief Metrologist", "Chief Meteorologist")
        saved = self.client.post("/uncertainty/api/save", json=self.payload()).get_json()["record"]
        response = self.client.post(
            f"/uncertainty/api/records/calculation/{saved['id']}/workflow",
            json={"action":"submit"})
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(response.get_json()["status"], "Approved")
        connection = database.get_connection()
        record = connection.execute("""SELECT status,submitted_by,approved_by,assigned_reviewer,
            assigned_approver FROM uncertainty_calculations WHERE id=?""", (saved["id"],)).fetchone()
        history = connection.execute("""SELECT action FROM approval_history
            WHERE entity_type='uncertainty_calculation' AND entity_id=? ORDER BY id""",
            (saved["id"],)).fetchall()
        tasks = connection.execute("""SELECT COUNT(*) FROM workflow_tasks
            WHERE entity_type='uncertainty_calculation' AND entity_id=?""", (saved["id"],)).fetchone()[0]
        connection.close()
        self.assertEqual(tuple(record),
            ("Approved", "Chief Metrologist", "Chief Metrologist", None, None))
        self.assertEqual([item[0] for item in history[-2:]], ["submit", "auto_approve"])
        self.assertEqual(tasks, 0)

    def test_chief_can_take_over_review_and_approval_tasks(self):
        saved = self.client.post("/uncertainty/api/save", json=self.payload()).get_json()["record"]
        self.submit_for_review(saved["id"])
        self.sign_in_as("Chief Metrologist", "Chief Meteorologist")
        reviewed = self.client.post(
            f"/uncertainty/api/records/calculation/{saved['id']}/workflow",
            json={"action":"review", "comment":"Chief authority review"})
        self.assertEqual(reviewed.status_code, 200, reviewed.get_data(as_text=True))
        approved = self.client.post(
            f"/uncertainty/api/records/calculation/{saved['id']}/workflow",
            json={"action":"approve", "comment":"Chief authority approval"})
        self.assertEqual(approved.status_code, 200, approved.get_data(as_text=True))
        self.assertEqual(approved.get_json()["status"], "Approved")

    def test_completed_job_blocks_new_uncertainty_until_authorized_reopen(self):
        connection = database.get_connection()
        connection.execute("UPDATE calibration_jobs SET status='Completed' WHERE id=?", (self.job_id,))
        connection.commit(); connection.close()
        response = self.client.post("/uncertainty/api/calculate", json=self.payload())
        self.assertEqual(response.status_code, 422)
        self.assertIn("HOD authorization", response.get_json()["error"])

    def test_revision_requires_reason(self):
        saved = self.client.post("/uncertainty/api/save", json=self.payload()).get_json()["record"]
        self.submit_for_review(saved["id"])
        self.review_and_approve(saved["id"])
        response = self.client.post(f"/uncertainty/api/records/calculation/{saved['id']}/revision", json={})
        self.assertEqual(response.status_code, 422)
        self.assertIn("reason", response.get_json()["error"].lower())

    def test_approved_uncertainty_allows_completion_and_controlled_job_reopen(self):
        saved = self.client.post("/uncertainty/api/save", json=self.payload()).get_json()["record"]
        self.submit_for_review(saved["id"])
        self.review_and_approve(saved["id"])
        response = self.client.post(f"/projects/jobs/{self.job_id}/complete")
        self.assertEqual(response.status_code, 302)
        self.sign_in_as("Flow Analyst", "Technician")
        response = self.client.post(f"/projects/jobs/{self.job_id}/request-reopen",
            data={"reason":"Additional customer flow point"})
        self.assertEqual(response.status_code, 302)
        connection = database.get_connection()
        request_id = connection.execute("SELECT id FROM job_reopen_requests WHERE job_id=?", (self.job_id,)).fetchone()[0]
        connection.close()
        self.sign_in_as("HOD Reviewer", "HOD")
        response = self.client.post(f"/projects/jobs/{self.job_id}/authorize-reopen",
            data={"request_id":request_id,"comment":"Authorized for the additional point"})
        self.assertEqual(response.status_code, 302)
        connection = database.get_connection()
        statuses = connection.execute("""SELECT j.status,u.status FROM calibration_jobs j
            JOIN uncertainty_calculations u ON u.job_id=j.id WHERE u.id=?""", (saved["id"],)).fetchone()
        reopen = connection.execute("SELECT status,authorized_by FROM job_reopen_requests WHERE id=?", (request_id,)).fetchone()
        audit_actions = {row[0] for row in connection.execute(
            "SELECT action FROM audit_trail WHERE entity_type='calibration_job' AND entity_id=?",
            (self.job_id,)).fetchall()}
        connection.close()
        self.assertEqual(tuple(statuses), ("In Progress", "Approved"))
        self.assertEqual(tuple(reopen), ("Authorized", "HOD Reviewer"))
        self.assertTrue({"complete", "request_reopen", "authorize_reopen"}.issubset(audit_actions))

    def test_cmc_is_separate_by_method_and_compared_on_backend(self):
        cmc = self.payload("cmcGrav"); cmc["jobId"]=""; cmc["reason"]="Capability review"
        saved = self.client.post("/uncertainty/api/save", json=cmc).get_json()["record"]
        response = self.submit_for_review(saved["id"], "cmc")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.review_and_approve(saved["id"], "cmc")
        result = self.calculate()
        self.assertEqual(len(result["cmcComparison"]), 1)
        self.assertIsNotNone(result["cmcComparison"][0]["applicableCmc"])
        revision = self.client.post(f"/uncertainty/api/records/cmc/{saved['id']}/revision",
            json={"reason":"Annual capability review"})
        self.assertEqual(revision.status_code, 200, revision.get_data(as_text=True))
        self.assertEqual(revision.get_json()["record"]["revision"], 2)

    def test_role_permissions_separate_calculation_and_approval(self):
        self.assertTrue(Permissions.can("Technician", "uncertainty_calculate"))
        self.assertTrue(Permissions.can("Technician", "uncertainty_save"))
        self.assertFalse(Permissions.can("Technician", "uncertainty_approve"))
        self.assertFalse(Permissions.can("Manager", "uncertainty_approve"))
        self.assertTrue(Permissions.can("HOD", "uncertainty_approve"))


if __name__ == "__main__":
    unittest.main()
