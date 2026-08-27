"""Database connections for local SQLite and production PostgreSQL deployments."""

import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path


DATABASE_PATH = Path("data/flowlab.db")


def database_url() -> str:
    return os.environ.get("FLOWLAB_DATABASE_URL", os.environ.get("DATABASE_URL", "")).strip()


def database_backend() -> str:
    return "postgresql" if database_url().lower().startswith(("postgresql://", "postgres://")) else "sqlite"


def _replace_qmarks(sql: str) -> str:
    output, quote, index = [], None, 0
    while index < len(sql):
        character = sql[index]
        if quote:
            output.append(character)
            if character == quote:
                if index + 1 < len(sql) and sql[index + 1] == quote:
                    output.append(sql[index + 1]); index += 1
                else:
                    quote = None
        elif character in ("'", '"'):
            quote = character; output.append(character)
        elif character == "?":
            output.append("%s")
        else:
            output.append(character)
        index += 1
    return "".join(output)


def translate_sql(sql: str) -> str:
    """Translate the limited SQLite dialect used by FlowLab Pro."""
    translated = sql
    translated = re.sub(r"date\(\s*'now'\s*,\s*'localtime'\s*,\s*\?\s*\)",
                        "TO_CHAR(CURRENT_DATE + (?)::interval, 'YYYY-MM-DD')", translated, flags=re.I)
    translated = re.sub(r"date\(\s*'now'\s*,\s*\?\s*\)",
                        "TO_CHAR(CURRENT_DATE + (?)::interval, 'YYYY-MM-DD')", translated, flags=re.I)

    def fixed_modifier(match):
        return f"TO_CHAR(CURRENT_DATE + INTERVAL '{match.group(1)}', 'YYYY-MM-DD')"

    translated = re.sub(r"date\(\s*'now'\s*,\s*'([^']+)'\s*\)", fixed_modifier, translated, flags=re.I)
    translated = re.sub(r"date\(\s*'now'\s*(?:,\s*'localtime'\s*)?\)",
                        "TO_CHAR(CURRENT_DATE, 'YYYY-MM-DD')", translated, flags=re.I)
    translated = re.sub(r"([A-Za-z_][A-Za-z0-9_.]*)\s*=\s*(\?)\s+COLLATE\s+NOCASE",
                        r"LOWER(\1) = LOWER(\2)", translated, flags=re.I)
    translated = re.sub(r"([A-Za-z_][A-Za-z0-9_.]*)\s+COLLATE\s+NOCASE",
                        r"LOWER(\1)", translated, flags=re.I)
    translated = re.sub(r"\bSELECT\s+last_insert_rowid\s*\(\s*\)", "SELECT LASTVAL()", translated, flags=re.I)
    ignore_insert = bool(re.search(r"\bINSERT\s+OR\s+IGNORE\b", translated, re.I))
    translated = re.sub(r"\bINSERT\s+OR\s+IGNORE\b", "INSERT", translated, flags=re.I)
    if ignore_insert and not re.search(r"\bON\s+CONFLICT\b", translated, re.I):
        stripped = translated.rstrip()
        semicolon = ";" if stripped.endswith(";") else ""
        translated = stripped.removesuffix(";") + " ON CONFLICT DO NOTHING" + semicolon
    return _replace_qmarks(translated)


class PostgreSQLCursor:
    def __init__(self, cursor):
        self._cursor, self.lastrowid = cursor, None

    def execute(self, sql, parameters=()):
        self._cursor.execute(translate_sql(sql), parameters or ())
        self.lastrowid = None
        if re.match(r"^\s*INSERT\b", sql, re.I):
            savepoint = self._cursor.connection.cursor()
            try:
                savepoint.execute("SAVEPOINT flowlab_lastrowid")
                with self._cursor.connection.cursor() as identity_cursor:
                    identity_cursor.execute("SELECT LASTVAL()")
                    self.lastrowid = identity_cursor.fetchone()[0]
            except Exception:
                savepoint.execute("ROLLBACK TO SAVEPOINT flowlab_lastrowid")
                self.lastrowid = None
            finally:
                savepoint.execute("RELEASE SAVEPOINT flowlab_lastrowid")
                savepoint.close()
        return self

    def executemany(self, sql, rows):
        self._cursor.executemany(translate_sql(sql), rows); return self

    def fetchone(self): return self._cursor.fetchone()
    def fetchall(self): return self._cursor.fetchall()
    def __iter__(self): return iter(self._cursor)
    def close(self): self._cursor.close()

    @property
    def rowcount(self): return self._cursor.rowcount


class PostgreSQLConnection:
    def __init__(self, connection): self._connection = connection
    def cursor(self): return PostgreSQLCursor(self._connection.cursor())
    def execute(self, sql, parameters=()): return self.cursor().execute(sql, parameters)
    def executemany(self, sql, rows): return self.cursor().executemany(sql, rows)
    def commit(self): self._connection.commit()
    def rollback(self): self._connection.rollback()
    def close(self): self._connection.close()


def get_connection():
    if database_backend() == "postgresql":
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                "PostgreSQL is configured but psycopg is not installed. "
                "Run: pip install -r requirements-postgresql.txt"
            ) from exc
        return PostgreSQLConnection(psycopg.connect(database_url()))

    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def managed_connection():
    """Yield a transaction and always release its database connection."""
    connection = get_connection()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
