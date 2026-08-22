from app.core.audit import record_audit
from app.database.database import get_connection
from app.modules.laboratory.models import LaboratoryAsset


class LaboratoryRepository:
    def __init__(self):
        self.conn = get_connection()

    def add_equipment(self, asset: LaboratoryAsset):
        cursor = self.conn.cursor()
        if asset.serial_number and cursor.execute("""SELECT 1 FROM laboratory_equipment
            WHERE LOWER(serial_number)=LOWER(?) AND is_active=1""", (asset.serial_number,)).fetchone():
            raise ValueError("Serial number is already assigned to another equipment record.")
        cursor.execute("""INSERT INTO laboratory_equipment(
            asset_number,equipment_name,equipment_type,manufacturer,model,serial_number,
            laboratory_location,department,calibration_interval_months,last_calibration_date,
            next_calibration_date,status,certificate_path,is_reference_standard,
            include_in_calibration_programme,is_active,notes,created_by,updated_by)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            asset.asset_number, asset.equipment_name, asset.equipment_type, asset.manufacturer,
            asset.model, asset.serial_number, asset.laboratory_location, asset.department,
            asset.calibration_interval_months, asset.last_calibration_date,
            asset.next_calibration_date, asset.status, asset.certificate_path,
            asset.is_reference_standard, asset.include_in_calibration_programme,
            asset.is_active, asset.notes, "Desktop user", "Desktop user"))
        equipment_id = cursor.lastrowid
        if asset.notes:
            cursor.execute("""INSERT INTO record_notes(entity_type,entity_id,note,author)
                VALUES ('equipment',?,?, 'Desktop user')""", (equipment_id, asset.notes))
        record_audit(cursor, "equipment", equipment_id, "create", "Desktop user",
            after_state={"asset_number": asset.asset_number, "equipment_name": asset.equipment_name,
                         "serial_number": asset.serial_number})
        self.conn.commit()

    def get_all_equipment(self):
        cursor = self.conn.cursor()
        setting = cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key='equipment_due_soon_days'").fetchone()
        try:
            warning_days = max(0, int(setting[0])) if setting else 30
        except (TypeError, ValueError):
            warning_days = 30
        return cursor.execute("""SELECT id,asset_number,equipment_name,equipment_type,
            manufacturer,model,serial_number,laboratory_location,department,
            calibration_interval_months,last_calibration_date,next_calibration_date,
            CASE WHEN next_calibration_date IS NOT NULL AND next_calibration_date < date('now','localtime') THEN 'Expired'
                 WHEN next_calibration_date IS NOT NULL AND next_calibration_date <= date('now','localtime',?) THEN 'Due Soon'
                 ELSE 'Active' END,
            certificate_path,is_reference_standard,is_active,notes,created_at,updated_at,
            include_in_calibration_programme
            FROM laboratory_equipment WHERE is_active=1 ORDER BY equipment_name""",
            (f"+{warning_days} days",)).fetchall()

    def get_equipment_by_id(self, equipment_id):
        return self.conn.execute("SELECT * FROM laboratory_equipment WHERE id=?", (equipment_id,)).fetchone()

    def update_equipment(self, equipment_id, asset: LaboratoryAsset):
        cursor = self.conn.cursor()
        before = cursor.execute("""SELECT asset_number,equipment_name,serial_number,notes
            FROM laboratory_equipment WHERE id=?""", (equipment_id,)).fetchone()
        if asset.serial_number and cursor.execute("""SELECT 1 FROM laboratory_equipment
            WHERE LOWER(serial_number)=LOWER(?) AND id<>? AND is_active=1""",
            (asset.serial_number, equipment_id)).fetchone():
            raise ValueError("Serial number is already assigned to another equipment record.")
        cursor.execute("""UPDATE laboratory_equipment SET asset_number=?,equipment_name=?,
            equipment_type=?,manufacturer=?,model=?,serial_number=?,laboratory_location=?,
            next_calibration_date=?,status=?,certificate_path=?,is_reference_standard=?,
            include_in_calibration_programme=?,notes=?,updated_by='Desktop user',
            updated_at=CURRENT_TIMESTAMP WHERE id=?""", (
            asset.asset_number, asset.equipment_name, asset.equipment_type, asset.manufacturer,
            asset.model, asset.serial_number, asset.laboratory_location,
            asset.next_calibration_date, asset.status, asset.certificate_path,
            asset.is_reference_standard, asset.include_in_calibration_programme,
            asset.notes, equipment_id))
        if asset.notes and (not before or asset.notes != (before[3] or "")):
            cursor.execute("""INSERT INTO record_notes(entity_type,entity_id,note,author)
                VALUES ('equipment',?,?, 'Desktop user')""", (equipment_id, asset.notes))
        record_audit(cursor, "equipment", equipment_id, "update", "Desktop user",
            {"asset_number": before[0], "equipment_name": before[1], "serial_number": before[2]} if before else None,
            {"asset_number": asset.asset_number, "equipment_name": asset.equipment_name,
             "serial_number": asset.serial_number})
        self.conn.commit()

    def delete_equipment(self, equipment_id):
        cursor = self.conn.cursor()
        before = cursor.execute("SELECT asset_number,equipment_name,is_active FROM laboratory_equipment WHERE id=?", (equipment_id,)).fetchone()
        cursor.execute("""UPDATE laboratory_equipment SET is_active=0,
            deactivated_at=CURRENT_TIMESTAMP,deactivated_by='Desktop user',
            updated_by='Desktop user',updated_at=CURRENT_TIMESTAMP WHERE id=?""", (equipment_id,))
        record_audit(cursor, "equipment", equipment_id, "deactivate", "Desktop user",
            {"asset_number": before[0], "equipment_name": before[1], "is_active": before[2]} if before else None,
            {"is_active": 0})
        self.conn.commit()

    def set_primary_equipment(self, equipment_id: int, is_primary: bool):
        cursor = self.conn.cursor()
        before = cursor.execute("SELECT is_reference_standard FROM laboratory_equipment WHERE id=?", (equipment_id,)).fetchone()
        cursor.execute("""UPDATE laboratory_equipment SET is_reference_standard=?,
            updated_by='Desktop user',updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (int(is_primary), equipment_id))
        record_audit(cursor, "equipment", equipment_id, "control_level_update", "Desktop user",
            {"is_reference_standard": before[0] if before else None},
            {"is_reference_standard": int(is_primary)})
        self.conn.commit()

    def calibration_programme(self):
        return self.conn.execute("""SELECT id,asset_number,equipment_name,equipment_type,
            calibration_interval_months,last_calibration_date,next_calibration_date,
            status,certificate_path,is_reference_standard FROM laboratory_equipment
            WHERE include_in_calibration_programme=1 AND is_active=1
            ORDER BY next_calibration_date,equipment_name""").fetchall()
