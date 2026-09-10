import io
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

import app.database.database as database
from app.database.init_db import initialize_database
from app.modules.auth.service import AuthService
from web_app import app


class EquipmentWebTests(unittest.TestCase):
    def setUp(self):
        self.original_path = database.DATABASE_PATH
        self.tempdir = tempfile.TemporaryDirectory()
        database.DATABASE_PATH = Path(self.tempdir.name) / "equipment.db"
        initialize_database()
        connection = database.get_connection()
        connection.execute("""INSERT INTO laboratory_equipment
            (asset_number,equipment_name,serial_number,model,last_calibration_date,
             next_calibration_date,is_active)
            VALUES ('EQ-001','Reference Flow Meter','SN-10','FM-500','2026-01-10','2099-01-10',1)""")
        self.equipment_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
        connection.commit()
        connection.close()
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def tearDown(self):
        database.DATABASE_PATH = self.original_path
        self.tempdir.cleanup()

    def test_register_uses_equipment_only_heading_and_expected_columns(self):
        response = self.client.get("/equipment")
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("<div class=\"page-title\">Equipment</div>", page)
        self.assertNotIn("Calibration Programme</span>", page)
        for heading in ("Equipment ID", "Serial No.", "Model", "Validity", "Cal Date", "Due Date", "Report"):
            self.assertIn(heading, page)

    def test_placeholder_records_are_hidden_and_csv_list_is_imported(self):
        connection = database.get_connection()
        connection.execute("""INSERT INTO laboratory_equipment
            (asset_number,equipment_name,is_active) VALUES ('BAD-PLACEHOLDER','Equipment',1)""")
        connection.commit()
        connection.close()
        equipment_csv = (
            "Equipment,Equipment ID,Serial No.,Model,Cal Date,Due Date,Manufacturer,Equipment Type\n"
            "Digital Pressure Gauge,PG-020,SN-200,DPG-10,2026-06-01,2027-06-01,Wika,Pressure\n"
        ).encode()
        response = self.client.post("/equipment", data={
            "action": "upload",
            "equipment_list": (io.BytesIO(equipment_csv), "equipment.csv"),
        }, content_type="multipart/form-data", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("Digital Pressure Gauge", page)
        self.assertIn("PG-020", page)
        self.assertNotIn("BAD-PLACEHOLDER", page)
        connection = database.get_connection()
        imported = connection.execute("""SELECT serial_number,model,last_calibration_date,
            next_calibration_date FROM laboratory_equipment WHERE asset_number='PG-020'""").fetchone()
        connection.close()
        self.assertEqual(imported, ("SN-200", "DPG-10", "2026-06-01", "2027-06-01"))

    def test_calibration_and_maintenance_are_appended(self):
        calibration = {
            "action": "calibration", "calibration_date": "2026-08-01",
            "calibrated_by": "Accredited Lab",
            "certificate_number": "CERT-1", "uncertainty_value": "0.10",
            "uncertainty_unit": "%", "uncertainty_input_type": "Expanded / Certificate Uncertainty",
            "coverage_factor": "2", "classification": "Primary", "result": "Pass",
            "range_min": "0", "range_max": "100", "range_unit": "L/min",
            "validity_value": "1", "validity_unit": "Years",
            "source_name": "Reference flow meter calibration uncertainty",
            "sensitivity_coefficient": "1", "degrees_of_freedom": "50",
            "certificate": (io.BytesIO(b"%PDF-1.4\n%test"), "certificate.pdf"),
        }
        self.assertEqual(self.client.post(f"/equipment/{self.equipment_id}", data=calibration,
            content_type="multipart/form-data").status_code, 302)
        maintenance = {
            "action": "maintenance", "maintenance_date": "2026-08-02",
            "maintenance_type": "Preventive", "performed_by": "Technician",
            "cost": "125", "currency": "NGN", "work_performed": "Inspection",
            "metrological_impact": "None",
        }
        self.client.post(f"/equipment/{self.equipment_id}", data=maintenance)
        self.client.post(f"/equipment/{self.equipment_id}", data=maintenance)
        connection = database.get_connection()
        counts = (
            connection.execute("SELECT COUNT(*) FROM calibration_history WHERE equipment_id=?", (self.equipment_id,)).fetchone()[0],
            connection.execute("SELECT COUNT(*) FROM maintenance_history WHERE equipment_id=?", (self.equipment_id,)).fetchone()[0],
        )
        profile = connection.execute("""SELECT expanded_uncertainty,standard_uncertainty,is_active,
            source_name,uncertainty_unit,evaluation_basis,divisor,sensitivity,degrees_of_freedom
            FROM uncertainty_profiles WHERE equipment_id=?""", (self.equipment_id,)).fetchone()
        connection.close()
        self.assertEqual(counts, (1, 2))
        self.assertEqual(profile, (0.1, 0.05, 1, "Reference flow meter calibration uncertainty",
            "%", "expanded", 2.0, 1.0, 50.0))

    def test_due_soon_setting_controls_status(self):
        due = (date.today() + timedelta(days=10)).isoformat()
        connection = database.get_connection()
        connection.execute("UPDATE laboratory_equipment SET next_calibration_date=? WHERE id=?", (due, self.equipment_id))
        connection.execute("UPDATE system_settings SET setting_value='5' WHERE setting_key='equipment_due_soon_days'")
        connection.commit(); connection.close()
        self.assertIn("Active", self.client.get("/equipment").get_data(as_text=True))
        self.client.post("/settings", data={"equipment_due_soon_days": "15"})
        page = self.client.get("/equipment").get_data(as_text=True)
        self.assertIn("Due Soon", page)

    def test_invalid_dates_do_not_save_and_notes_are_historical(self):
        response = self.client.post(f"/equipment/{self.equipment_id}", data={
            "action": "calibration", "calibration_date": "2027-08-01",
            "next_due_date": "2026-08-01", "calibrated_by": "Lab",
            "classification": "Primary Equipment", "coverage_factor": "2",
            "source_name": "Reference flow meter calibration uncertainty",
            "sensitivity_coefficient": "1", "degrees_of_freedom": "50",
        }, follow_redirects=True)
        self.assertIn("Required calibration fields", response.get_data(as_text=True))
        connection = database.get_connection()
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM calibration_history").fetchone()[0], 0)
        connection.close()
        self.client.post(f"/equipment/{self.equipment_id}", data={
            "action": "maintenance", "maintenance_date": "2026-08-02",
            "maintenance_type": "Preventive", "cost": "20", "notes": "Initial inspection",
        })
        self.client.post(f"/equipment/{self.equipment_id}", data={
            "action": "maintenance", "maintenance_date": "2026-08-03",
            "maintenance_type": "Corrective", "cost": "30", "notes": "Seal replaced",
        })
        connection = database.get_connection()
        notes = connection.execute("SELECT note FROM record_notes WHERE entity_type='maintenance' ORDER BY id").fetchall()
        connection.close()
        self.assertEqual(notes, [("Initial inspection",), ("Seal replaced",)])

    def test_report_reopens_and_delete_is_soft_with_audit(self):
        response = self.client.post(f"/equipment/{self.equipment_id}", data={
            "action": "calibration", "calibration_date": "2026-08-01",
            "calibrated_by": "Lab", "certificate_number": "CERT-FILE-1",
            "uncertainty_value": "0.10", "uncertainty_unit": "%",
            "uncertainty_input_type": "Expanded / Certificate Uncertainty",
            "range_min": "0", "range_max": "100", "range_unit": "L/min",
            "validity_value": "1", "validity_unit": "Years", "result": "Pass",
            "classification": "Primary Equipment", "coverage_factor": "2",
            "source_name": "Reference flow meter calibration uncertainty",
            "sensitivity_coefficient": "1", "degrees_of_freedom": "50",
            "certificate": (io.BytesIO(b"%PDF-1.4\n%test"), "certificate.pdf"),
        }, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 302)
        connection = database.get_connection()
        record_id = connection.execute("SELECT id FROM calibration_history").fetchone()[0]
        connection.close()
        report = self.client.get(f"/equipment/{self.equipment_id}/file/calibration/{record_id}")
        self.assertEqual(report.status_code, 200)
        self.client.post(f"/equipment/{self.equipment_id}/calibration/{record_id}/delete",
            data={"reason": "Incorrect controlled upload"})
        connection = database.get_connection()
        deleted = connection.execute("SELECT is_deleted,deleted_by FROM calibration_history WHERE id=?", (record_id,)).fetchone()
        audit = connection.execute("SELECT action FROM audit_trail WHERE entity_type='calibration' AND entity_id=? ORDER BY id DESC", (record_id,)).fetchone()
        connection.close()
        self.assertEqual(deleted[0], 1)
        self.assertTrue(deleted[1])
        self.assertEqual(audit[0], "soft_delete")
        self.assertEqual(self.client.get(f"/equipment/{self.equipment_id}/file/calibration/{record_id}").status_code, 404)

    def test_empty_state_and_responsive_rules(self):
        connection = database.get_connection()
        connection.execute("UPDATE laboratory_equipment SET is_active=0")
        connection.commit(); connection.close()
        page = self.client.get("/equipment").get_data(as_text=True)
        self.assertIn("No equipment has been added.", page)
        self.assertIn("Add Equipment", page)
        css = Path("static/responsive.css").read_text(encoding="utf-8")
        self.assertIn("overflow-x:auto", css)
        self.assertIn("max-width:580px", css)
        self.assertIn("prefers-reduced-motion", css)


class FreshDatabaseWebTests(unittest.TestCase):
    def setUp(self):
        self.original_path = database.DATABASE_PATH
        self.tempdir = tempfile.TemporaryDirectory()
        database.DATABASE_PATH = Path(self.tempdir.name) / "fresh.db"
        initialize_database()
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def tearDown(self):
        database.DATABASE_PATH = self.original_path
        self.tempdir.cleanup()

    def test_iso_clause_checklist_retains_evidence_and_controls_assessment(self):
        landing = self.client.get("/iso17025/clause-checklist")
        self.assertEqual(landing.status_code, 200)
        page = landing.get_data(as_text=True)
        self.assertIn("ISO/IEC 17025 Clause Checklist", page)
        self.assertIn("0 applicable clauses", page)
        connection = database.get_connection()
        clause_id = connection.execute(
            "SELECT id FROM iso_clauses WHERE clause_code='4.2'").fetchone()[0]
        connection.close()
        self.assertEqual(self.client.get("/iso17025/clause-scope").status_code,403)
        self.assertEqual(self.client.get(
            f"/iso17025/clause-checklist/{clause_id}").status_code,404)
        with self.client.session_transaction() as login:
            login.update(user_id=1, username="chief", full_name="Chief Metrologist",
                role_name="Chief Meteorologist")
        response = self.client.post("/iso17025/clause-scope", data={
            f"decision_{clause_id}":"Applicable",
            f"justification_{clause_id}":"Confidentiality applies to all laboratory and field work"})
        self.assertEqual(response.status_code,302)
        self.assertIn("Confidentiality", self.client.get(
            "/iso17025/clause-checklist").get_data(as_text=True))
        detail_page = self.client.get(f"/iso17025/clause-checklist/{clause_id}").get_data(as_text=True)
        self.assertIn('id="clauseEvidenceForm"', detail_page)
        self.assertIn("data-collapsible-form hidden", detail_page)
        self.assertIn("4.2.1 — Confidentiality policy and personnel undertaking", detail_page)
        self.assertIn("4.2.4",detail_page)
        self.assertIn("Require personnel and external parties",detail_page)
        response = self.client.post(f"/iso17025/clause-checklist/{clause_id}", data={
            "applicability":"Applicable", "compliance_status":"Compliant",
            "finding":"Confidentiality arrangements reviewed", "last_review_date":"2026-09-09",
            "next_review_date":"2027-09-09"})
        self.assertEqual(response.status_code, 302)
        response = self.client.post(f"/iso17025/clause-checklist/{clause_id}/workflow",
            data={"action":"submit"}, follow_redirects=True)
        self.assertIn("Approval is blocked", response.get_data(as_text=True))
        connection = database.get_connection()
        connection.execute("UPDATE iso_clause_assessments SET compliance_status='Partially Compliant' WHERE clause_id=?", (clause_id,))
        connection.commit(); connection.close()
        response = self.client.post(f"/iso17025/clause-checklist/{clause_id}/workflow",
            data={"action":"submit"}, follow_redirects=True)
        self.assertIn("Approval is blocked", response.get_data(as_text=True))
        connection = database.get_connection()
        requirement_id = connection.execute("""SELECT id FROM iso_clause_evidence_requirements
            WHERE clause_id=?""", (clause_id,)).fetchone()[0]
        connection.close()
        response = self.client.post(f"/iso17025/clause-checklist/{clause_id}/evidence", data={
            "requirement_id":str(requirement_id), "title":"Confidentiality agreement",
            "document_number":"POL-004", "revision":"1",
            "document_owner":"Quality Manager", "effective_date":"2026-09-09",
            "retention_until":"2030-09-09",
            "evidence_file":(io.BytesIO(b"%PDF-1.4 evidence"),"confidentiality.pdf")},
            content_type="multipart/form-data")
        self.assertEqual(response.status_code, 302)
        self.client.post(f"/iso17025/clause-checklist/{clause_id}/workflow",
            data={"action":"submit"})
        connection = database.get_connection()
        assessment_status = connection.execute("""SELECT status FROM iso_clause_assessments
            WHERE clause_id=?""", (clause_id,)).fetchone()[0]
        evidence_status = connection.execute("""SELECT status FROM iso_clause_evidence
            WHERE clause_id=?""", (clause_id,)).fetchone()[0]
        clause_compliance = connection.execute("""SELECT compliance_status FROM iso_clause_assessments
            WHERE clause_id=?""", (clause_id,)).fetchone()[0]
        connection.close()
        self.assertEqual((assessment_status,evidence_status),("Approved","Approved"))
        self.assertEqual(clause_compliance,"Compliant")
        detail_page = self.client.get(f"/iso17025/clause-checklist/{clause_id}").get_data(as_text=True)
        self.assertIn("Active", detail_page)

    def test_iso_workspace_and_coveter_render_for_authorized_profiles(self):
        iso_page=self.client.get("/workspace/iso17025")
        self.assertEqual(iso_page.status_code,200)
        self.assertNotIn("Accreditation Scope &amp; Clause Applicability",iso_page.get_data(as_text=True))
        with self.client.session_transaction() as login:
            login.update(user_id=1,username="chief",full_name="Chief Metrologist",
                role_name="Chief Meteorologist")
        iso_page=self.client.get("/workspace/iso17025")
        self.assertEqual(iso_page.status_code,200)
        self.assertIn("Accreditation Scope &amp; Clause Applicability",iso_page.get_data(as_text=True))
        tools=self.client.get("/tools").get_data(as_text=True)
        self.assertIn("Coveter",tools);self.assertIn("Uncertainty Calculator",tools)
        converter=self.client.get("/tools/coveter")
        self.assertEqual(converter.status_code,200)
        page=converter.get_data(as_text=True)
        for unit in ("L/min","m³/h","US gal/min (GPM)","bbl/day (BPD)","ft³/min (CFM)"):
            self.assertIn(unit,page)
        self.assertIn('id="conversionBasisEquation"',page)
        self.assertIn('id="converterBasisInline"',page)
        converter_script=(Path("static")/"converter.js").read_text(encoding="utf-8")
        self.assertIn("updateBasis",converter_script)
        self.assertIn("1 petroleum barrel = 0.158987294928 m³",converter_script)

    def test_personnel_clause_register_and_controlled_document_approval(self):
        connection = database.get_connection()
        clause_id = connection.execute("SELECT id FROM iso_clauses WHERE clause_code='6.2'").fetchone()[0]
        chief_role = connection.execute("SELECT id FROM roles WHERE name='Chief Meteorologist'").fetchone()[0]
        supervisor_role = connection.execute("SELECT id FROM roles WHERE name='Supervisor'").fetchone()[0]
        technician_role = connection.execute("SELECT id FROM roles WHERE name='Technician'").fetchone()[0]
        chief_id = connection.execute("""INSERT INTO users(username,password_hash,full_name,role_id,is_active)
            VALUES ('personnelchief','hash','Personnel Chief',?,1)""",(chief_role,)).lastrowid
        supervisor_id = connection.execute("""INSERT INTO users(username,password_hash,full_name,role_id,is_active)
            VALUES ('personnelsupervisor','hash','Personnel Supervisor',?,1)""",(supervisor_role,)).lastrowid
        technician_id = connection.execute("""INSERT INTO users(username,password_hash,full_name,role_id,is_active)
            VALUES ('personneltech','hash','Personnel Technician',?,1)""",(technician_role,)).lastrowid
        connection.execute("""INSERT INTO iso_clause_assessments
            (clause_id,applicability,applicability_set_by,compliance_status,status,created_by)
            VALUES (?,'Applicable','Personnel Chief','Not Assessed','Draft','Personnel Chief')
            ON CONFLICT(clause_id) DO UPDATE SET applicability='Applicable',applicability_set_by='Personnel Chief'""",(clause_id,))
        connection.commit(); connection.close()
        with self.client.session_transaction() as login:
            login.update(user_id=technician_id,username="personneltech",full_name="Personnel Technician",role_name="Technician")
        page = self.client.get(f"/iso17025/clause-checklist/{clause_id}/personnel?user_id={technician_id}").get_data(as_text=True)
        self.assertIn("Personnel Compliance Register",page)
        self.assertIn("Lab Role",page); self.assertIn("Impartiality",page)
        self.assertIn("Confidentiality",page); self.assertIn("Job Description",page)
        self.assertIn("6.2.6 — Authorization Letter",page)
        self.assertNotIn("Active account",page); self.assertNotIn("Laboratory role</span>",page)
        self.assertIn("6.2.1",page); self.assertIn("6.2.6",page)
        self.assertIn("6.2.2 / 6.2.4 — Job Description",page)
        response = self.client.post(f"/iso17025/personnel/{technician_id}/documents",data={
            "document_type":"Impartiality Assessment","document_number":"IMP-001","revision":"1",
            "issued_date":"2026-09-10","reviewer_user_id":str(supervisor_id),
            "document_file":(io.BytesIO(b"%PDF-1.4 personnel"),"impartiality.pdf")},
            content_type="multipart/form-data")
        self.assertEqual(response.status_code,302)
        duplicate = self.client.post(f"/iso17025/personnel/{technician_id}/documents",data={
            "document_type":"Impartiality Assessment","document_number":"IMP-001","revision":"duplicate",
            "issued_date":"2026-09-10","reviewer_user_id":str(supervisor_id),
            "document_file":(io.BytesIO(b"%PDF-1.4 duplicate"),"duplicate.pdf")},
            content_type="multipart/form-data",follow_redirects=True)
        self.assertIn("Document number IMP-001 is already registered",duplicate.get_data(as_text=True))
        connection = database.get_connection()
        document_id,status = connection.execute("SELECT id,status FROM personnel_documents").fetchone()
        task = connection.execute("""SELECT assigned_user_id,status FROM workflow_tasks
            WHERE entity_type='personnel_document' AND entity_id=?""",(document_id,)).fetchone()
        connection.close()
        self.assertEqual(status,"Submitted for Review"); self.assertEqual(task,(supervisor_id,"Pending"))
        with self.client.session_transaction() as login:
            login.update(user_id=supervisor_id,username="personnelsupervisor",full_name="Personnel Supervisor",role_name="Supervisor")
        self.client.post(f"/iso17025/personnel-documents/{document_id}/workflow",data={"action":"approve"})
        connection = database.get_connection()
        approved = connection.execute("SELECT status,is_current,approved_by FROM personnel_documents WHERE id=?",(document_id,)).fetchone()
        connection.close()
        self.assertEqual(approved,("Approved",1,"Personnel Supervisor"))
        with self.client.session_transaction() as login:
            login.update(user_id=chief_id,username="personnelchief",full_name="Personnel Chief",role_name="Chief Meteorologist")
        self.client.post(f"/iso17025/personnel/{technician_id}/documents",data={
            "document_type":"Impartiality Assessment","document_number":"IMP-002","revision":"2",
            "issued_date":"2026-09-11","document_file":(io.BytesIO(b"%PDF-1.4 replacement"),"impartiality-v2.pdf")},
            content_type="multipart/form-data")
        connection = database.get_connection()
        versions = connection.execute("""SELECT revision,status,is_current,superseded_by_id
            FROM personnel_documents WHERE user_id=? ORDER BY id""",(technician_id,)).fetchall()
        connection.close()
        self.assertEqual(versions[0][0:3],("1","Approved",0))
        self.assertIsNotNone(versions[0][3]); self.assertEqual(versions[1][0:3],("2","Approved",1))
        personnel_page=self.client.get(f"/iso17025/personnel/{technician_id}",follow_redirects=True).get_data(as_text=True)
        self.assertIn("Superseded",personnel_page);self.assertIn("Save Revision",personnel_page)
        connection=database.get_connection()
        replacement_id=connection.execute("SELECT id FROM personnel_documents WHERE revision='2'").fetchone()[0]
        connection.close()
        self.client.post(f"/iso17025/personnel-documents/{replacement_id}/edit",data={
            "document_number":"IMP-003","revision":"3","issued_date":"2026-09-12"})
        connection=database.get_connection()
        edited_id=connection.execute("SELECT id FROM personnel_documents WHERE revision='3'").fetchone()[0]
        edited_state=connection.execute("SELECT status,is_current FROM personnel_documents WHERE id=?",(edited_id,)).fetchone()
        connection.close()
        self.assertEqual(edited_state,("Approved",1))
        self.client.post(f"/iso17025/personnel-documents/{edited_id}/delete")
        connection=database.get_connection()
        restored=connection.execute("SELECT is_current FROM personnel_documents WHERE id=?",(replacement_id,)).fetchone()[0]
        deleted=connection.execute("SELECT is_deleted FROM personnel_documents WHERE id=?",(edited_id,)).fetchone()[0]
        connection.close()
        self.assertEqual((restored,deleted),(1,1))
        with self.client.session_transaction() as login:
            login.update(user_id=technician_id,username="personneltech",full_name="Personnel Technician",role_name="Technician")
        self.client.post(f"/iso17025/clause-checklist/{clause_id}/personnel/register",data={
            "full_name":"New Operator","email":"operator@example.com","requested_role":"Operator"})
        connection = database.get_connection()
        registration = connection.execute("SELECT status,assigned_reviewer_id FROM personnel_registrations").fetchone()
        registration_task = connection.execute("""SELECT assigned_user_id,status FROM workflow_tasks
            WHERE entity_type='personnel_registration'""").fetchone()
        connection.close()
        self.assertEqual(registration,("Pending",chief_id)); self.assertEqual(registration_task,(chief_id,"Pending"))

    def test_fresh_database_has_zero_counts_and_real_empty_states(self):
        connection = database.get_connection()
        operational_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("laboratory_equipment", "calibration_jobs", "customers", "projects",
                          "calibration_history", "maintenance_history", "controlled_documents")
        }
        connection.close()
        self.assertTrue(all(value == 0 for value in operational_counts.values()))
        dashboard = self.client.get("/").get_data(as_text=True)
        self.assertGreaterEqual(dashboard.count(">0<"), 4)
        self.assertIn("No equipment has been added to the calibration programme.", dashboard)
        self.assertIn("No equipment has been added.", self.client.get("/equipment").get_data(as_text=True))
        self.assertIn("No jobs match the selected filters.", self.client.get("/projects/jobs").get_data(as_text=True))
        self.assertIn("No controlled document has been uploaded.", self.client.get("/documents").get_data(as_text=True))

    def test_equipment_location_can_be_created_edited_and_viewed(self):
        response = self.client.post("/equipment", data={
            "equipment_name":"Reference Pressure Gauge", "asset_number":"RPG-001",
            "laboratory_location":"Pressure Laboratory · Bay 2",
            "validity_value":"12", "validity_unit":"Months"})
        self.assertEqual(response.status_code, 302)
        connection = database.get_connection()
        equipment_id,location = connection.execute("""SELECT id,laboratory_location
            FROM laboratory_equipment WHERE asset_number='RPG-001'""").fetchone()
        connection.close()
        self.assertEqual(location, "Pressure Laboratory · Bay 2")
        detail = self.client.get(f"/equipment/{equipment_id}").get_data(as_text=True)
        self.assertIn("Pressure Laboratory · Bay 2", detail)
        response = self.client.post(f"/equipment/{equipment_id}/edit", data={
            "equipment_name":"Reference Pressure Gauge", "serial_number":"",
            "manufacturer":"", "model":"", "equipment_type":"Pressure",
            "laboratory_location":"Standards Room", "validity_value":"1",
            "validity_unit":"Years", "notes":"", "reason":"Correct equipment location"})
        self.assertEqual(response.status_code, 302)
        connection = database.get_connection()
        location = connection.execute("SELECT laboratory_location FROM laboratory_equipment WHERE id=?",
            (equipment_id,)).fetchone()[0]
        connection.close()
        self.assertEqual(location, "Standards Room")

    def test_chief_document_submission_is_approved_automatically(self):
        connection = database.get_connection()
        document_id = connection.execute("""INSERT INTO controlled_documents
            (document_type,title,original_filename,file_path,status,uploaded_by)
            VALUES ('Procedure','Chief procedure','procedure.pdf','procedure.pdf','Draft','Chief Metrologist')""").lastrowid
        connection.commit(); connection.close()
        with self.client.session_transaction() as login:
            login["full_name"] = "Chief Metrologist"
            login["role_name"] = "Chief Meteorologist"
        response = self.client.post(f"/documents/{document_id}/workflow",
            data={"action":"submit"})
        self.assertEqual(response.status_code, 302)
        connection = database.get_connection()
        record = connection.execute("""SELECT status,submitted_by,approved_by,approved_at,effective_date
            FROM controlled_documents WHERE id=?""", (document_id,)).fetchone()
        history = connection.execute("""SELECT action FROM approval_history
            WHERE entity_type='controlled_document' AND entity_id=? ORDER BY id""",
            (document_id,)).fetchall()
        connection.close()
        self.assertEqual(record[0:3], ("Approved","Chief Metrologist","Chief Metrologist"))
        self.assertTrue(record[3]); self.assertTrue(record[4])
        self.assertEqual([item[0] for item in history], ["submit","auto_approve"])

    def test_capa_requires_both_documents_and_chief_closure_approval(self):
        connection=database.get_connection()
        admin_role=connection.execute("SELECT id FROM roles WHERE name='Administrator'").fetchone()[0]
        admin_id=connection.execute("""INSERT INTO users(username,password_hash,full_name,role_id,is_active)
            VALUES ('capa-admin',?,'CAPA Administrator',?,1)""",(AuthService.hash_password("AdminPassword1"),admin_role)).lastrowid
        connection.commit();connection.close()
        with self.client.session_transaction() as login:
            login.update(user_id=admin_id,username="capa-admin",full_name="CAPA Administrator",role_name="Administrator")
        invalid=self.client.post("/capa",data={"ncr_number":"NCR-DATE-INVALID","title":"Invalid chronology",
            "source":"Audit","description":"Date sequence check","owner":"Quality Officer",
            "issued_date":"2026-09-10","target_close_date":"2026-09-01",
            "issued_ncr":(io.BytesIO(b"%PDF-1.4 issued"),"issued.pdf")},
            content_type="multipart/form-data",follow_redirects=True)
        self.assertIn("Target close-out date cannot be earlier",invalid.get_data(as_text=True))
        response=self.client.post("/capa",data={"ncr_number":"NCR-TEST-001","title":"Test NCR",
            "source":"Internal audit","clause_reference":"7.10","description":"Observed nonconforming work",
            "owner":"Quality Officer","issued_date":"2026-09-01","target_close_date":"2026-09-30",
            "issued_ncr":(io.BytesIO(b"%PDF-1.4 issued"),"issued.pdf")},content_type="multipart/form-data")
        self.assertEqual(response.status_code,302)
        connection=database.get_connection();record_id=connection.execute(
            "SELECT id FROM capa_records WHERE ncr_number='NCR-TEST-001'").fetchone()[0];connection.close()
        self.client.post(f"/capa/{record_id}",data={"immediate_correction":"Stopped work",
            "root_cause":"Procedure gap","corrective_action":"Procedure revised","owner":"Quality Officer",
            "target_close_date":"2026-09-30","closeout_report":(io.BytesIO(b"%PDF-1.4 closeout"),"closeout.pdf")},
            content_type="multipart/form-data")
        self.client.post(f"/capa/{record_id}/submit",data={"reviewer_user_id":admin_id})
        connection=database.get_connection();status=connection.execute(
            "SELECT status FROM capa_records WHERE id=?",(record_id,)).fetchone()[0];task_count=connection.execute(
            "SELECT COUNT(*) FROM workflow_tasks WHERE entity_type='capa' AND status='Pending'").fetchone()[0]
        connection.close();self.assertEqual((status,task_count),("Submitted for Closure Review",1))
        self.client.post(f"/capa/{record_id}/workflow",data={"action":"approve","comment":"Evidence accepted"})
        connection=database.get_connection();status=connection.execute(
            "SELECT status FROM capa_records WHERE id=?",(record_id,)).fetchone()[0];task_count=connection.execute(
            "SELECT COUNT(*) FROM workflow_tasks WHERE entity_type='capa' AND status='Pending'").fetchone()[0]
        connection.close();self.assertEqual((status,task_count),("Closed",0))

    def test_forgot_password_requires_temporary_password_and_new_password(self):
        connection = database.get_connection()
        chief_role = connection.execute(
            "SELECT id FROM roles WHERE name='Chief Meteorologist'").fetchone()[0]
        technician_role = connection.execute(
            "SELECT id FROM roles WHERE name='Technician'").fetchone()[0]
        chief_id = connection.execute("""INSERT INTO users
            (username,password_hash,full_name,role_id,is_active)
            VALUES ('chief-reset',?,'Chief Reset',?,1)""",
            (AuthService.hash_password("ChiefPass123"),chief_role)).lastrowid
        technician_id = connection.execute("""INSERT INTO users
            (username,password_hash,full_name,role_id,is_active)
            VALUES ('tech-reset',?,'Tech Reset',?,1)""",
            (AuthService.hash_password("OldPassword1"),technician_role)).lastrowid
        connection.commit(); connection.close()

        response = self.client.post("/forgot-password", data={"username":"tech-reset"})
        self.assertEqual(response.status_code, 302)
        connection = database.get_connection()
        request_status = connection.execute("""SELECT status FROM password_reset_requests
            WHERE user_id=?""", (technician_id,)).fetchone()[0]
        notification_count = connection.execute("""SELECT COUNT(*) FROM notifications
            WHERE user_id=? AND entity_type='password_reset_request'""", (chief_id,)).fetchone()[0]
        connection.close()
        self.assertEqual(request_status, "Pending"); self.assertEqual(notification_count, 1)

        with self.client.session_transaction() as login:
            login["user_id"] = chief_id; login["username"] = "chief-reset"
            login["full_name"] = "Chief Reset"; login["role_name"] = "Chief Meteorologist"
        response = self.client.post("/users", data={"action":"reset_password",
            "user_id":technician_id,"password":"Temporary123"})
        self.assertEqual(response.status_code, 302)
        connection = database.get_connection()
        forced = connection.execute("SELECT must_change_password FROM users WHERE id=?",
            (technician_id,)).fetchone()[0]
        request_status = connection.execute("""SELECT status FROM password_reset_requests
            WHERE user_id=?""", (technician_id,)).fetchone()[0]
        connection.close()
        self.assertEqual(forced, 1); self.assertEqual(request_status, "Resolved")

        with self.client.session_transaction() as login:
            login.clear()
        response = self.client.post("/login", data={"username":"tech-reset",
            "password":"Temporary123"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/change-password"))
        response = self.client.post("/change-password", data={"password":"NewPassword123",
            "password_confirmation":"NewPassword123","recovery_email":"technician@example.com"})
        self.assertEqual(response.status_code, 302)
        connection = database.get_connection()
        password_row = connection.execute("SELECT password_hash,must_change_password FROM users WHERE id=?",
            (technician_id,)).fetchone()
        request_status = connection.execute("""SELECT status FROM password_reset_requests
            WHERE user_id=?""", (technician_id,)).fetchone()[0]
        connection.close()
        self.assertEqual(password_row,
            (AuthService.hash_password("NewPassword123"),0))
        self.assertEqual(request_status, "Completed")

    def test_registered_email_receives_single_use_password_reset_link(self):
        connection = database.get_connection()
        technician_role = connection.execute(
            "SELECT id FROM roles WHERE name='Technician'").fetchone()[0]
        user_id = connection.execute("""INSERT INTO users
            (username,password_hash,full_name,email,role_id,is_active)
            VALUES ('email-reset',?,'Email Reset','analyst@example.test',?,1)""",
            (AuthService.hash_password("OldPassword1"),technician_role)).lastrowid
        connection.commit(); connection.close()
        sent = []

        with patch("web_app.email_recovery_configured", return_value=True), \
                patch("web_app.send_password_reset_email",
                    side_effect=lambda recipient,url: sent.append((recipient,url))), \
                patch.dict("os.environ", {"FLOWLAB_PUBLIC_URL":"https://flowlab.example"}):
            response = self.client.post("/forgot-password",
                data={"identifier":"analyst@example.test"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(sent[0][0], "analyst@example.test")
        reset_path = urlparse(sent[0][1]).path
        self.assertIn("Reset password", self.client.get(reset_path).get_data(as_text=True))
        response = self.client.post(reset_path, data={
            "password":"NewEmailPassword123", "password_confirmation":"NewEmailPassword123"})
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(AuthService().authenticate("email-reset", "NewEmailPassword123"))
        self.assertIn("already been used", self.client.get(reset_path).get_data(as_text=True))
        connection = database.get_connection()
        used = connection.execute("""SELECT used_at FROM password_reset_tokens
            WHERE user_id=?""", (user_id,)).fetchone()[0]
        connection.close()
        self.assertTrue(used)

    def test_chief_sees_all_pending_tasks_and_notifications_open_the_record(self):
        connection = database.get_connection()
        chief_role = connection.execute(
            "SELECT id FROM roles WHERE name='Chief Meteorologist'").fetchone()[0]
        technician_role = connection.execute(
            "SELECT id FROM roles WHERE name='Technician'").fetchone()[0]
        chief_id = connection.execute("""INSERT INTO users
            (username,password_hash,full_name,role_id,is_active)
            VALUES ('task-chief',?,'Task Chief',?,1)""",
            (AuthService.hash_password("ChiefPassword1"),chief_role)).lastrowid
        technician_id = connection.execute("""INSERT INTO users
            (username,password_hash,full_name,role_id,is_active)
            VALUES ('task-tech',?,'Task Technician',?,1)""",
            (AuthService.hash_password("TechPassword1"),technician_role)).lastrowid
        connection.execute("""INSERT INTO workflow_tasks
            (entity_type,entity_id,task_type,status,submitted_by,assigned_to,assigned_user_id)
            VALUES ('controlled_document',42,'Approval','Pending','Task Technician','Task Technician',?)""",
            (technician_id,))
        notification_id = connection.execute("""INSERT INTO notifications
            (user_id,title,message,link,entity_type,entity_id)
            VALUES (?,'Document approval','Open the submitted document','/documents','controlled_document',42)""",
            (chief_id,)).lastrowid
        connection.commit(); connection.close()
        with self.client.session_transaction() as login:
            login.update(user_id=chief_id,username="task-chief",full_name="Task Chief",
                role_name="Chief Meteorologist")
        page = self.client.get("/reminders").get_data(as_text=True)
        self.assertIn("Actionable tasks", page)
        self.assertIn("Record 42", page)
        self.assertIn("Open task", page)
        response = self.client.get(f"/notifications/{notification_id}/open")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/documents"))
        connection = database.get_connection()
        self.assertEqual(connection.execute("SELECT is_read FROM notifications WHERE id=?",
            (notification_id,)).fetchone()[0], 1)
        connection.close()

    def test_admin_recovery_email_is_defaulted_changeable_and_routes_admin_recovery(self):
        connection = database.get_connection()
        administrator_role = connection.execute(
            "SELECT id FROM roles WHERE name='Administrator'").fetchone()[0]
        admin_id = connection.execute("""INSERT INTO users
            (username,password_hash,full_name,email,role_id,is_active)
            VALUES ('recovery-admin',?,'Recovery Admin','other@example.test',?,1)""",
            (AuthService.hash_password("AdminPassword1"),administrator_role)).lastrowid
        default_email = connection.execute("""SELECT setting_value FROM system_settings
            WHERE setting_key='admin_recovery_email'""").fetchone()[0]
        connection.commit(); connection.close()
        self.assertEqual(default_email, "ikechukwuumezulike@gmail.com")
        sent = []
        with patch("web_app.email_recovery_configured", return_value=True), \
                patch("web_app.send_password_reset_email",
                    side_effect=lambda recipient,url: sent.append((recipient,url))), \
                patch.dict("os.environ", {"FLOWLAB_PUBLIC_URL":"https://flowlab.example"}):
            self.client.post("/forgot-password", data={"identifier":default_email})
        self.assertEqual(sent[0][0], default_email)

        with self.client.session_transaction() as login:
            login.update(user_id=admin_id,username="recovery-admin",full_name="Recovery Admin",
                role_name="Administrator")
        response = self.client.post("/settings", data={
            "equipment_due_soon_days":"30", "admin_recovery_email":"new-admin@example.test"})
        self.assertEqual(response.status_code, 302)
        connection = database.get_connection()
        changed = connection.execute("""SELECT setting_value FROM system_settings
            WHERE setting_key='admin_recovery_email'""").fetchone()[0]
        connection.close()
        self.assertEqual(changed, "new-admin@example.test")

        with self.client.session_transaction() as login:
            login["role_name"] = "Chief Meteorologist"
        response = self.client.post("/settings", data={
            "equipment_due_soon_days":"30", "admin_recovery_email":"blocked@example.test"})
        self.assertEqual(response.status_code, 302)
        connection = database.get_connection()
        protected = connection.execute("""SELECT setting_value FROM system_settings
            WHERE setting_key='admin_recovery_email'""").fetchone()[0]
        connection.close()
        self.assertEqual(protected, "new-admin@example.test")


if __name__ == "__main__":
    unittest.main()
