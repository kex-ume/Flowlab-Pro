"""Safely migrate the E&I Lab SQLite data into FlowLab PostgreSQL.

Run with FlowLab's Python. The script never removes or modifies the SQLite
source database; it creates a timestamped backup and a JSON fixture first.
"""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import psycopg


ROOT = Path(__file__).resolve().parents[1]
EI_ROOT = ROOT / "jobrec-review"
SQLITE_PATH = EI_ROOT / "db.sqlite3"
BACKUP_ROOT = ROOT / "data" / "migration_backups"
DJANGO_SITE = EI_ROOT / ".venv-jobrec" / "Lib" / "site-packages"
DJANGO_TABLE_PREFIXES = ("auth_", "django_", "core_", "authtoken_")


def django_environment(*, sqlite: bool) -> dict[str, str]:
    env = os.environ.copy()
    paths = [str(DJANGO_SITE), str(EI_ROOT)]
    if env.get("PYTHONPATH"):
        paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(paths)
    env["DJANGO_SETTINGS_MODULE"] = "jobrec.settings"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    if sqlite:
        env["EI_LAB_FORCE_SQLITE"] = "1"
        env["DJANGO_DB_PATH"] = str(SQLITE_PATH)
    else:
        env.pop("EI_LAB_FORCE_SQLITE", None)
    return env


def run_manage(*args: str, sqlite: bool, stdout=None) -> None:
    command = [sys.executable, str(EI_ROOT / "manage.py"), *args]
    subprocess.run(
        command,
        cwd=EI_ROOT,
        env=django_environment(sqlite=sqlite),
        check=True,
        stdout=stdout,
    )


def sqlite_counts() -> dict[str, int]:
    connection = sqlite3.connect(SQLITE_PATH)
    try:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        return {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in tables
        }
    finally:
        connection.close()


def postgres_django_tables(database_url: str) -> list[str]:
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname='public' ORDER BY tablename"
            )
            return [
                row[0]
                for row in cursor.fetchall()
                if row[0].startswith(DJANGO_TABLE_PREFIXES)
            ]


def postgres_record_counts(database_url: str) -> dict[str, int]:
    """Return the user-owned rows that indicate whether an import occurred."""
    counts = {}
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            for table in ("auth_user", "core_personnel", "core_job", "core_client"):
                try:
                    cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                    counts[table] = cursor.fetchone()[0]
                except psycopg.errors.UndefinedTable:
                    connection.rollback()
                    counts[table] = 0
    return counts


def latest_fixture() -> Path | None:
    candidates = sorted(BACKUP_ROOT.glob("ei-lab-*/ei-lab-data.json"), reverse=True)
    return candidates[0] if candidates else None


def ensure_utf8_fixture(source: Path) -> Path:
    """Return a UTF-8 fixture without modifying the preserved source export."""
    raw = source.read_bytes()
    try:
        raw.decode("utf-8")
        return source
    except UnicodeDecodeError:
        converted = source.with_name("ei-lab-data-utf8.json")
        converted.write_text(raw.decode("cp1252"), encoding="utf-8")
        return converted


def main() -> None:
    database_url = (
        os.environ.get("EI_LAB_DATABASE_URL")
        or os.environ.get("FLOWLAB_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or ""
    ).strip()
    if not database_url.lower().startswith(("postgresql://", "postgres://")):
        raise SystemExit("FlowLab PostgreSQL is not configured in this process.")
    if not SQLITE_PATH.is_file():
        raise SystemExit(f"E&I SQLite database was not found: {SQLITE_PATH}")

    existing_tables = postgres_django_tables(database_url)
    if existing_tables:
        counts = postgres_record_counts(database_url)
        if any(counts.values()):
            raise SystemExit(
                "Migration stopped: PostgreSQL already contains E&I user/domain records "
                f"({counts}). No data was changed."
            )
        fixture = latest_fixture()
        if fixture is None:
            raise SystemExit(
                "Migration stopped: the E&I schema exists but no backup fixture was found."
            )
        fixture = ensure_utf8_fixture(fixture)
        run_manage("loaddata", str(fixture), sqlite=False)
        run_manage("check", sqlite=False)
        print(f"BACKUP={fixture.parent}")
        print("MIGRATION=complete-resumed")
        return

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = BACKUP_ROOT / f"ei-lab-{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    database_backup = backup_dir / "db.sqlite3"
    fixture_path = backup_dir / "ei-lab-data.json"
    counts_path = backup_dir / "sqlite-counts.json"

    shutil.copy2(SQLITE_PATH, database_backup)
    counts = sqlite_counts()
    counts_path.write_text(json.dumps(counts, indent=2), encoding="utf-8")

    with fixture_path.open("w", encoding="utf-8") as fixture:
        run_manage(
            "dumpdata",
            "--natural-foreign",
            "--natural-primary",
            "--exclude", "contenttypes",
            "--exclude", "auth.permission",
            "--exclude", "admin.logentry",
            "--exclude", "sessions",
            "--indent", "2",
            sqlite=True,
            stdout=fixture,
        )

    run_manage("migrate", "--noinput", sqlite=False)
    run_manage("loaddata", str(ensure_utf8_fixture(fixture_path)), sqlite=False)
    run_manage("check", sqlite=False)

    print(f"BACKUP={backup_dir}")
    print(f"SQLITE_TABLES={len(counts)}")
    print(f"SQLITE_ROWS={sum(counts.values())}")
    print("MIGRATION=complete")


if __name__ == "__main__":
    main()
