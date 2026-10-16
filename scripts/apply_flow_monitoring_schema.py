"""Apply additive FlowLab monitoring schema and verify existing records unchanged."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import integrated_app
from app.database.database import get_connection
from app.database.init_db import initialize_database


def snapshot():
    connection=get_connection()
    try:
        values={name:connection.execute(f'SELECT * FROM {name} ORDER BY id').fetchall()
                for name in ('calibration_jobs','uncertainty_calculations','users','laboratory_equipment')}
        values['environmental_records']=connection.execute('''SELECT id,record_date,record_time,
            ambient_temperature,relative_humidity,atmospheric_pressure,recorded_by,instrument_used
            FROM environmental_records ORDER BY id''').fetchall()
        return values
    finally: connection.close()


before=snapshot()
initialize_database()
after=snapshot()
if before!=after:
    raise RuntimeError('FlowLab preservation check failed; inspect the backup before continuing.')
print('FlowLab existing records preserved:',{name:len(rows) for name,rows in before.items()})
