from datetime import datetime, timedelta

from app.database.database import get_connection
from app.modules.laboratory.calibration.models import CalibrationRecord


class CalibrationRepository:

    @staticmethod
    def _requires_certificate(cursor, equipment_id: int) -> bool:
        cursor.execute(
            "SELECT is_reference_standard FROM laboratory_equipment WHERE id=?",
            (equipment_id,),
        )
        row = cursor.fetchone()
        return bool(row and row[0])

    @classmethod
    def _validate_certificate_requirement(cls, cursor, record: CalibrationRecord):
        if cls._requires_certificate(cursor, record.equipment_id) and not record.certificate_path.strip():
            raise ValueError(
                "Primary equipment requires an uploaded calibration certificate."
            )

    def _calculate_status(self, next_due_date: str):

        due = datetime.strptime(next_due_date, "%Y-%m-%d").date()
        today = datetime.today().date()

        if due < today:
            return "Overdue"

        if due <= today + timedelta(days=30):
            return "Due Soon"

        return "Active"

    def add_record(self, record: CalibrationRecord):

        conn = get_connection()
        cursor = conn.cursor()

        self._validate_certificate_requirement(cursor, record)

        cursor.execute("""
            INSERT INTO calibration_history(
                equipment_id,
                calibration_date,
                next_due_date,
                calibrated_by,
                certificate_path,
                remarks
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            record.equipment_id,
            record.calibration_date,
            record.next_due_date,
            record.calibrated_by,
            record.certificate_path,
            record.remarks,
        ))

        status = self._calculate_status(record.next_due_date)

        cursor.execute("""
            UPDATE laboratory_equipment
            SET
                last_calibration_date=?,
                next_calibration_date=?,
                status=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (
            record.calibration_date,
            record.next_due_date,
            status,
            record.equipment_id,
        ))

        conn.commit()
        conn.close()

    def update_record(self, record: CalibrationRecord):

        conn = get_connection()
        cursor = conn.cursor()

        self._validate_certificate_requirement(cursor, record)

        cursor.execute("""
            UPDATE calibration_history
            SET
                calibration_date=?,
                next_due_date=?,
                calibrated_by=?,
                certificate_path=?,
                remarks=?
            WHERE id=?
        """, (
            record.calibration_date,
            record.next_due_date,
            record.calibrated_by,
            record.certificate_path,
            record.remarks,
            record.id,
        ))

        status = self._calculate_status(record.next_due_date)

        cursor.execute("""
            UPDATE laboratory_equipment
            SET
                last_calibration_date=?,
                next_calibration_date=?,
                status=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (
            record.calibration_date,
            record.next_due_date,
            status,
            record.equipment_id,
        ))

        conn.commit()
        conn.close()

    def get_record(self, record_id):

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM calibration_history WHERE id=?",
            (record_id,)
        )

        row = cursor.fetchone()

        conn.close()

        return row

    def get_records(self, equipment_id):

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT *
            FROM calibration_history
            WHERE equipment_id=?
            ORDER BY calibration_date DESC
        """, (equipment_id,))

        rows = cursor.fetchall()

        conn.close()

        return rows

    def delete_record(self, record_id):

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM calibration_history WHERE id=?",
            (record_id,)
        )

        conn.commit()
        conn.close()
