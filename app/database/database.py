import sqlite3
from pathlib import Path


DATABASE_PATH = Path("data/flowlab.db")


def get_connection():
    DATABASE_PATH.parent.mkdir(exist_ok=True)

    return sqlite3.connect(DATABASE_PATH)