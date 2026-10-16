"""FlowLab environmental records; existing daily records are retained unchanged."""
from datetime import date
import math


SLOTS = ('08:00', '12:00', '17:00')


def ensure_schema(connection, postgres=False):
    identity = 'BIGSERIAL PRIMARY KEY' if postgres else 'INTEGER PRIMARY KEY AUTOINCREMENT'
    connection.execute(f'''CREATE TABLE IF NOT EXISTS flow_environment_readings (
        id {identity}, record_date TEXT NOT NULL, record_time TEXT NOT NULL,
        location TEXT NOT NULL, ambient_temperature REAL NOT NULL,
        relative_humidity REAL NOT NULL, atmospheric_pressure REAL,
        instrument_used TEXT NOT NULL, recorded_by_user_id INTEGER REFERENCES users(id),
        recorded_by TEXT NOT NULL, notes TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        is_deleted INTEGER NOT NULL DEFAULT 0)''')
    connection.execute('''CREATE UNIQUE INDEX IF NOT EXISTS flow_environment_active_slot
        ON flow_environment_readings(record_date,record_time,location) WHERE is_deleted=0''')
    connection.execute('''CREATE INDEX IF NOT EXISTS flow_environment_dates
        ON flow_environment_readings(record_date,location)''')
    if postgres:
        connection.execute('ALTER TABLE environmental_records ADD COLUMN IF NOT EXISTS is_deleted INTEGER NOT NULL DEFAULT 0')
    else:
        if 'is_deleted' not in {row[1] for row in connection.execute('PRAGMA table_info(environmental_records)')}:
            connection.execute('ALTER TABLE environmental_records ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0')


def filters(values):
    start, end = values.get('from_date', ''), values.get('to_date', '')
    for value in (start, end):
        if value:
            date.fromisoformat(value)
    if start and end and start > end:
        raise ValueError('Start date must not be after end date.')
    return {'from_date': start, 'to_date': end, 'location': values.get('location', '').strip()[:150]}


def records(connection, selected):
    sql = '''SELECT id,record_date,record_time,location,ambient_temperature,relative_humidity,
        atmospheric_pressure,instrument_used,recorded_by,notes,created_at,'flow_environment' AS kind
        FROM flow_environment_readings WHERE is_deleted=0 UNION ALL
        SELECT id,CAST(record_date AS TEXT),COALESCE(record_time,''),'Flow Laboratory',ambient_temperature,
        relative_humidity,atmospheric_pressure,instrument_used,recorded_by,notes,CAST(created_at AS TEXT),
        'flow_environment_legacy' FROM environmental_records WHERE is_deleted=0'''
    params, clauses = [], []
    for name, expression in (('from_date', 'record_date>=?'), ('to_date', 'record_date<=?'), ('location', 'location=?')):
        if selected.get(name):
            clauses.append(expression); params.append(selected[name])
    sql = 'SELECT * FROM (' + sql + ') AS readings' + (' WHERE ' + ' AND '.join(clauses) if clauses else '')
    columns = ('id','date','time','location','temperature','humidity','pressure','instrument','recorder','notes','created','kind')
    return [dict(zip(columns, row)) for row in connection.execute(sql + ' ORDER BY record_date DESC,record_time DESC,id DESC', params)]


def save(connection, values, user_id, actor):
    day = date.fromisoformat(values.get('record_date', ''))
    if day > date.today():
        raise ValueError('Environmental readings cannot be recorded in the future.')
    slot = values.get('record_time')
    location = values.get('location', '').strip()[:150]
    instrument = values.get('instrument_used', '').strip()[:200]
    if slot not in SLOTS or not location or not instrument:
        raise ValueError('Select a time slot and enter the location and monitoring instrument.')
    def number(key, optional=False):
        raw = values.get(key, '')
        if optional and not raw:
            return None
        try:
            value = float(raw)
        except (TypeError, ValueError):
            raise ValueError('Enter valid numeric temperature, humidity and pressure values.')
        if not math.isfinite(value):
            raise ValueError('Environmental values must be finite.')
        return value
    temperature, humidity, pressure = number('temperature'), number('humidity'), number('pressure', True)
    if temperature <= -273.15 or not 0 <= humidity <= 100 or (pressure is not None and pressure <= 0):
        raise ValueError('Check temperature, humidity (0–100%) and positive pressure (kPa).')
    if connection.execute('''SELECT id FROM flow_environment_readings WHERE record_date=? AND record_time=?
        AND location=? AND is_deleted=0''', (day.isoformat(), slot, location)).fetchone():
        raise ValueError('This location and time slot already has a reading. The existing record was not overwritten.')
    return connection.execute('''INSERT INTO flow_environment_readings
        (record_date,record_time,location,ambient_temperature,relative_humidity,atmospheric_pressure,
        instrument_used,recorded_by_user_id,recorded_by,notes) VALUES (?,?,?,?,?,?,?,?,?,?)''',
        (day.isoformat(), slot, location, temperature, humidity, pressure, instrument, user_id, actor,
         values.get('notes', '').strip()[:4000])).lastrowid
