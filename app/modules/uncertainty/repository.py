import json

from app.database.database import managed_connection


class UncertaintyRepository:
    def profiles(self):
        with managed_connection() as conn:
            return conn.execute("""SELECT p.id, e.asset_number, e.equipment_name, e.equipment_type,
                e.is_reference_standard, e.next_calibration_date, e.certificate_path, p.version,
                p.certificate_number, p.standard_uncertainty, p.coverage_factor, p.is_active,
                ec.operating_range_min, ec.operating_range_max, ec.operating_unit,
                CASE WHEN e.next_calibration_date IS NULL THEN 'No due date'
                     WHEN e.next_calibration_date < date('now','localtime') THEN 'Expired'
                     WHEN e.next_calibration_date <= date('now','localtime','+30 days') THEN 'Expiring'
                     ELSE 'Valid' END
                FROM uncertainty_profiles p JOIN laboratory_equipment e ON e.id=p.equipment_id
                LEFT JOIN equipment_capabilities ec ON ec.equipment_id=e.id
                ORDER BY e.equipment_name, p.version DESC""").fetchall()

    def equipment(self):
        with managed_connection() as conn:
            return conn.execute("SELECT id, asset_number || ' - ' || equipment_name FROM laboratory_equipment WHERE is_active=1 ORDER BY equipment_name").fetchall()

    def meter_types(self):
        with managed_connection() as conn:
            return conn.execute("""SELECT DISTINCT meter_type FROM calibration_methods
                WHERE meter_type IS NOT NULL AND TRIM(meter_type) <> ''
                ORDER BY meter_type""").fetchall()

    def approved_methods(self):
        with managed_connection() as conn:
            return conn.execute("""SELECT DISTINCT method_name FROM calibration_methods
                WHERE is_active=1 OR status='Approved' ORDER BY method_name""").fetchall()

    def add_profile(self, equipment_id, version, certificate_number, standard_uncertainty, coverage_factor, actor=None):
        with managed_connection() as conn:
            conn.execute("UPDATE uncertainty_profiles SET is_active=0 WHERE equipment_id=?", (equipment_id,))
            return conn.execute("""INSERT INTO uncertainty_profiles (equipment_id, version, certificate_number, standard_uncertainty, coverage_factor, is_active)
                VALUES (?, ?, ?, ?, ?, 1)""", (equipment_id, version, certificate_number or None, standard_uncertainty, coverage_factor)).lastrowid

    def type_b_components(self):
        with managed_connection() as conn:
            return conn.execute("""SELECT id, component_name, value, unit, distribution, divisor,
                sensitivity_coefficient, source, revision, status, applies_to_method FROM type_b_library_components ORDER BY component_name, revision DESC""").fetchall()

    def add_type_b(self, name, value, unit, distribution, divisor, sensitivity, source, revision, applies_to_method):
        with managed_connection() as conn:
            return conn.execute("""INSERT INTO type_b_library_components
                (component_name,value,unit,distribution,divisor,sensitivity_coefficient,source,revision,status,applies_to_method)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Approved', ?)""", (name, value, unit, distribution, divisor, sensitivity, source, revision, applies_to_method)).lastrowid

    def active_components(self, method_type):
        with managed_connection() as conn:
            return conn.execute("""SELECT component_name, value, divisor, sensitivity_coefficient, source
                FROM type_b_library_components WHERE status='Approved'
                AND applies_to_method IN ('Both', ?)""", (method_type,)).fetchall()

    def active_profile_components(self, equipment_ids=None):
        where, params = "WHERE p.is_active=1", []
        if equipment_ids is not None:
            placeholders = ",".join("?" for _ in equipment_ids)
            where += f" AND p.equipment_id IN ({placeholders})"
            params = list(equipment_ids)
        with managed_connection() as conn:
            return conn.execute(f"""SELECT c.component_name, c.value, c.divisor, c.sensitivity_coefficient,
                COALESCE(c.source, e.asset_number) FROM uncertainty_profile_components c
                JOIN uncertainty_profiles p ON p.id=c.profile_id
                JOIN laboratory_equipment e ON e.id=p.equipment_id {where}""", params).fetchall()

    def active_profile_uncertainties(self, equipment_ids):
        if not equipment_ids:
            return []
        placeholders = ",".join("?" for _ in equipment_ids)
        with managed_connection() as conn:
            return conn.execute(f"""SELECT e.asset_number || ' profile', p.standard_uncertainty,
                p.coverage_factor, p.sensitivity FROM uncertainty_profiles p
                JOIN laboratory_equipment e ON e.id=p.equipment_id
                WHERE p.is_active=1 AND p.equipment_id IN ({placeholders})
                  AND p.standard_uncertainty IS NOT NULL""", list(equipment_ids)).fetchall()

    def current_environment(self):
        with managed_connection() as conn:
            return conn.execute("""SELECT record_date, ambient_temperature, relative_humidity,
                atmospheric_pressure, recorded_by FROM environmental_records
                WHERE record_date=date('now','localtime')""").fetchone()

    def resolve_primary_equipment(self, meter_type, method_name, flow_range):
        with managed_connection() as conn:
            rows = conn.execute("""SELECT r.equipment_role, r.equipment_id FROM primary_selection_rules r
                JOIN primary_selection_configurations c ON c.id=r.configuration_id
                WHERE c.is_active=1 AND r.meter_type=? AND r.method_name=?
                  AND ? BETWEEN r.flow_min AND r.flow_max""", (meter_type, method_name, flow_range)).fetchall()
        return {role: equipment_id for role, equipment_id in rows}

    def primary_rules(self):
        with managed_connection() as conn:
            return conn.execute("""SELECT r.id, r.meter_type, r.method_name, r.flow_min, r.flow_max,
                r.equipment_role, e.asset_number || ' - ' || e.equipment_name, c.name, c.version
                FROM primary_selection_rules r JOIN laboratory_equipment e ON e.id=r.equipment_id
                JOIN primary_selection_configurations c ON c.id=r.configuration_id
                WHERE c.is_active=1 ORDER BY r.meter_type, r.method_name, r.flow_min, r.equipment_role""").fetchall()

    def add_primary_rule(self, meter_type, method_name, flow_min, flow_max, role, equipment_id):
        with managed_connection() as conn:
            config = conn.execute("SELECT id FROM primary_selection_configurations WHERE is_active=1").fetchone()
            if config is None:
                cursor = conn.execute("INSERT INTO primary_selection_configurations (name, version, is_active) VALUES ('Primary Selection', '1.0', 1)")
                configuration_id = cursor.lastrowid
            else:
                configuration_id = config[0]
            return conn.execute("""INSERT INTO primary_selection_rules
                (configuration_id,meter_type,method_name,flow_min,flow_max,equipment_role,equipment_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)""", (configuration_id, meter_type, method_name, flow_min, flow_max, role, equipment_id)).lastrowid

    def active_configuration_id(self):
        with managed_connection() as conn:
            row = conn.execute("SELECT id FROM primary_selection_configurations WHERE is_active=1").fetchone()
            return row[0] if row else None

    def add_configuration_document(self, original_filename, file_path):
        with managed_connection() as conn:
            configuration_id = conn.execute("SELECT id FROM primary_selection_configurations WHERE is_active=1").fetchone()
            if configuration_id is None:
                configuration_id = conn.execute("INSERT INTO primary_selection_configurations (name, version, is_active) VALUES ('Primary Selection', '1.0', 1)").lastrowid
            else:
                configuration_id = configuration_id[0]
            return conn.execute("""INSERT INTO uncertainty_configuration_documents
                (configuration_id, original_filename, file_path, format) VALUES (?, ?, ?, ?)""",
                (configuration_id, original_filename, file_path, original_filename.rsplit('.', 1)[-1].lower())).lastrowid

    def save_measurement_session(self, meter_type, method_name, flow_range, report_path,
                                 observations, temperature, combined, expanded, actor=None):
        with managed_connection() as conn:
            config = conn.execute("SELECT id FROM primary_selection_configurations WHERE is_active=1").fetchone()
            return conn.execute("""INSERT INTO measurement_sessions
                (meter_type, method_name, flow_range, type_a_report_path, imported_observations,
                 report_temperature, combined_standard_uncertainty, expanded_uncertainty,
                 primary_configuration_id, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (meter_type, method_name, flow_range, report_path, json.dumps(observations),
                 temperature, combined, expanded, config[0] if config else None, actor)).lastrowid

    def environmental_records(self):
        with managed_connection() as conn:
            return conn.execute("""SELECT record_date, record_time, ambient_temperature,
                relative_humidity, atmospheric_pressure, recorded_by, instrument_used
                FROM environmental_records ORDER BY record_date DESC, record_time DESC""").fetchall()

    def save_environmental_record(self, record_date, record_time, temperature, humidity,
                                  pressure, operator, instrument):
        with managed_connection() as conn:
            conn.execute("""INSERT INTO environmental_records
                (record_date, record_time, ambient_temperature, relative_humidity,
                 atmospheric_pressure, recorded_by, instrument_used)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(record_date) DO UPDATE SET record_time=excluded.record_time,
                 ambient_temperature=excluded.ambient_temperature,
                 relative_humidity=excluded.relative_humidity,
                 atmospheric_pressure=excluded.atmospheric_pressure,
                 recorded_by=excluded.recorded_by, instrument_used=excluded.instrument_used,
                 updated_at=CURRENT_TIMESTAMP""",
                (record_date, record_time, temperature, humidity, pressure, operator, instrument))
