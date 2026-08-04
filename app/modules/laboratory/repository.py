from app.database.database import get_connection
from app.modules.laboratory.models import LaboratoryAsset


class LaboratoryRepository:

    def __init__(self):
        self.conn = get_connection()

    def add_equipment(self, asset: LaboratoryAsset):

        cursor = self.conn.cursor()

        cursor.execute(
            """
            INSERT INTO laboratory_equipment(
                asset_number,
                equipment_name,
                equipment_type,
                manufacturer,
                model,
                serial_number,
                laboratory_location,
                department,
                calibration_interval_months,
                last_calibration_date,
                next_calibration_date,
                status,
                certificate_path,
                is_reference_standard,
                include_in_calibration_programme,
                is_active,
                notes
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                asset.asset_number,
                asset.equipment_name,
                asset.equipment_type,
                asset.manufacturer,
                asset.model,
                asset.serial_number,
                asset.laboratory_location,
                asset.department,
                asset.calibration_interval_months,
                asset.last_calibration_date,
                asset.next_calibration_date,
                asset.status,
                asset.certificate_path,
                asset.is_reference_standard,
                asset.include_in_calibration_programme,
                asset.is_active,
                asset.notes,
            ),
        )

        self.conn.commit()

    def get_all_equipment(self):

        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM laboratory_equipment
            ORDER BY equipment_name
            """
        )

        return cursor.fetchall()

    def get_equipment_by_id(self, equipment_id):

        cursor = self.conn.cursor()

        cursor.execute(
            "SELECT * FROM laboratory_equipment WHERE id=?",
            (equipment_id,),
        )

        return cursor.fetchone()

    def update_equipment(self, equipment_id, asset: LaboratoryAsset):

        cursor = self.conn.cursor()

        cursor.execute(
            """
            UPDATE laboratory_equipment
            SET
                asset_number=?,
                equipment_name=?,
                manufacturer=?,
                model=?,
                serial_number=?,
                laboratory_location=?,
                next_calibration_date=?,
                status=?,
                certificate_path=?,
                notes=?
            WHERE id=?
            """,
            (
                asset.asset_number,
                asset.equipment_name,
                asset.manufacturer,
                asset.model,
                asset.serial_number,
                asset.laboratory_location,
                asset.next_calibration_date,
                asset.status,
                asset.certificate_path,
                asset.notes,
                equipment_id,
            ),
        )

        self.conn.commit()

    def delete_equipment(self, equipment_id):

        cursor = self.conn.cursor()

        cursor.execute(
            "DELETE FROM laboratory_equipment WHERE id=?",
            (equipment_id,),
        )

        self.conn.commit()

    def set_primary_equipment(self, equipment_id: int, is_primary: bool):
        """Set the ISO 17025 control level for an existing inventory item."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE laboratory_equipment
            SET
                is_reference_standard=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (int(is_primary), equipment_id),
        )
        self.conn.commit()

    def calibration_programme(self):
        cursor = self.conn.cursor()
        return cursor.execute("""SELECT id, asset_number, equipment_name, equipment_type,
            calibration_interval_months, last_calibration_date, next_calibration_date,
            status, certificate_path, is_reference_standard
            FROM laboratory_equipment WHERE include_in_calibration_programme=1
            ORDER BY next_calibration_date, equipment_name""").fetchall()
