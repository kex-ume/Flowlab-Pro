import unittest

from app.database.database import translate_sql
from scripts.migrate_sqlite_to_postgres import normalized_row, postgres_ddl


class PostgreSQLCompatibilityTests(unittest.TestCase):
    def test_qmarks_outside_literals_are_translated(self):
        sql = translate_sql("SELECT '?' AS literal FROM users WHERE username=?")
        self.assertEqual(sql, "SELECT '?' AS literal FROM users WHERE username=%s")

    def test_date_and_case_insensitive_sql_are_translated(self):
        sql = translate_sql(
            "SELECT * FROM projects WHERE customer_name=? COLLATE NOCASE "
            "AND due_date <= date('now', '+30 days') ORDER BY project_name COLLATE NOCASE"
        )
        self.assertIn("LOWER(customer_name) = LOWER(%s)", sql)
        self.assertIn("INTERVAL '+30 days'", sql)
        self.assertIn("ORDER BY LOWER(project_name)", sql)

    def test_dynamic_date_modifier_is_translated(self):
        sql = translate_sql("SELECT date('now', ?)")
        self.assertEqual(sql, "SELECT TO_CHAR(CURRENT_DATE + (%s)::interval, 'YYYY-MM-DD')")

    def test_insert_or_ignore_is_translated(self):
        sql = translate_sql("INSERT OR IGNORE INTO roles(name) VALUES (?)")
        self.assertEqual(sql, "INSERT INTO roles(name) VALUES (%s) ON CONFLICT DO NOTHING")

    def test_sqlite_schema_types_are_translated(self):
        ddl = postgres_ddl(
            "CREATE TABLE samples (id INTEGER PRIMARY KEY AUTOINCREMENT, value REAL, "
            "created_at DATETIME DEFAULT (datetime('now')))"
        )
        self.assertIn("id BIGSERIAL PRIMARY KEY", ddl)
        self.assertIn("value DOUBLE PRECISION", ddl)
        self.assertIn("created_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP)", ddl)

    def test_empty_values_are_normalized_only_for_typed_fields(self):
        row = normalized_row(("", "", "", "note"), ("REAL", "INTEGER", "TEXT", "TEXT"))
        self.assertEqual(row, (None, None, "", "note"))


if __name__ == "__main__":
    unittest.main()
