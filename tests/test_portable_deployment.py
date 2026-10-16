from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal
import importlib.util
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

from app.database.sqlite_snapshot import copy_postgres, sqlite_value

spec = importlib.util.spec_from_file_location('portable_launcher', Path(__file__).resolve().parents[1] / 'deployment' / 'flowlab_launcher.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class PortableDeploymentTests(unittest.TestCase):
    def test_listener_does_not_reuse_an_occupied_windows_port(self):
        import socket
        with socket.socket() as occupied:
            if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):
                occupied.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
            occupied.bind(('127.0.0.1',0));occupied.listen(1)
            port=occupied.getsockname()[1]
            with self.assertRaises(OSError):
                launcher.create_local_server(lambda environ,start: [],port)

    def test_listener_uses_the_reserved_port(self):
        server=launcher.create_local_server(lambda environ,start: [],0)
        try:
            self.assertGreater(int(server.effective_port),0)
        finally:
            server.close()

    def test_snapshot_value_conversion_preserves_uuid_dates_and_json(self):
        identifier = uuid.uuid4()
        self.assertEqual(sqlite_value(identifier), identifier.hex)
        self.assertEqual(sqlite_value(Decimal('0.1200')), '0.1200')
        self.assertEqual(sqlite_value(True), 1)
        self.assertEqual(sqlite_value(datetime(2026, 10, 15, 8, 30, tzinfo=timezone.utc)), '2026-10-15 08:30:00')
        self.assertEqual(sqlite_value({'b': 2, 'a': 1}), '{"a":1,"b":2}')

    def test_embedded_database_installs_once_and_preserves_later_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            seed = root / 'embedded' / 'seed-data'
            seed.mkdir(parents=True)
            with closing(sqlite3.connect(seed / 'eatl.sqlite3')) as database:
                database.execute('CREATE TABLE records(id INTEGER PRIMARY KEY, name TEXT)')
                database.execute("INSERT INTO records VALUES (1, 'original')")
                database.commit()
            runtime = root / 'runtime'
            runtime.mkdir()
            with patch.object(sys, '_MEIPASS', str(seed.parent), create=True):
                launcher.seed_sqlite_data(runtime / 'data')
                with closing(sqlite3.connect(runtime / 'data' / 'eatl.sqlite3')) as database:
                    database.execute("INSERT INTO records VALUES (2, 'later')")
                    database.commit()
                launcher.seed_sqlite_data(runtime / 'data')
                with closing(sqlite3.connect(runtime / 'data' / 'eatl.sqlite3')) as database:
                    self.assertEqual(database.execute('SELECT COUNT(*) FROM records').fetchone()[0], 2)

    def test_seed_refuses_to_overwrite_existing_files_when_database_is_missing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            seed = root / 'embedded' / 'seed-data'
            seed.mkdir(parents=True)
            with closing(sqlite3.connect(seed / 'eatl.sqlite3')):
                pass
            data = root / 'data'
            data.mkdir()
            evidence = data / 'evidence.sqlite3'
            with closing(sqlite3.connect(evidence)):
                pass
            with patch.object(sys, '_MEIPASS', str(seed.parent), create=True):
                with self.assertRaisesRegex(RuntimeError, 'not overwritten'):
                    launcher.seed_sqlite_data(data)
            self.assertTrue(evidence.exists())
            self.assertFalse((data / 'eatl.sqlite3').exists())

    def test_native_startup_error_is_visible(self):
        with patch.dict(os.environ, {'EATL_NO_DIALOG':'0'}), patch('ctypes.windll.user32.MessageBoxW') as dialog:
            launcher.show_message('Test startup error')
            dialog.assert_called_once()
            self.assertIn('Test startup error', dialog.call_args.args)

    def test_snapshot_failure_rolls_back_target_and_never_writes_source(self):
        class Cursor:
            description = [SimpleNamespace(name='id'), SimpleNamespace(name='parent_id')]
            def __init__(self, table):
                self.table = table
                self.sent = False
                if table == 'parent':
                    self.description = [SimpleNamespace(name='id')]
            def fetchmany(self, amount):
                if self.sent:
                    return []
                self.sent = True
                return [(1,)] if self.table == 'parent' else [(1, 999)]
        class Source:
            statements = []
            def execute(self, sql):
                self.statements.append(sql)
                if 'information_schema.tables' in sql:
                    return [('parent',), ('child',)]
                return Cursor('parent' if '"parent"' in sql else 'child')
            def rollback(self):
                pass
            def close(self):
                pass
        source = Source()
        fake = SimpleNamespace(connect=lambda url: source, IsolationLevel=SimpleNamespace(REPEATABLE_READ='repeatable'))
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'copy.sqlite3'
            with closing(sqlite3.connect(target)) as database:
                database.executescript('CREATE TABLE parent(id INTEGER PRIMARY KEY); CREATE TABLE child(id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES parent(id)); INSERT INTO parent VALUES(99);')
            with patch.dict(sys.modules, {'psycopg':fake}):
                with self.assertRaisesRegex(RuntimeError, 'Foreign-key'):
                    copy_postgres('postgresql://unused', target)
            with closing(sqlite3.connect(target)) as database:
                self.assertEqual(database.execute('SELECT id FROM parent').fetchall(), [(99,)])
            self.assertTrue(source.read_only)
            self.assertTrue(all(statement.startswith('SELECT') for statement in source.statements))


if __name__ == '__main__':
    unittest.main()
