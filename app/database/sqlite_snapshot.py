"""Verified read-only PostgreSQL snapshot into an initialized SQLite schema."""
from datetime import date, datetime, time, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def sqlite_value(value):
    if isinstance(value, uuid.UUID):
        return value.hex
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    if isinstance(value, datetime):
        if value.tzinfo:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value.isoformat(' ')
    if isinstance(value, (date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, memoryview):
        return bytes(value)
    return value


def row_digest(row, types):
    normalized = []
    for value, declared in zip(row, types):
        if isinstance(value, bytes):
            value = ['binary', value.hex()]
        elif value is not None and any(kind in declared.upper() for kind in ('INT', 'REAL', 'NUM', 'DEC', 'FLOAT', 'DOUBLE', 'BOOL')):
            value = format(Decimal(str(value)).normalize(), 'f')
        normalized.append(value)
    return hashlib.sha256(json.dumps(normalized, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()


def copy_postgres(source_url, sqlite_path):
    """Copy all public base tables; verify every row, count and foreign key.

    Target must be a freshly initialized staging database, never an active DB.
    The source transaction is REPEATABLE READ and READ ONLY.
    """
    import psycopg
    target = sqlite3.connect(str(sqlite_path))
    source = psycopg.connect(source_url)
    source.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
    source.read_only = True
    report = {}
    try:
        tables = [row[0] for row in source.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name")]
        available = {row[0] for row in target.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        missing = set(tables) - available
        if missing:
            raise RuntimeError('SQLite schema is missing source tables: ' + ', '.join(sorted(missing)))
        target.execute('PRAGMA foreign_keys=OFF')
        target.execute('BEGIN IMMEDIATE')
        for table in available:
            target.execute('DELETE FROM ' + quote(table))
        for table in tables:
            info = {row[1]: row[2] for row in target.execute('PRAGMA table_info(' + quote(table) + ')')}
            cursor = source.execute('SELECT * FROM public.' + quote(table))
            columns = [column.name for column in cursor.description]
            if set(columns) - set(info):
                raise RuntimeError('SQLite columns do not match PostgreSQL for ' + table)
            types = [info[column] for column in columns]
            column_sql = ','.join(quote(column) for column in columns)
            statement = 'INSERT INTO ' + quote(table) + ' (' + column_sql + ') VALUES (' + ','.join('?' for column in columns) + ')'
            expected = []
            while batch := cursor.fetchmany(500):
                converted = [tuple(sqlite_value(value) for value in row) for row in batch]
                expected.extend(row_digest(row, types) for row in converted)
                target.executemany(statement, converted)
            actual = [row_digest(row, types) for row in target.execute('SELECT ' + column_sql + ' FROM ' + quote(table))]
            if sorted(actual) != sorted(expected):
                raise RuntimeError('Row-content verification failed for ' + table)
            report[table] = {'rows': len(expected), 'verified': True}
        violations = target.execute('PRAGMA foreign_key_check').fetchall()
        if violations:
            raise RuntimeError('Foreign-key verification failed for ' + ', '.join(sorted({row[0] for row in violations})))
        if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('SQLite integrity check failed.')
        target.commit()
        return {'status': 'verified', 'source': 'PostgreSQL read-only snapshot', 'tables': report, 'total_rows': sum(item['rows'] for item in report.values())}
    except Exception:
        target.rollback()
        raise
    finally:
        source.rollback()
        source.close()
        target.close()
