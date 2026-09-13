import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

import app.modules.decision_rules as decision_rules


class DecisionRuleTests(unittest.TestCase):
    def sample_data(self):
        return {
            "assessment_uid": "DR-TEST-001", "assessment_id": 1, "status": "Approved",
            "job_id": 1, "job_number": "JOB-TEST-001", "customer_name": "Test Customer",
            "address": "1 Test Road", "city": "Lagos", "state": "Lagos", "country": "Nigeria",
            "meter_type": "Coriolis", "mut_description": "Flow meter", "manufacturer": "Test OEM",
            "model_number": "M-1", "mut_serial_number": "SN-1", "meter_size": "4 in",
            "flow_min": 500, "flow_max": 6000, "flow_unit": "L/min", "method_name": "Gravimetric",
            "service_request_number": "LSR-001", "service_request_revision": "04",
            "calculation_uid": "UB-001", "calculation_revision": 1,
            "rule_code": "DR-02", "rule_revision": "TBC", "specification_reference": "OEM specification",
            "specification_revision": "4", "specification_clause": "5.2", "tolerance_unit": "%",
            "statement_text": "All reported points conform.", "overall_decision": "PASS",
            "approved_by": "Chief Test", "approved_at": "2026-09-13",
            "points": [{"flow_value": 500, "flow_unit": "L/min", "error_percent": .12,
                "expanded_uncertainty": .08, "lower_tolerance": -.5, "upper_tolerance": .5,
                "lower_acceptance": -.42, "upper_acceptance": .42, "decision": "PASS"}],
        }

    def test_guarded_acceptance_uses_expanded_uncertainty(self):
        self.assertEqual(decision_rules.calculate_dr02_point(.25, .09, -.5, .5)["decision"], "PASS")
        result = decision_rules.calculate_dr02_point(.43, .10, -.5, .5)
        self.assertEqual(result["decision"], "FAIL")
        self.assertAlmostEqual(result["upper_acceptance"], .4)
        self.assertEqual(decision_rules.parse_flow_range("500 - 6,000 L/min"), (500.0, 6000.0, "L/min"))

    def test_controlled_template_and_pdf_are_generated(self):
        original_directory = decision_rules._report_directory
        with tempfile.TemporaryDirectory() as directory:
            decision_rules._report_directory = lambda: Path(directory)
            try:
                template = Path("data/templates/report_cover.xlsx")
                excel = decision_rules.generate_excel_cover(self.sample_data(), template)
                pdf = decision_rules.generate_pdf_cover(self.sample_data())
                workbook = load_workbook(excel, data_only=True)
                sheet = workbook[workbook.sheetnames[0]]
                self.assertEqual(sheet["F4"].value, "JOB-TEST-001")
                self.assertEqual(sheet["B32"].value, "CALIBRATION RESULT AND CONFORMITY")
                self.assertGreater(pdf.stat().st_size, 1000)
            finally:
                decision_rules._report_directory = original_directory


if __name__ == "__main__":
    unittest.main()
