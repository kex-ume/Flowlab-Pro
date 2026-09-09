from app.database.database import database_backend, get_connection


ISO_CLAUSES = (
    ("4.1", "Impartiality", "General", "Impartiality risks and safeguards"),
    ("4.2", "Confidentiality", "General", "Confidentiality commitments and information-release controls"),
    ("5", "Structural requirements", "Structure", "Legal identity, organization, responsibilities and authority"),
    ("6.1", "Resources — general", "Resources", "Resource planning and availability"),
    ("6.2", "Personnel", "Resources", "Competence, training, supervision and authorization"),
    ("6.3", "Facilities and environmental conditions", "Resources", "Environmental limits, monitoring and excursion control"),
    ("6.4", "Equipment", "Resources", "Equipment suitability, identification, control and records"),
    ("6.5", "Metrological traceability", "Resources", "Documented calibration chain and traceability evidence"),
    ("6.6", "Externally provided products and services", "Resources", "Supplier selection, evaluation and acceptance"),
    ("7.1", "Review of requests, tenders and contracts", "Process", "Capability, method and customer-requirement review"),
    ("7.2", "Selection, verification and validation of methods", "Process", "Controlled method selection, verification, validation and deviations"),
    ("7.3", "Sampling", "Process", "Sampling plans and records where sampling is performed"),
    ("7.4", "Handling of test or calibration items", "Process", "Receipt, identification, condition, storage and return"),
    ("7.5", "Technical records", "Process", "Traceable observations, calculations, amendments and responsible personnel"),
    ("7.6", "Evaluation of measurement uncertainty", "Process", "Approved uncertainty methods, budgets and supporting data"),
    ("7.7", "Ensuring the validity of results", "Process", "Quality-control planning, monitoring, PT or ILC and investigations"),
    ("7.8", "Reporting of results", "Process", "Controlled reports, certificates, amendments and authorization"),
    ("7.9", "Complaints", "Process", "Complaint receipt, independent evaluation, decisions and closure"),
    ("7.10", "Nonconforming work", "Process", "Control, impact evaluation, notification and authorization to resume"),
    ("7.11", "Control of data and information management", "Process", "System validation, access, integrity, backup and change control"),
    ("8.1", "Management system options", "Management system", "Selected management-system option and defined scope"),
    ("8.2", "Management system documentation", "Management system", "Policies, objectives and accessible management-system documentation"),
    ("8.3", "Control of management system documents", "Management system", "Approval, revision, distribution and obsolete-document control"),
    ("8.4", "Control of records", "Management system", "Identification, retention, protection, retrieval and disposition"),
    ("8.5", "Actions to address risks and opportunities", "Management system", "Risk identification, action, proportionality and effectiveness"),
    ("8.6", "Improvement", "Management system", "Improvement opportunities and customer feedback"),
    ("8.7", "Corrective actions", "Management system", "Cause analysis, corrective action and effectiveness review"),
    ("8.8", "Internal audits", "Management system", "Audit programme, execution, findings and follow-up"),
    ("8.9", "Management reviews", "Management system", "Planned review inputs, decisions, actions and records"),
)

ISO_EVIDENCE_REQUIREMENTS = {
    "4.1": ("Impartiality risk register", "Conflict-of-interest declarations"),
    "4.2": ("Confidentiality policy or agreement",),
    "5": ("Organization chart", "Roles and responsibility matrix"),
    "6.2": ("Competence and authorization records",),
    "6.3": ("Environmental monitoring and excursion records",),
    "6.4": ("Equipment records",),
    "6.5": ("Traceability evidence",),
    "6.6": ("Approved supplier evaluation records",),
    "7.1": ("Contract or request review records",),
    "7.2": ("Method verification or validation evidence",),
    "7.3": ("Sampling plan and records",),
    "7.4": ("Item receipt and handling records",),
    "7.5": ("Technical records",),
    "7.6": ("Approved uncertainty evidence",),
    "7.7": ("Validity monitoring or PT/ILC evidence",),
    "7.8": ("Approved report or certificate evidence",),
    "7.9": ("Complaint records",),
    "7.10": ("Nonconforming-work records",),
    "7.11": ("System validation and backup evidence",),
    "8.1": ("Management system option declaration",),
    "8.2": ("Management system policy and objectives",),
    "8.3": ("Master document register",),
    "8.4": ("Record retention schedule",),
    "8.5": ("Risk and opportunity register",),
    "8.6": ("Improvement or customer-feedback records",),
    "8.7": ("Corrective-action records",),
    "8.8": ("Internal audit programme and reports",),
    "8.9": ("Management review minutes and action records",),
}


def _create_iso_checklist_schema(conn, postgres=False):
    identity = "BIGSERIAL" if postgres else "INTEGER"
    primary = "PRIMARY KEY" if postgres else "PRIMARY KEY AUTOINCREMENT"
    user_type = "BIGINT" if postgres else "INTEGER"
    conn.execute(f"""CREATE TABLE IF NOT EXISTS iso_clauses (
        id {identity} {primary}, clause_code TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
        category TEXT NOT NULL, guidance TEXT, sort_order INTEGER NOT NULL, is_active INTEGER NOT NULL DEFAULT 1)""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS iso_clause_assessments (
        id {identity} {primary}, clause_id {user_type} NOT NULL UNIQUE REFERENCES iso_clauses(id),
        applicability TEXT NOT NULL DEFAULT 'Applicable', applicability_reason TEXT,
        compliance_status TEXT NOT NULL DEFAULT 'Not Assessed', owner_user_id {user_type} REFERENCES users(id),
        finding TEXT, planned_action TEXT, target_date DATE, last_review_date DATE, next_review_date DATE,
        status TEXT NOT NULL DEFAULT 'Draft', created_by TEXT NOT NULL, updated_by TEXT,
        submitted_by TEXT, submitted_at TIMESTAMP, assigned_reviewer_id {user_type} REFERENCES users(id),
        review_comment TEXT, approved_by TEXT, approved_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS iso_clause_evidence_requirements (
        id {identity} {primary}, clause_id {user_type} NOT NULL REFERENCES iso_clauses(id),
        evidence_name TEXT NOT NULL, is_required INTEGER NOT NULL DEFAULT 1,
        UNIQUE(clause_id,evidence_name))""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS iso_clause_evidence (
        id {identity} {primary}, clause_id {user_type} NOT NULL REFERENCES iso_clauses(id),
        requirement_id {user_type} REFERENCES iso_clause_evidence_requirements(id),
        title TEXT NOT NULL, document_number TEXT, revision TEXT, effective_date DATE,
        review_date DATE, retention_until DATE, file_name TEXT NOT NULL, file_path TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Draft', uploaded_by TEXT NOT NULL,
        assigned_reviewer_id {user_type} REFERENCES users(id), submitted_at TIMESTAMP,
        review_comment TEXT, approved_by TEXT, approved_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, is_deleted INTEGER NOT NULL DEFAULT 0)""")
    for order, (code, title, category, guidance) in enumerate(ISO_CLAUSES, 1):
        conn.execute("""INSERT INTO iso_clauses(clause_code,title,category,guidance,sort_order)
            VALUES (?,?,?,?,?) ON CONFLICT(clause_code) DO NOTHING""", (code,title,category,guidance,order))
        clause = conn.execute("SELECT id FROM iso_clauses WHERE clause_code=?", (code,)).fetchone()
        for evidence_name in ISO_EVIDENCE_REQUIREMENTS.get(code, ()):
            conn.execute("""INSERT INTO iso_clause_evidence_requirements(clause_id,evidence_name)
                VALUES (?,?) ON CONFLICT(clause_id,evidence_name) DO NOTHING""", (clause[0],evidence_name))


_postgres_schema_verified = False


def initialize_database():
    global _postgres_schema_verified
    if database_backend() == "postgresql":
        if _postgres_schema_verified:
            return
        conn = get_connection()
        try:
            row = conn.execute("SELECT to_regclass('public.users')").fetchone()
            if not row or row[0] is None:
                raise RuntimeError(
                    "The PostgreSQL database is empty. Run scripts/migrate_sqlite_to_postgres.py "
                    "before starting FlowLab Pro."
                )
            conn.execute("""CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at_epoch BIGINT NOT NULL,
                used_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
            conn.execute("""CREATE INDEX IF NOT EXISTS idx_password_reset_token_lookup
                ON password_reset_tokens(token_hash,expires_at_epoch,used_at)""")
            conn.execute("""INSERT INTO system_settings
                (setting_key,setting_value,value_type,updated_by,updated_at)
                VALUES ('admin_recovery_email','ikechukwuumezulike@gmail.com','email',
                    'System configuration',CURRENT_TIMESTAMP)
                ON CONFLICT(setting_key) DO NOTHING""")
            conn.execute("""CREATE TABLE IF NOT EXISTS capa_records (
                id BIGSERIAL PRIMARY KEY,ncr_number TEXT NOT NULL UNIQUE,title TEXT NOT NULL,
                source TEXT NOT NULL,clause_reference TEXT,description TEXT NOT NULL,
                immediate_correction TEXT,root_cause TEXT,corrective_action TEXT,owner TEXT NOT NULL,
                issued_date DATE NOT NULL,target_close_date DATE NOT NULL,status TEXT NOT NULL DEFAULT 'Draft',
                issued_ncr_path TEXT NOT NULL,closeout_report_path TEXT,created_by TEXT NOT NULL,
                assigned_reviewer_id BIGINT REFERENCES users(id),submitted_by TEXT,submitted_at TIMESTAMP,
                review_comment TEXT,approved_by TEXT,approved_at TIMESTAMP,closed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER NOT NULL DEFAULT 0)""")
            _create_iso_checklist_schema(conn, postgres=True)
            conn.commit()
            _postgres_schema_verified = True
        finally:
            conn.close()
        return

    conn = get_connection()
    cursor = conn.cursor()

    _create_iso_checklist_schema(conn)

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
            calibration_interval_months INTEGER,
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

    ensure_column("calibration_history", "uncertainty_value", "REAL")
    ensure_column("calibration_history", "uncertainty_unit", "TEXT")
    ensure_column("calibration_history", "coverage_factor", "REAL")
    ensure_column("calibration_history", "calibration_range", "TEXT")
    ensure_column("calibration_history", "range_unit", "TEXT")
    ensure_column("calibration_history", "result", "TEXT")

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

    ensure_column("maintenance_history", "next_maintenance_date", "TEXT")
    ensure_column("maintenance_history", "currency", "TEXT")
    ensure_column("maintenance_history", "supplier", "TEXT")
    ensure_column("maintenance_history", "work_performed", "TEXT")
    ensure_column("maintenance_history", "findings", "TEXT")
    ensure_column("maintenance_history", "parts_replaced", "TEXT")
    ensure_column("maintenance_history", "metrological_impact", "TEXT")
    ensure_column("maintenance_history", "recalibration_required", "INTEGER NOT NULL DEFAULT 0")

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
    ensure_column("laboratory_equipment", "created_by", "TEXT")
    ensure_column("laboratory_equipment", "updated_by", "TEXT")
    ensure_column("laboratory_equipment", "deactivated_at", "TEXT")
    ensure_column("laboratory_equipment", "deactivated_by", "TEXT")
    ensure_column("laboratory_equipment", "validity_months", "INTEGER")
    ensure_column("laboratory_equipment", "validity_value", "INTEGER")
    ensure_column("laboratory_equipment", "validity_unit", "TEXT")
    ensure_column("laboratory_equipment", "record_status", "TEXT NOT NULL DEFAULT 'Approved'")
    ensure_column("laboratory_equipment", "submitted_by", "TEXT")
    ensure_column("laboratory_equipment", "submitted_at", "TIMESTAMP")
    ensure_column("laboratory_equipment", "reviewed_by", "TEXT")
    ensure_column("laboratory_equipment", "reviewed_at", "TIMESTAMP")
    ensure_column("laboratory_equipment", "approved_by", "TEXT")
    ensure_column("laboratory_equipment", "approved_at", "TIMESTAMP")
    ensure_column("calibration_history", "uploaded_by", "TEXT")
    ensure_column("calibration_history", "notes", "TEXT")
    ensure_column("maintenance_history", "uploaded_by", "TEXT")
    ensure_column("maintenance_history", "notes", "TEXT")
    ensure_column("calibration_history", "is_deleted", "INTEGER NOT NULL DEFAULT 0")
    ensure_column("calibration_history", "deleted_at", "TEXT")
    ensure_column("calibration_history", "deleted_by", "TEXT")
    ensure_column("calibration_history", "certificate_number", "TEXT")
    ensure_column("calibration_history", "uncertainty_input_type", "TEXT")
    ensure_column("calibration_history", "status", "TEXT NOT NULL DEFAULT 'Approved'")
    ensure_column("calibration_history", "submitted_by", "TEXT")
    ensure_column("calibration_history", "reviewed_by", "TEXT")
    ensure_column("calibration_history", "reviewed_at", "TEXT")
    ensure_column("calibration_history", "approved_by", "TEXT")
    ensure_column("calibration_history", "approved_at", "TEXT")
    ensure_column("calibration_history", "superseded_by", "INTEGER")
    ensure_column("calibration_history", "validity_value", "INTEGER")
    ensure_column("calibration_history", "validity_unit", "TEXT")
    ensure_column("calibration_history", "classification", "TEXT")
    ensure_column("calibration_history", "source_name", "TEXT")
    ensure_column("calibration_history", "sensitivity_coefficient", "REAL")
    ensure_column("calibration_history", "degrees_of_freedom", "REAL")
    ensure_column("maintenance_history", "is_deleted", "INTEGER NOT NULL DEFAULT 0")
    ensure_column("maintenance_history", "deleted_at", "TEXT")
    ensure_column("maintenance_history", "deleted_by", "TEXT")
    ensure_column("maintenance_history", "status", "TEXT NOT NULL DEFAULT 'Approved'")
    ensure_column("maintenance_history", "submitted_by", "TEXT")
    ensure_column("maintenance_history", "reviewed_by", "TEXT")
    ensure_column("maintenance_history", "reviewed_at", "TEXT")
    ensure_column("maintenance_history", "approved_by", "TEXT")
    ensure_column("maintenance_history", "approved_at", "TEXT")

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
    ensure_column("users", "must_change_password", "INTEGER NOT NULL DEFAULT 0")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            requested_at TEXT DEFAULT CURRENT_TIMESTAMP,
            resolved_by TEXT,
            resolved_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    cursor.execute("""CREATE INDEX IF NOT EXISTS idx_password_reset_pending
        ON password_reset_requests(user_id,status,requested_at)""")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at_epoch INTEGER NOT NULL,
            used_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""CREATE INDEX IF NOT EXISTS idx_password_reset_token_lookup
        ON password_reset_tokens(token_hash,expires_at_epoch,used_at)""")

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
    ensure_column("customers", "notes", "TEXT")
    ensure_column("projects", "notes", "TEXT")
    ensure_column("projects", "project_manager", "TEXT")
    ensure_column("projects", "created_by", "TEXT")
    ensure_column("projects", "purchase_order", "TEXT")
    ensure_column("projects", "is_deleted", "INTEGER NOT NULL DEFAULT 0")
    ensure_column("projects", "deleted_at", "TEXT")
    ensure_column("projects", "deleted_by", "TEXT")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recycle_bin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            display_name TEXT NOT NULL,
            original_location TEXT,
            deleted_by TEXT NOT NULL,
            deleted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(entity_type, entity_id)
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
    cursor.executemany("""INSERT OR IGNORE INTO calibration_methods
        (meter_type,method_name,revision,description,status,effective_date,approved_by,approved_at,is_active)
        VALUES (?,?, '1.0',?,'Approved',date('now'),'System method register',CURRENT_TIMESTAMP,1)""", (
        ("Flow", "Gravimetric Method", "Controlled gravimetric flow calibration method."),
        ("Flow", "Coriolis Master Meter Method", "Controlled Coriolis master-meter comparison method."),
    ))

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
    ensure_column("controlled_documents", "notes", "TEXT")
    ensure_column("controlled_documents", "uploaded_by", "TEXT")
    ensure_column("controlled_documents", "is_deleted", "INTEGER NOT NULL DEFAULT 0")
    ensure_column("controlled_documents", "deleted_at", "TEXT")
    ensure_column("controlled_documents", "deleted_by", "TEXT")
    ensure_column("controlled_documents", "submitted_by", "TEXT")
    ensure_column("controlled_documents", "reviewed_by", "TEXT")
    ensure_column("controlled_documents", "reviewed_at", "TEXT")
    ensure_column("controlled_documents", "approved_by", "TEXT")
    ensure_column("controlled_documents", "approved_at", "TEXT")

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
    ensure_column("equipment_capabilities", "accuracy_value", "REAL")
    ensure_column("equipment_capabilities", "tolerance", "REAL")

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
    ensure_column("uncertainty_profiles", "source_name", "TEXT")
    ensure_column("uncertainty_profiles", "uncertainty_unit", "TEXT")
    ensure_column("uncertainty_profiles", "evaluation_basis", "TEXT")
    ensure_column("uncertainty_profiles", "distribution", "TEXT")
    ensure_column("uncertainty_profiles", "divisor", "REAL")
    ensure_column("uncertainty_profiles", "degrees_of_freedom", "REAL")
    cursor.execute("""UPDATE uncertainty_profiles SET source_name=COALESCE(source_name,
        (SELECT e.equipment_name || ' calibration uncertainty' FROM laboratory_equipment e
         WHERE e.id=uncertainty_profiles.equipment_id)) WHERE source_name IS NULL""")
    cursor.execute("""UPDATE uncertainty_profiles SET
        uncertainty_unit=COALESCE(uncertainty_unit,(SELECT ch.uncertainty_unit FROM calibration_history ch
            WHERE ch.equipment_id=uncertainty_profiles.equipment_id AND ch.status='Approved'
            AND ch.is_deleted=0 ORDER BY ch.calibration_date DESC,ch.id DESC LIMIT 1)),
        evaluation_basis=COALESCE(evaluation_basis,(SELECT CASE WHEN ch.uncertainty_input_type='Standard Uc'
            THEN 'standard' ELSE 'expanded' END FROM calibration_history ch
            WHERE ch.equipment_id=uncertainty_profiles.equipment_id AND ch.status='Approved'
            AND ch.is_deleted=0 ORDER BY ch.calibration_date DESC,ch.id DESC LIMIT 1)),
        distribution=COALESCE(distribution,'Normal'),
        divisor=COALESCE(divisor,(SELECT CASE WHEN ch.uncertainty_input_type='Standard Uc' THEN 1
            ELSE ch.coverage_factor END FROM calibration_history ch
            WHERE ch.equipment_id=uncertainty_profiles.equipment_id AND ch.status='Approved'
            AND ch.is_deleted=0 ORDER BY ch.calibration_date DESC,ch.id DESC LIMIT 1))""")
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
    ensure_column("calibration_jobs", "mut_description", "TEXT")
    ensure_column("calibration_jobs", "mut_serial_number", "TEXT")
    ensure_column("calibration_jobs", "meter_type", "TEXT")
    ensure_column("calibration_jobs", "engineer_operator", "TEXT")
    ensure_column("calibration_jobs", "required_date", "TEXT")
    ensure_column("calibration_jobs", "flow_min", "REAL")
    ensure_column("calibration_jobs", "flow_max", "REAL")
    ensure_column("calibration_jobs", "flow_unit", "TEXT")
    ensure_column("calibration_jobs", "nominated_flow_point", "REAL")
    ensure_column("calibration_jobs", "flow_point_count", "INTEGER NOT NULL DEFAULT 1")
    ensure_column("calibration_jobs", "attachment_path", "TEXT")
    ensure_column("calibration_jobs", "notes", "TEXT")
    ensure_column("calibration_jobs", "attachment_uploaded_by", "TEXT")
    ensure_column("calibration_jobs", "is_deleted", "INTEGER NOT NULL DEFAULT 0")
    ensure_column("calibration_jobs", "deleted_at", "TEXT")
    ensure_column("calibration_jobs", "deleted_by", "TEXT")
    ensure_column("calibration_jobs", "job_title", "TEXT")
    ensure_column("calibration_jobs", "job_type", "TEXT")
    ensure_column("calibration_jobs", "planned_start_date", "TEXT")
    ensure_column("calibration_jobs", "mut_asset_id", "TEXT")
    ensure_column("calibration_jobs", "manufacturer", "TEXT")
    ensure_column("calibration_jobs", "model_number", "TEXT")
    ensure_column("calibration_jobs", "meter_size", "TEXT")
    ensure_column("calibration_jobs", "fluid_medium", "TEXT")
    ensure_column("calibration_jobs", "calibration_quantity", "TEXT")
    ensure_column("calibration_jobs", "completion_history", "TEXT")
    ensure_column("calibration_jobs", "assigned_user_id", "INTEGER")
    ensure_column("calibration_jobs", "assigned_by", "TEXT")
    ensure_column("calibration_jobs", "assigned_at", "TEXT")
    ensure_column("calibration_jobs", "assignment_history", "TEXT")
    ensure_column("calibration_jobs", "purchase_order_override", "TEXT")

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

    # ------------------------------------------------------------------
    # Reproducible Uncertainty / CMC Calculations and Workflow
    # ------------------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS budget2_input_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            distribution TEXT NOT NULL,
            divisor REAL NOT NULL,
            requires_coverage_factor INTEGER NOT NULL DEFAULT 0,
            version TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Draft',
            approved_by TEXT,
            approved_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(name, version),
            CHECK(divisor > 0)
        )
    """)
    cursor.executemany("""INSERT OR IGNORE INTO budget2_input_types
        (name, distribution, divisor, requires_coverage_factor, version,
         status, approved_by, approved_at)
        VALUES (?, ?, ?, ?, '1.0', 'Approved', 'Laboratory Directive', CURRENT_TIMESTAMP)""", [
        ("Standard Uc", "Normal", 1.0, 0),
        ("Expanded / Certificate Uncertainty", "Normal", 1.0, 1),
        ("Accuracy", "Rectangular", 3 ** 0.5, 0),
        ("Resolution", "Rectangular", 12 ** 0.5, 0),
        ("Tolerance", "Rectangular", 12 ** 0.5, 0),
        ("Limit", "Rectangular", 12 ** 0.5, 0),
        ("Triangular Limit", "Triangular", 6 ** 0.5, 0),
        ("U-shaped Limit", "U-shaped", 2 ** 0.5, 0),
    ])

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS flow_matrix_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            version TEXT NOT NULL,
            source_files TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Draft',
            approved_by TEXT,
            approved_at TEXT,
            is_active INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(name, version)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS flow_matrix_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id INTEGER NOT NULL,
            flow_min_lpm REAL NOT NULL,
            flow_max_lpm REAL NOT NULL,
            pump TEXT NOT NULL,
            tank TEXT NOT NULL,
            diverter TEXT NOT NULL,
            weighing_system TEXT NOT NULL,
            reference_meter TEXT NOT NULL,
            temperature_instrument TEXT NOT NULL,
            pressure_instrument TEXT NOT NULL,
            procedure TEXT NOT NULL,
            FOREIGN KEY(version_id) REFERENCES flow_matrix_versions(id) ON DELETE CASCADE,
            CHECK(flow_min_lpm <= flow_max_lpm),
            UNIQUE(version_id, flow_min_lpm, flow_max_lpm)
        )
    """)
    matrix_version = cursor.execute("""SELECT id FROM flow_matrix_versions
        WHERE name='FlowLab Range Matrix' AND version='1.0'""").fetchone()
    if matrix_version is None:
        matrix_version_id = cursor.execute("""INSERT INTO flow_matrix_versions
            (name, version, source_files, status, approved_by, approved_at, is_active)
            VALUES ('FlowLab Range Matrix','1.0',?, 'Approved',
                    'Laboratory Directive',CURRENT_TIMESTAMP,1)""",
            ('matrix.xlsx; Flow_Matrix_Selector_Range.xlsx',)).lastrowid
        matrix_rows = [
            (0, 30, "P1", "T1", "DIV-1", "WS-1", "MM-1", "TT-1", "PT-1", "Pump 1 - Low Range Calibration"),
            (31, 100, "P1", "T1", "DIV-1", "WS-2", "MM-2", "TT-1", "PT-1", "Pump 1 - High Range Calibration"),
            (101, 400, "P2", "T2", "DIV-2", "WS-2", "MM-3", "TT-2", "PT-2", "Pump 2 - Low Range Calibration"),
            (401, 1500, "P2", "T2", "DIV-2", "WS-3", "MM-3", "TT-2", "PT-2", "Pump 2 - High Range Calibration"),
            (1501, 2000, "P3/P4", "T3", "DIV-3", "WS-3", "MM-4", "TT-3", "PT-3", "Pumps 3 & 4 - Low Range Calibration"),
            (2001, 8500, "P3/P4", "T3", "DIV-3", "WS-4", "MM-4", "TT-3", "PT-3", "Pumps 3 & 4 - High Range Calibration"),
        ]
        cursor.executemany("""INSERT INTO flow_matrix_rows
            (version_id,flow_min_lpm,flow_max_lpm,pump,tank,diverter,
             weighing_system,reference_meter,temperature_instrument,
             pressure_instrument,procedure) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            [(matrix_version_id, *row) for row in matrix_rows])
    cursor.execute("""UPDATE flow_matrix_versions SET source_files=?
        WHERE name='FlowLab Range Matrix' AND version='1.0'""", (
        "data/documents/configuration/matrix_source_v1.xlsx; "
        "data/documents/configuration/flow_matrix_selector_range_v1.xlsx",
    ))

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS uncertainty_calculations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            revision INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'Draft',
            final_job_rule TEXT,
            combined_standard_uncertainty REAL,
            coverage_factor REAL,
            expanded_uncertainty REAL,
            final_job_uncertainty REAL,
            calculation_version TEXT NOT NULL,
            snapshot_json TEXT NOT NULL,
            calculated_by TEXT,
            calculated_at TEXT,
            saved_at TEXT DEFAULT CURRENT_TIMESTAMP,
            submitted_by TEXT,
            submitted_at TEXT,
            approved_by TEXT,
            approved_at TEXT,
            superseded_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(job_id) REFERENCES calibration_jobs(id),
            UNIQUE(job_id, revision)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS uncertainty_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            calculation_id INTEGER NOT NULL,
            flow_point REAL,
            source_name TEXT NOT NULL,
            source_type TEXT NOT NULL CHECK(source_type IN ('A','B')),
            source_origin TEXT NOT NULL,
            equipment_id INTEGER,
            input_value REAL NOT NULL,
            unit TEXT,
            uncertainty_input_type TEXT NOT NULL,
            distribution TEXT NOT NULL,
            divisor REAL NOT NULL,
            standard_uncertainty REAL NOT NULL,
            sensitivity_coefficient REAL NOT NULL,
            contribution REAL NOT NULL,
            contribution_percent REAL NOT NULL,
            degrees_of_freedom REAL,
            source_status TEXT NOT NULL,
            evidence_path TEXT,
            observations_json TEXT,
            source_version TEXT,
            notes TEXT,
            added_by TEXT,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(calculation_id) REFERENCES uncertainty_calculations(id) ON DELETE CASCADE,
            FOREIGN KEY(equipment_id) REFERENCES laboratory_equipment(id),
            CHECK(divisor > 0)
        )
    """)

    ensure_column("uncertainty_calculations", "calculation_uid", "TEXT")
    ensure_column("uncertainty_calculations", "calculation_type", "TEXT")
    ensure_column("uncertainty_calculations", "method_name", "TEXT")
    ensure_column("uncertainty_calculations", "quantity", "TEXT")
    ensure_column("uncertainty_calculations", "fluid", "TEXT")
    ensure_column("uncertainty_calculations", "analyst", "TEXT")
    ensure_column("uncertainty_calculations", "reviewed_by", "TEXT")
    ensure_column("uncertainty_calculations", "reviewed_at", "TEXT")
    ensure_column("uncertainty_calculations", "parent_calculation_id", "INTEGER")
    ensure_column("uncertainty_calculations", "updated_at", "TEXT")
    ensure_column("uncertainty_calculations", "revision_reason", "TEXT")
    ensure_column("uncertainty_calculations", "review_comment", "TEXT")
    ensure_column("uncertainty_calculations", "hod_reviewer", "TEXT")
    ensure_column("uncertainty_calculations", "created_by", "TEXT")
    ensure_column("uncertainty_calculations", "last_edited_by", "TEXT")
    ensure_column("uncertainty_calculations", "assigned_reviewer", "TEXT")
    ensure_column("uncertainty_calculations", "assigned_approver", "TEXT")
    ensure_column("uncertainty_sources", "calibration_record_id", "INTEGER")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS uncertainty_flow_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            calculation_id INTEGER NOT NULL,
            point_order INTEGER NOT NULL,
            label TEXT,
            nominal_flow REAL NOT NULL,
            flow_unit TEXT NOT NULL,
            reference_temperature REAL,
            reference_pressure REAL,
            coverage_mode TEXT NOT NULL DEFAULT 'auto',
            coverage_probability REAL NOT NULL DEFAULT 95,
            manual_coverage_factor REAL,
            cmc_expression TEXT,
            cmc_coefficient_a REAL,
            cmc_coefficient_b REAL,
            FOREIGN KEY(calculation_id) REFERENCES uncertainty_calculations(id) ON DELETE CASCADE,
            UNIQUE(calculation_id, point_order)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS uncertainty_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flow_point_id INTEGER NOT NULL,
            run_number INTEGER NOT NULL,
            collected_mass REAL,
            collection_time REAL,
            density REAL,
            density_unit TEXT,
            mut_indication REAL,
            master_equipment_id INTEGER,
            master_indication REAL,
            master_correction REAL,
            correction_basis TEXT,
            reference_flow REAL NOT NULL,
            error_percent REAL NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(flow_point_id) REFERENCES uncertainty_flow_points(id) ON DELETE CASCADE,
            FOREIGN KEY(master_equipment_id) REFERENCES laboratory_equipment(id),
            UNIQUE(flow_point_id, run_number)
        )
    """)
    ensure_column("uncertainty_observations", "density_unit", "TEXT")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS uncertainty_correlations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flow_point_id INTEGER NOT NULL,
            source_i TEXT NOT NULL,
            source_j TEXT NOT NULL,
            coefficient REAL NOT NULL CHECK(coefficient BETWEEN -1 AND 1),
            justification TEXT NOT NULL,
            FOREIGN KEY(flow_point_id) REFERENCES uncertainty_flow_points(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS uncertainty_point_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flow_point_id INTEGER NOT NULL UNIQUE,
            observation_count INTEGER NOT NULL,
            mean_error REAL,
            sample_standard_deviation REAL,
            type_a_standard_uncertainty REAL,
            combined_standard_uncertainty REAL NOT NULL,
            effective_degrees_of_freedom REAL,
            coverage_factor REAL NOT NULL,
            expanded_uncertainty REAL NOT NULL,
            applicable_cmc REAL,
            reportable_uncertainty REAL,
            comparison_status TEXT,
            result_json TEXT NOT NULL,
            calculated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(flow_point_id) REFERENCES uncertainty_flow_points(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflow_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            task_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            submitted_by TEXT NOT NULL,
            submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            assigned_to TEXT NOT NULL,
            assigned_at TEXT DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TEXT,
            decision TEXT,
            comment TEXT,
            priority TEXT DEFAULT 'Normal',
            due_date TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cmc_revisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            method_name TEXT NOT NULL CHECK(method_name IN ('Gravimetric Method','Coriolis Comparison Method')),
            revision INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Draft',
            reason TEXT NOT NULL,
            previous_cmc REAL,
            proposed_cmc REAL,
            coverage_factor REAL,
            calculation_version TEXT NOT NULL,
            snapshot_json TEXT NOT NULL,
            created_by TEXT NOT NULL,
            calculated_at TEXT,
            submitted_at TEXT,
            approved_by TEXT,
            approved_at TEXT,
            effective_at TEXT,
            superseded_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(method_name, revision)
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
    cursor.execute("""CREATE TABLE IF NOT EXISTS capa_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,ncr_number TEXT NOT NULL UNIQUE,title TEXT NOT NULL,
        source TEXT NOT NULL,clause_reference TEXT,description TEXT NOT NULL,
        immediate_correction TEXT,root_cause TEXT,corrective_action TEXT,owner TEXT NOT NULL,
        issued_date TEXT NOT NULL,target_close_date TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'Draft',
        issued_ncr_path TEXT NOT NULL,closeout_report_path TEXT,created_by TEXT NOT NULL,
        assigned_reviewer_id INTEGER,submitted_by TEXT,submitted_at TEXT,review_comment TEXT,
        approved_by TEXT,approved_at TEXT,closed_at TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,is_deleted INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(assigned_reviewer_id) REFERENCES users(id))""")

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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL,
            value_type TEXT NOT NULL DEFAULT 'text',
            updated_by TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""INSERT OR IGNORE INTO system_settings
        (setting_key,setting_value,value_type,updated_by)
        VALUES ('equipment_due_soon_days','30','integer','System configuration')""")
    cursor.execute("""INSERT OR IGNORE INTO system_settings
        (setting_key,setting_value,value_type,updated_by)
        VALUES ('admin_recovery_email','ikechukwuumezulike@gmail.com','email','System configuration')""")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS record_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            note TEXT NOT NULL,
            author TEXT NOT NULL,
            visibility TEXT NOT NULL DEFAULT 'Internal',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            edited_at TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS equipment_status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_id INTEGER NOT NULL,
            previous_status TEXT,
            new_status TEXT NOT NULL,
            changed_by TEXT,
            changed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(equipment_id) REFERENCES laboratory_equipment(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS equipment_work_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_id INTEGER NOT NULL,
            work_order_number TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Open',
            assigned_to TEXT,
            due_date TEXT,
            notes TEXT,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(equipment_id) REFERENCES laboratory_equipment(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS approval_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            actor TEXT NOT NULL,
            notes TEXT,
            occurred_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS job_reopen_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            requested_by TEXT NOT NULL,
            requested_at TEXT DEFAULT CURRENT_TIMESTAMP,
            authorized_by TEXT,
            authorized_at TEXT,
            decision_comment TEXT,
            FOREIGN KEY(job_id) REFERENCES calibration_jobs(id)
        )
    """)
    ensure_column("uncertainty_budgets", "notes", "TEXT")
    ensure_column("uncertainty_calculations", "notes", "TEXT")
    ensure_column("cmc_revisions", "notes", "TEXT")
    ensure_column("cmc_revisions", "reviewed_by", "TEXT")
    ensure_column("cmc_revisions", "reviewed_at", "TEXT")
    ensure_column("cmc_revisions", "review_comment", "TEXT")
    ensure_column("cmc_revisions", "hod_reviewer", "TEXT")
    ensure_column("cmc_revisions", "assigned_reviewer", "TEXT")
    ensure_column("cmc_revisions", "assigned_approver", "TEXT")
    ensure_column("environmental_records", "notes", "TEXT")
    ensure_column("quality_records", "notes", "TEXT")
    ensure_column("quality_records", "is_deleted", "INTEGER NOT NULL DEFAULT 0")
    ensure_column("quality_records", "deleted_at", "TEXT")
    ensure_column("quality_records", "deleted_by", "TEXT")
    ensure_column("workflow_tasks", "notes", "TEXT")
    ensure_column("workflow_tasks", "submitted_user_id", "INTEGER")
    ensure_column("workflow_tasks", "assigned_user_id", "INTEGER")
    ensure_column("calibration_history", "assigned_reviewer_id", "INTEGER")
    ensure_column("calibration_history", "review_comment", "TEXT")
    ensure_column("maintenance_history", "assigned_reviewer_id", "INTEGER")
    ensure_column("maintenance_history", "review_comment", "TEXT")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            notification_type TEXT NOT NULL DEFAULT 'Workflow',
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            link TEXT,
            entity_type TEXT,
            entity_id INTEGER,
            created_by TEXT,
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            read_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            draft_key TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id),
            UNIQUE(user_id, draft_key)
        )
    """)

    cursor.executescript("""
        UPDATE laboratory_equipment SET validity_months=calibration_interval_months
        WHERE validity_months IS NULL AND calibration_interval_months IS NOT NULL;
        UPDATE laboratory_equipment SET validity_value=COALESCE(validity_months,calibration_interval_months),validity_unit='Months'
        WHERE validity_value IS NULL AND COALESCE(validity_months,calibration_interval_months) IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_projects_customer ON projects(customer_id);
        CREATE INDEX IF NOT EXISTS idx_calibration_jobs_status ON calibration_jobs(status);
        CREATE INDEX IF NOT EXISTS idx_calibration_jobs_customer ON calibration_jobs(customer_id);
        CREATE INDEX IF NOT EXISTS idx_reminders_status_due ON reminders(status, due_date);
        CREATE INDEX IF NOT EXISTS idx_quality_records_type_status ON quality_records(record_type, status);
        CREATE INDEX IF NOT EXISTS idx_knowledge_base_category ON knowledge_base_entries(category, status);
        CREATE INDEX IF NOT EXISTS idx_controlled_documents_type ON controlled_documents(document_type, status);
        CREATE INDEX IF NOT EXISTS idx_uncertainty_profiles_active ON uncertainty_profiles(equipment_id, is_active);
        CREATE INDEX IF NOT EXISTS idx_record_notes_entity ON record_notes(entity_type, entity_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_equipment_status_history ON equipment_status_history(equipment_id, changed_at);
        CREATE INDEX IF NOT EXISTS idx_approval_history_entity ON approval_history(entity_type, entity_id, occurred_at);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_uncertainty_calculation_uid ON uncertainty_calculations(calculation_uid) WHERE calculation_uid IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_job_reopen_requests ON job_reopen_requests(job_id,status);
        CREATE INDEX IF NOT EXISTS idx_calibration_review_status ON calibration_history(status,equipment_id);
        CREATE INDEX IF NOT EXISTS idx_maintenance_review_status ON maintenance_history(status,equipment_id);
        CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications(user_id,is_read,created_at);
        CREATE INDEX IF NOT EXISTS idx_user_drafts_owner ON user_drafts(user_id,updated_at);
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
        ("Chief Meteorologist", "Chief laboratory authority"),
        ("Supervisor", "Laboratory supervisor and approval authority"),
        ("Engineer", "Laboratory engineer"),
        ("Technician", "Laboratory Technician"),
        ("Operator", "Laboratory operator"),
        ("Guest", "Read Only Access"),
        ("Administrator", "System administration and chief authority"),
        ("Manager", "Legacy role mapped to Supervisor"),
        ("Viewer", "Legacy role mapped to Guest"),
        ("HOD", "Legacy role mapped to Chief Meteorologist"),
    ])

    conn.commit()
    conn.close()


if __name__ == "__main__":
    initialize_database()
