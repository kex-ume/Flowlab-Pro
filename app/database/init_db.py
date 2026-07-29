from app.database.database import get_connection


def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()

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