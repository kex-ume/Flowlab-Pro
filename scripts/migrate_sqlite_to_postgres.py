"""Safely copy a FlowLab Pro SQLite database into PostgreSQL."""

import argparse
import os
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path


def quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def postgres_ddl(sql: str) -> str:
    converted = re.sub(r"datetime\(\s*'now'\s*\)", "CURRENT_TIMESTAMP", sql, flags=re.I)
    converted = re.sub(r"date\(\s*'now'\s*\)", "CURRENT_DATE", converted, flags=re.I)
    converted = re.sub(
        r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b",
        "BIGSERIAL PRIMARY KEY",
        converted,
        flags=re.I,
    )
    converted = re.sub(r"\bAUTOINCREMENT\b", "", converted, flags=re.I)
    converted = re.sub(r"\bINTEGER\b", "BIGINT", converted, flags=re.I)
    converted = re.sub(r"\bREAL\b", "DOUBLE PRECISION", converted, flags=re.I)
    converted = re.sub(r"\bBLOB\b", "BYTEA", converted, flags=re.I)
    converted = re.sub(r"\bDATETIME\b", "TIMESTAMP", converted, flags=re.I)
    converted = re.sub(r"\s+COLLATE\s+NOCASE\b", "", converted, flags=re.I)
    return converted


def ordered_tables(connection) -> list[str]:
    rows = connection.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    names = {row[0] for row in rows}
    dependencies = {}
    for name, ddl in rows:
        references = set(re.findall(r"\bREFERENCES\s+[\"`\[]?([A-Za-z0-9_]+)", ddl or "", re.I))
        dependencies[name] = references & names - {name}

    result, remaining = [], set(names)
    while remaining:
        ready = sorted(name for name in remaining if not (dependencies[name] & remaining))
        if not ready:  # Cycles can be deferred because constraints are checked at transaction end.
            ready = [sorted(remaining)[0]]
        result.extend(ready)
        remaining.difference_update(ready)
    return result


def source_summary(connection, tables):
    return {table: connection.execute(f"SELECT COUNT(*) FROM {quote(table)}").fetchone()[0] for table in tables}


def normalized_row(row, declared_types):
    """Account for SQLite's permissive empty strings in typed PostgreSQL fields."""
    text_types = ("CHAR", "CLOB", "TEXT", "BLOB")
    return tuple(
        None if value == "" and not any(kind in (declared_type or "").upper() for kind in text_types) else value
        for value, declared_type in zip(row, declared_types)
    )


def migrate(sqlite_path: Path, target_url: str, drop_existing: bool) -> None:
    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit("Install PostgreSQL support first: pip install -r requirements-postgresql.txt") from exc

    source = sqlite3.connect(sqlite_path)
    source.execute("PRAGMA foreign_keys = ON")
    tables = ordered_tables(source)
    counts = source_summary(source, tables)
    target = psycopg.connect(target_url)
    try:
        with target.transaction():
            cursor = target.cursor()
            if drop_existing:
                cursor.execute("DROP SCHEMA public CASCADE")
                cursor.execute("CREATE SCHEMA public")

            existing = cursor.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname='public'"
            ).fetchall()
            if existing:
                raise RuntimeError(
                    "Target database is not empty. Use a new database or explicitly pass --drop-existing."
                )

            cursor.execute("SET CONSTRAINTS ALL DEFERRED")
            for table in tables:
                ddl = source.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()[0]
                cursor.execute(postgres_ddl(ddl))

            for table in tables:
                column_info = source.execute(f"PRAGMA table_info({quote(table)})").fetchall()
                columns = [row[1] for row in column_info]
                declared_types = [row[2] for row in column_info]
                rows = [
                    normalized_row(row, declared_types)
                    for row in source.execute(f"SELECT * FROM {quote(table)}").fetchall()
                ]
                if rows:
                    column_sql = ", ".join(quote(column) for column in columns)
                    placeholders = ", ".join(["%s"] * len(columns))
                    cursor.executemany(
                        f"INSERT INTO {quote(table)} ({column_sql}) VALUES ({placeholders})",
                        rows,
                    )

            indexes = source.execute(
                "SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL ORDER BY name"
            ).fetchall()
            for (index_sql,) in indexes:
                cursor.execute(postgres_ddl(index_sql))

            for table in tables:
                primary_keys = [
                    row[1] for row in source.execute(f"PRAGMA table_info({quote(table)})") if row[5]
                ]
                for column in primary_keys:
                    sequence = cursor.execute(
                        "SELECT pg_get_serial_sequence(%s, %s)", (table, column)
                    ).fetchone()[0]
                    if sequence:
                        cursor.execute(
                            f"SELECT setval(%s, COALESCE((SELECT MAX({quote(column)}) FROM {quote(table)}), 1), "
                            f"EXISTS(SELECT 1 FROM {quote(table)}))",
                            (sequence,),
                        )

            mismatches = []
            for table, source_count in counts.items():
                target_count = cursor.execute(f"SELECT COUNT(*) FROM {quote(table)}").fetchone()[0]
                if source_count != target_count:
                    mismatches.append(f"{table}: SQLite={source_count}, PostgreSQL={target_count}")
            if mismatches:
                raise RuntimeError("Row-count verification failed:\n" + "\n".join(mismatches))
    finally:
        target.close()
        source.close()

    print(f"Migration verified: {sum(counts.values())} rows across {len(tables)} tables.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", type=Path, default=Path("data/flowlab.db"))
    parser.add_argument("--database-url", default=os.environ.get("FLOWLAB_DATABASE_URL", ""))
    parser.add_argument("--apply", action="store_true", help="Perform the migration; otherwise only inspect.")
    parser.add_argument("--drop-existing", action="store_true", help="Erase the target public schema first.")
    args = parser.parse_args()
    if not args.sqlite.is_file():
        parser.error(f"SQLite database not found: {args.sqlite}")

    source = sqlite3.connect(args.sqlite)
    tables = ordered_tables(source)
    counts = source_summary(source, tables)
    source.close()
    print(f"Source: {args.sqlite.resolve()}")
    print(f"Inventory: {len(tables)} tables, {sum(counts.values())} rows")
    if not args.apply:
        print("Inspection only. Add --apply and a PostgreSQL --database-url to migrate.")
        return
    if not args.database_url.startswith(("postgresql://", "postgres://")):
        parser.error("Provide a PostgreSQL URL using --database-url or FLOWLAB_DATABASE_URL.")
    migrate(args.sqlite, args.database_url, args.drop_existing)


if __name__ == "__main__":
    main()
