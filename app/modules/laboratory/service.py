from __future__ import annotations

from datetime import date, timedelta

from app.modules.laboratory.models import LaboratoryAsset
from app.database.database import get_connection


class LaboratoryService:
    @staticmethod
    def calculate_next_due_date(last_date: date, interval_months: int) -> date:
        days = int(interval_months * 30.44)
        return last_date + timedelta(days=days)

    @staticmethod
    def determine_status(next_due: date) -> str:
        if next_due < date.today():
            return "Expired"

        connection = get_connection()
        try:
            row = connection.execute("""SELECT setting_value FROM system_settings
                WHERE setting_key='equipment_due_soon_days'""").fetchone()
            warning_days = max(0, int(row[0])) if row else 30
        except (TypeError, ValueError):
            warning_days = 30
        finally:
            connection.close()
        if next_due <= date.today() + timedelta(days=warning_days):
            return "Due Soon"

        return "Active"

    @staticmethod
    def is_calibration_due(asset: LaboratoryAsset) -> bool:
        if asset.next_calibration_date is None:
            return False

        return asset.next_calibration_date <= date.today()

    @staticmethod
    def validate_asset(asset: LaboratoryAsset) -> None:
        if not asset.asset_number.strip():
            raise ValueError("Asset number is required.")

        if not asset.equipment_name.strip():
            raise ValueError("Equipment name is required.")

        if asset.calibration_interval_months is None or asset.calibration_interval_months < 1:
            raise ValueError("Calibration interval must be greater than zero.")
