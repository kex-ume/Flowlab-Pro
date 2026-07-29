from dataclasses import dataclass


@dataclass(slots=True)
class CalibrationRecord:
    id: int | None = None
    equipment_id: int | None = None
    calibration_date: str = ""
    next_due_date: str = ""
    calibrated_by: str = ""
    certificate_path: str = ""
    remarks: str = ""
    created_at: str = ""