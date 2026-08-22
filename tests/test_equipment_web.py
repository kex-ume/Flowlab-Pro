import io
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import app.database.database as database
from app.database.init_db import initialize_database
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


if __name__ == "__main__":
    unittest.main()
