from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(slots=True)
class LaboratoryAsset:
    id: Optional[int] = None

    asset_number: str = ""
    equipment_name: str = ""
    equipment_type: str = ""

    manufacturer: str = ""
    model: str = ""
    serial_number: str = ""

    laboratory_location: str = ""
    department: str = ""

    calibration_interval_months: Optional[int] = None

    last_calibration_date: Optional[date] = None
    next_calibration_date: Optional[date] = None

    status: str = "Active"

    certificate_path: str = ""

    is_reference_standard: bool = False
    include_in_calibration_programme: bool = False
    is_active: bool = True

    notes: str = ""

    created_at: Optional[date] = None
    updated_at: Optional[date] = None
