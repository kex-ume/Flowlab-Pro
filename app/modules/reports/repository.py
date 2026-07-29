from app.database.database import get_connection


class ReportsRepository:

    def equipment(self):

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                asset_number,
                equipment_name,
                manufacturer,
                model,
                status,
                next_calibration_date
            FROM laboratory_equipment
            ORDER BY equipment_name
        """)

        rows = cursor.fetchall()

        conn.close()

        return rows

    def calibrations(self):

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                l.equipment_name,
                c.calibration_date,
                c.next_due_date,
                c.calibrated_by
            FROM calibration_history c
            JOIN laboratory_equipment l
            ON c.equipment_id=l.id
            ORDER BY c.calibration_date DESC
        """)

        rows = cursor.fetchall()

        conn.close()

        return rows

    def maintenance(self):

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                l.equipment_name,
                m.maintenance_date,
                m.maintenance_type,
                m.performed_by,
                m.cost
            FROM maintenance_history m
            JOIN laboratory_equipment l
            ON m.equipment_id=l.id
            ORDER BY m.maintenance_date DESC
        """)

        rows = cursor.fetchall()

        conn.close()

        return rows

    def users(self):

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                username,
                full_name,
                email,
                is_active
            FROM users
            ORDER BY username
        """)

        rows = cursor.fetchall()

        conn.close()

        return rows