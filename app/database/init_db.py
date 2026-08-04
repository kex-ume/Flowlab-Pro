from app.database.database import get_connection


def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()

    def ensure_column(table: str, column: str, definition: str) -> None:
        """Apply additive migrations without disrupting an existing laboratory database."""
        columns = {row[1] for row in cursor.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    # ------------------------------------------------------------------
    # Legacy Equipment Table
    # ------------------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS equipment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag TEXT NOT NULL,
            description TEXT,
            manufacturer TEXT,
            model TEXT,
            serial_number TEXT,
            calibration_due TEXT,
            status TEXT
        )
    """)

    # ------------------------------------------------------------------
    # Laboratory Equipment
    # ------------------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS laboratory_equipment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_number TEXT NOT NULL UNIQUE,
            equipment_name TEXT NOT NULL,
            equipment_type TEXT,
            manufacturer TEXT,
            model TEXT,
            serial_number TEXT,
            laboratory_location TEXT,
            department TEXT,
            calibration_interval_months INTEGER DEFAULT 12,
            last_calibration_date TEXT,
            next_calibration_date TEXT,
            status TEXT DEFAULT 'Active',
            certificate_path TEXT,
            is_reference_standard INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ------------------------------------------------------------------
    # Calibration History
    # ------------------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS calibration_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_id INTEGER NOT NULL,
            calibration_date TEXT NOT NULL,
            next_due_date TEXT NOT NULL,
            calibrated_by TEXT,
            certificate_path TEXT,
            remarks TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (equipment_id)
                REFERENCES laboratory_equipment(id)
                ON DELETE CASCADE
        )
    """)

    # ------------------------------------------------------------------
    # Maintenance History
    # ------------------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS maintenance_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_id INTEGER NOT NULL,
            maintenance_date TEXT NOT NULL,
            maintenance_type TEXT,
            performed_by TEXT,
            cost REAL DEFAULT 0,
            document_path TEXT,
            remarks TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (equipment_id)
                REFERENCES laboratory_equipment(id)
                ON DELETE CASCADE
        )
    """)

    # ------------------------------------------------------------------
    # Roles
    # ------------------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT
        )
    """)

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT,
            role_id INTEGER NOT NULL,
            is_active INTEGER DEFAULT 1,
            last_login TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(role_id) REFERENCES roles(id)
        )
    """)
    ensure_column("laboratory_equipment", "include_in_calibration_programme", "INTEGER NOT NULL DEFAULT 0")

    # ------------------------------------------------------------------
    # Customer and Project Management (SDS Section 9)
    # ------------------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL UNIQUE,
            account_reference TEXT,
            primary_contact TEXT,
            email TEXT,
            phone TEXT,
            site_address TEXT,
            status TEXT NOT NULL DEFAULT 'Active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_number TEXT NOT NULL UNIQUE,
            customer_id INTEGER NOT NULL,
            project_name TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'Draft',
            target_start_date TEXT,
            target_completion_date TEXT,
            closed_at TEXT,
            deliverable_summary TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    """)

    # ------------------------------------------------------------------
    # Method Configuration and Equipment Intelligence (SDS Sections 8, 10)
    # ------------------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS calibration_methods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meter_type TEXT NOT NULL,
            method_name TEXT NOT NULL,
            revision TEXT NOT NULL,
            procedure_reference TEXT,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'Draft',
            effective_date TEXT,
            superseded_date TEXT,
            approved_by TEXT,
            approved_at TEXT,
            is_active INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (meter_type, method_name, revision)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS controlled_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_type TEXT NOT NULL,
            document_number TEXT,
            title TEXT NOT NULL,
            revision TEXT,
            original_filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Draft',
            effective_date TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (document_type, document_number, revision)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS method_configurations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            method_id INTEGER NOT NULL,
            version TEXT NOT NULL,
            file_path TEXT,
            checksum TEXT,
            change_summary TEXT,
            status TEXT NOT NULL DEFAULT 'Draft',
            effective_date TEXT,
            approved_by TEXT,
            approved_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (method_id) REFERENCES calibration_methods(id),
            UNIQUE (method_id, version)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS method_equipment_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            method_id INTEGER NOT NULL,
            equipment_id INTEGER NOT NULL,
            equipment_role TEXT NOT NULL,
            is_required INTEGER NOT NULL DEFAULT 1,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (method_id) REFERENCES calibration_methods(id),
            FOREIGN KEY (equipment_id) REFERENCES laboratory_equipment(id),
            UNIQUE (method_id, equipment_id, equipment_role)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS primary_standards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_id INTEGER NOT NULL UNIQUE,
            expanded_uncertainty REAL,
            coverage_factor REAL DEFAULT 2,
            correction_table_reference TEXT,
            drift_value REAL,
            calibration_date TEXT,
            next_due_date TEXT,
            certificate_reference TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (equipment_id) REFERENCES laboratory_equipment(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS equipment_capabilities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_id INTEGER NOT NULL UNIQUE,
            operating_range_min REAL,
            operating_range_max REAL,
            operating_unit TEXT,
            accuracy_class TEXT,
            resolution REAL,
            standard_uncertainty REAL,
            supported_methods TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (equipment_id) REFERENCES laboratory_equipment(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS certificate_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            method_id INTEGER,
            template_name TEXT NOT NULL,
            version TEXT NOT NULL,
            file_path TEXT,
            field_definitions TEXT,
            status TEXT NOT NULL DEFAULT 'Draft',
            approved_by TEXT,
            approved_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (method_id) REFERENCES calibration_methods(id),
            UNIQUE (template_name, version)
        )
    """)

    # ------------------------------------------------------------------
    # Measurement, Uncertainty and Certificates (SDS Sections 7, 11, 13)
    # ------------------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS environmental_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_date TEXT NOT NULL UNIQUE,
            ambient_temperature REAL,
            relative_humidity REAL,
            atmospheric_pressure REAL,
            recorded_by TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    ensure_column("environmental_records", "record_time", "TEXT")
    ensure_column("environmental_records", "instrument_used", "TEXT")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS uncertainty_budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            method_id INTEGER NOT NULL,
            component_name TEXT NOT NULL,
            source_description TEXT,
            standard_uncertainty REAL NOT NULL,
            distribution TEXT,
            divisor REAL,
            sensitivity_coefficient REAL DEFAULT 1,
            correlation_group TEXT,
            status TEXT NOT NULL DEFAULT 'Draft',
            approved_by TEXT,
            approved_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (method_id) REFERENCES calibration_methods(id),
            UNIQUE (method_id, component_name)
        )
    """)

    # Controlled uncertainty data.  Type B inputs are maintained here and are
    # never entered ad hoc while a technician is performing a calibration.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS uncertainty_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_id INTEGER NOT NULL,
            version TEXT NOT NULL,
            certificate_number TEXT,
            calibration_laboratory TEXT,
            calibration_date TEXT,
            next_due_date TEXT,
            coverage_factor REAL NOT NULL DEFAULT 2,
            expanded_uncertainty REAL,
            standard_uncertainty REAL,
            resolution REAL,
            drift REAL,
            correction_factor REAL,
            sensitivity REAL NOT NULL DEFAULT 1,
            certificate_path TEXT,
            is_active INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (equipment_id) REFERENCES laboratory_equipment(id),
            UNIQUE (equipment_id, version)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS uncertainty_profile_components (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER NOT NULL,
            component_name TEXT NOT NULL,
            value REAL NOT NULL,
            unit TEXT,
            distribution TEXT,
            divisor REAL NOT NULL DEFAULT 1,
            sensitivity_coefficient REAL NOT NULL DEFAULT 1,
            degrees_of_freedom REAL,
            source TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (profile_id) REFERENCES uncertainty_profiles(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS type_b_library_components (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            component_name TEXT NOT NULL,
            value REAL NOT NULL,
            unit TEXT,
            distribution TEXT,
            divisor REAL NOT NULL DEFAULT 1,
            sensitivity_coefficient REAL NOT NULL DEFAULT 1,
            source TEXT,
            revision TEXT NOT NULL DEFAULT '1.0',
            status TEXT NOT NULL DEFAULT 'Draft',
            approved_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (component_name, revision)
        )
    """)
    ensure_column("type_b_library_components", "applies_to_method", "TEXT NOT NULL DEFAULT 'Both'")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS primary_selection_configurations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            version TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (name, version)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS primary_selection_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            configuration_id INTEGER NOT NULL,
            meter_type TEXT NOT NULL,
            method_name TEXT NOT NULL,
            flow_min REAL NOT NULL,
            flow_max REAL NOT NULL,
            equipment_role TEXT NOT NULL,
            equipment_id INTEGER NOT NULL,
            FOREIGN KEY (configuration_id) REFERENCES primary_selection_configurations(id) ON DELETE CASCADE,
            FOREIGN KEY (equipment_id) REFERENCES laboratory_equipment(id),
            CHECK (flow_min <= flow_max),
            UNIQUE (configuration_id, meter_type, method_name, flow_min, flow_max, equipment_role)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS uncertainty_configuration_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            configuration_id INTEGER,
            original_filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            format TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (configuration_id) REFERENCES primary_selection_configurations(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS measurement_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meter_type TEXT NOT NULL,
            method_name TEXT NOT NULL,
            flow_range REAL NOT NULL,
            type_a_report_path TEXT NOT NULL,
            imported_observations TEXT NOT NULL,
            report_temperature REAL,
            combined_standard_uncertainty REAL NOT NULL,
            expanded_uncertainty REAL NOT NULL,
            coverage_factor REAL NOT NULL DEFAULT 2,
            primary_configuration_id INTEGER,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (primary_configuration_id) REFERENCES primary_selection_configurations(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS calibration_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_number TEXT NOT NULL UNIQUE,
            customer_id INTEGER,
            equipment_id INTEGER,
            method_id INTEGER,
            method_configuration_id INTEGER,
            environmental_record_id INTEGER,
            status TEXT NOT NULL DEFAULT 'Draft',
            flow_range TEXT,
            test_data_path TEXT,
            imported_values TEXT,
            calculated_values TEXT,
            combined_uncertainty REAL,
            expanded_uncertainty REAL,
            coverage_factor REAL DEFAULT 2,
            started_at TEXT,
            completed_at TEXT,
            approved_by TEXT,
            approved_at TEXT,
            notes TEXT,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (equipment_id) REFERENCES laboratory_equipment(id),
            FOREIGN KEY (method_id) REFERENCES calibration_methods(id),
            FOREIGN KEY (method_configuration_id) REFERENCES method_configurations(id),
            FOREIGN KEY (environmental_record_id) REFERENCES environmental_records(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS type_a_test_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            run_number INTEGER NOT NULL,
            reference_value REAL,
            meter_indication REAL,
            flow_value REAL,
            recorded_at TEXT,
            imported_from TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES calibration_jobs(id) ON DELETE CASCADE,
            UNIQUE (job_id, run_number)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            certificate_number TEXT NOT NULL UNIQUE,
            version TEXT NOT NULL DEFAULT '1',
            status TEXT NOT NULL DEFAULT 'Draft',
            file_path TEXT,
            issued_at TEXT,
            next_due_date TEXT,
            issued_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES calibration_jobs(id)
        )
    """)

    # ------------------------------------------------------------------
    # Project Deliverables (SDS Section 9)
    # ------------------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            job_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (job_id) REFERENCES calibration_jobs(id) ON DELETE CASCADE,
            UNIQUE (project_id, job_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deliverables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            deliverable_name TEXT NOT NULL,
            description TEXT,
            due_date TEXT,
            status TEXT NOT NULL DEFAULT 'Open',
            completed_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    """)

    # ------------------------------------------------------------------
    # Reminder and Quality Management (SDS Sections 12, 14)
    # ------------------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reminder_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_name TEXT NOT NULL UNIQUE,
            entity_type TEXT NOT NULL,
            equipment_type TEXT,
            lead_days INTEGER NOT NULL,
            escalation_role TEXT DEFAULT 'Manager',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reminder_rule_id INTEGER,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            detail TEXT,
            due_date TEXT NOT NULL,
            trigger_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Open',
            escalated_at TEXT,
            resolved_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (reminder_rule_id) REFERENCES reminder_rules(id),
            UNIQUE (entity_type, entity_id, trigger_date)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quality_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_type TEXT NOT NULL,
            reference_number TEXT UNIQUE,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'Open',
            owner TEXT,
            due_date TEXT,
            closed_at TEXT,
            related_entity_type TEXT,
            related_entity_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ------------------------------------------------------------------
    # Controlled Knowledge and Audit Trail (SDS Sections 16, 17)
    # ------------------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_base_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            entry_key TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            version TEXT NOT NULL DEFAULT '1.0',
            status TEXT NOT NULL DEFAULT 'Draft',
            approved_by TEXT,
            approved_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (category, entry_key, version)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_trail (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id INTEGER,
            action TEXT NOT NULL,
            actor TEXT,
            before_state TEXT,
            after_state TEXT,
            occurred_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.executescript("""
        CREATE INDEX IF NOT EXISTS idx_projects_customer ON projects(customer_id);
        CREATE INDEX IF NOT EXISTS idx_calibration_jobs_status ON calibration_jobs(status);
        CREATE INDEX IF NOT EXISTS idx_calibration_jobs_customer ON calibration_jobs(customer_id);
        CREATE INDEX IF NOT EXISTS idx_reminders_status_due ON reminders(status, due_date);
        CREATE INDEX IF NOT EXISTS idx_quality_records_type_status ON quality_records(record_type, status);
        CREATE INDEX IF NOT EXISTS idx_knowledge_base_category ON knowledge_base_entries(category, status);
        CREATE INDEX IF NOT EXISTS idx_controlled_documents_type ON controlled_documents(document_type, status);
        CREATE INDEX IF NOT EXISTS idx_uncertainty_profiles_active ON uncertainty_profiles(equipment_id, is_active);
    """)

    # ------------------------------------------------------------------
    # Default Roles
    # ------------------------------------------------------------------

    cursor.executemany("""
        INSERT OR IGNORE INTO roles (
            name,
            description
        )
        VALUES (?, ?)
    """, [
        ("Administrator", "Full system access"),
        ("Manager", "Laboratory Manager"),
        ("Technician", "Laboratory Technician"),
        ("Viewer", "Read Only Access"),
    ])

    conn.commit()
    conn.close()


if __name__ == "__main__":
    initialize_database()
