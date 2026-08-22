import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

import app.database.database as database
from app.database.init_db import initialize_database
from app.modules.auth.service import AuthService


demo_root = Path(os.environ["FLOWLAB_DEMO_ROOT"])
demo_root.mkdir(parents=True, exist_ok=True)
database.DATABASE_PATH = demo_root / "flowlab-demo.db"
initialize_database()

connection = database.get_connection()
try:
    users = (
        (os.environ["FLOWLAB_CHIEF_USER"], os.environ["FLOWLAB_CHIEF_PASSWORD"], "Demo Chief Meteorologist", "Chief Meteorologist"),
        (os.environ["FLOWLAB_TECH_USER"], os.environ["FLOWLAB_TECH_PASSWORD"], "Demo Technician", "Technician"),
    )
    for username, password, full_name, role_name in users:
        role_id = connection.execute("SELECT id FROM roles WHERE name=?", (role_name,)).fetchone()[0]
        connection.execute(
            """INSERT INTO users (username,password_hash,full_name,role_id,is_active)
               VALUES (?,?,?,?,1)
               ON CONFLICT(username) DO UPDATE SET password_hash=excluded.password_hash,
               full_name=excluded.full_name,role_id=excluded.role_id,is_active=1""",
            (username, AuthService.hash_password(password), full_name, role_id),
        )
    connection.commit()
finally:
    connection.close()

from web_app import app

app.config["SECRET_KEY"] = os.environ["FLOWLAB_DEMO_SECRET"]
app.run(host="127.0.0.1", port=int(os.environ.get("FLOWLAB_DEMO_PORT", "5050")), debug=False, use_reloader=False)
