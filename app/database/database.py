import sqlite3
from contextlib import contextmanager
from pathlib import Path


DATABASE_PATH = Path("data/flowlab.db")


def get_connection():
    DATABASE_PATH.parent.mkdir(exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def managed_connection():
    """Yield a transaction and always release its SQLite file handle."""
    connection = get_connection()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
