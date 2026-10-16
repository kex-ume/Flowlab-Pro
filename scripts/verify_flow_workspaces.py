"""Read-only authenticated rendering checks against the configured source database."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import integrated_app
from web_app import app
from app.database.database import get_connection

connection=get_connection()
try:
    identity=connection.execute("""SELECT u.id,u.full_name,r.name FROM users u JOIN roles r ON r.id=u.role_id
        WHERE u.is_active=1 AND r.name IN ('Chief Metrologist','Chief Meteorologist','Administrator')
        ORDER BY u.id LIMIT 1""").fetchone()
finally: connection.close()
if not identity: raise RuntimeError('No existing Chief/Admin identity is available for read-only rendering checks.')
client=app.test_client()
with client.session_transaction() as state:
    state.update(user_id=identity[0],full_name=identity[1],role_name=identity[2])
for path in ('/environment','/environment?export=csv','/personnel/register','/analytics/calibration',
             '/analytics/uncertainty','/analytics/cmc','/analytics/equipment','/analytics/capa','/analytics/audit-pt'):
    response=client.get(path)
    if response.status_code!=200:
        raise RuntimeError(f'Rendering check failed: {path}: {response.status_code}')
    print('OK',path)
print('Read-only source checks passed; no accounts, readings or job records were added.')
