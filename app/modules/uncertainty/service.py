from __future__ import annotations

from math import sqrt
from statistics import stdev

from app.modules.uncertainty.repository import UncertaintyRepository


class UncertaintyService:
    """Assembles approved Type B data; it deliberately accepts no ad hoc Type B input."""

    def __init__(self, repository=None):
        self.repository = repository or UncertaintyRepository()

    def execute_measurement(self, meter_type, method_name, flow_range, observations,
                            report_path, report_temperature, actor=None, coverage_factor=2.0):
        """Execute an uncertainty assembly using controlled data only."""
        if not meter_type or not method_name:
            raise ValueError("Meter type and calibration method are required.")
        resolved = self.repository.resolve_primary_equipment(meter_type, method_name, flow_range)
        if not resolved:
            raise ValueError("No active primary-selection configuration matches this measurement session.")
        # Measurement temperature is supplied by the uploaded report. The daily
        # environmental log remains compliance evidence and is optional here.
        environment = self.repository.current_environment()
        type_a = self.type_a_from_observations(observations)
        equipment_ids = list(resolved.values())
        components = [("Type A repeatability", type_a, 1.0, 1.0, "Uploaded measurement report")]
        components += [(name, value, divisor, sensitivity, source) for name, value, divisor, sensitivity, source in self.repository.active_profile_components(equipment_ids)]
        components += [(name, value, factor, sensitivity, "Approved uncertainty profile") for name, value, factor, sensitivity in self.repository.active_profile_uncertainties(equipment_ids)]
        method_type = "Mass" if "mass" in method_name.lower() else "Volumetric" if "volum" in method_name.lower() else "Both"
        components += self.repository.active_components(method_type)
        rows, squares = [], []
        for name, value, divisor, sensitivity, source in components:
            if not divisor:
                raise ValueError(f"Approved component '{name}' has a zero divisor.")
            contribution = (float(value) / float(divisor)) * float(sensitivity)
            rows.append((name, contribution, source or "Controlled library"))
            squares.append(contribution ** 2)
        combined = sqrt(sum(squares))
        expanded = combined * coverage_factor
        session_id = self.repository.save_measurement_session(
            meter_type, method_name, flow_range, report_path, observations,
            report_temperature, combined, expanded, actor,
        )
        return {"session_id": session_id, "components": rows, "combined": combined, "expanded": expanded,
                "primaries": resolved, "environment": environment, "type_a": type_a}

    @staticmethod
    def type_a_from_observations(values):
        """Return the standard uncertainty of the mean from report observations."""
        values = [float(value) for value in values]
        if len(values) < 2:
            raise ValueError("The uploaded report needs at least two numeric observations for Type A uncertainty.")
        return stdev(values) / sqrt(len(values))
