from dataclasses import dataclass


@dataclass(slots=True)
class MaintenanceRecord:
    id: int | None = None
    equipment_id: int | None = None
    maintenance_date: str = ""
    maintenance_type: str = ""
    performed_by: str = ""
    cost: float = 0.0
    document_path: str = ""
    remarks: str = ""
    created_at: str = ""