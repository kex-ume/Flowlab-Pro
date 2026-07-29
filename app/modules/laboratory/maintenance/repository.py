from app.database.database import get_connection
from app.modules.laboratory.maintenance.models import MaintenanceRecord


class MaintenanceRepository:

    def add_record(self, record: MaintenanceRecord):

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO maintenance_history (
                equipment_id,
                maintenance_date,
                maintenance_type,
                performed_by,
                cost,
                document_path,
                remarks
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            record.equipment_id,
            record.maintenance_date,
            record.maintenance_type,
            record.performed_by,
            record.cost,
            record.document_path,
            record.remarks,
        ))

        conn.commit()
        conn.close()

    def get_records(self, equipment_id):

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT *
            FROM maintenance_history
            WHERE equipment_id=?
            ORDER BY maintenance_date DESC
        """, (equipment_id,))

        rows = cursor.fetchall()

        conn.close()

        return rows

    def get_record(self, record_id):

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM maintenance_history WHERE id=?",
            (record_id,)
        )

        row = cursor.fetchone()

        conn.close()

        return row

    def update_record(self, record: MaintenanceRecord):

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE maintenance_history
            SET
                maintenance_date=?,
                maintenance_type=?,
                performed_by=?,
                cost=?,
                document_path=?,
                remarks=?
            WHERE id=?
        """, (
            record.maintenance_date,
            record.maintenance_type,
            record.performed_by,
            record.cost,
            record.document_path,
            record.remarks,
            record.id,
        ))

        conn.commit()
        conn.close()

    def delete_record(self, record_id):

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM maintenance_history WHERE id=?",
            (record_id,)
        )

        conn.commit()
        conn.close()