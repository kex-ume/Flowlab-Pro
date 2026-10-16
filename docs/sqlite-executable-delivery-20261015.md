# SQLite single-executable delivery — 15 October 2026

Use `release/EATL-SQLite-Ready-20261015/EATL-Integrated-Lab.exe` (65,321,993 bytes). This supersedes the earlier folder-based deployment and the intermediate single-file test build.

## Verified migration

- PostgreSQL was read using a REPEATABLE READ, READ ONLY transaction. No source rows or schema were changed.
- Copied all 130 public tables and 1,109 rows into a shared SQLite schema initialized from FlowLab and the current E&I Django migrations.
- Verified every copied row using normalized content hashes, counts, foreign-key checks and SQLite integrity checks. Existing account IDs, password hashes, role memberships and job relationships are preserved; authentication systems remain separate.
- Copied 1,184 associated files and verified each SHA-256 against its source. Relative attachment paths remain portable.
- The complete verified database and files are embedded as first-install seed data. This executable is PRIVATE and must not be publicly distributed.
- PostgreSQL remains active for the original application. Changes made later in either copy are not synchronized automatically.

## Runtime and startup

The executable embeds Python and its runtime DLLs, SQLite, libraries, templates and assets; it does not require a separate `_internal` folder, Python installation or PostgreSQL server. Windows x64 is required. The user screenshot showed a DLL-load failure while launching the older folder-based executable from a temporary ZIP location. The new one-file executable extracts its own runtime; Python and both Visual C++ runtime DLLs were verified inside its archive. The receiving computer's security policy and antivirus must still permit execution and extraction; no clean-machine/remote-computer test was performed.

First launch copies seed records to `%LOCALAPPDATA%/EATL-Integrated-Lab/data/eatl.sqlite3`; later launches retain that database instead of overwriting it. Uploaded files use its data subfolders. Installation secrets are generated locally. Both modules use the same SQLite file, with independent portable cookies to avoid conflicts with the source application. SQLite connections allow a 30-second busy timeout and use WAL at runtime.

Startup uses a writable user-data folder. A named mutex reopens an already-running instance. It chooses a free local port from 5050–5070 unless a port is specified. Runtime errors display a native Windows message and save `startup-error.log`; the active URL is recorded in `runtime-status.json`. Pending local Django migrations receive a SQLite backup before automatic application. Closing the browser does not stop the background server.

Controlled cover generation still requires Microsoft Excel on Windows. It is not a public HTTPS deployment; do not host the live SQLite file on a network share. The executable is unsigned.

## Tests

- 72 E&I acceptance tests passed.
- 75 FlowLab/integration regression tests passed.
- 5 portable-deployment tests passed, including source-read-only copy/rollback, data conversion, seed persistence and native error-dialog invocation.
- Authenticated views against a disposable copy of migrated data: 8 E&I pages and 6 FlowLab pages returned HTTP 200.
- Frozen executable first-run test passed: seeded records, both logins, frontend assets, SQLite deployment check, existing account presence and repeated-launch persistence.
- Ordinary default-port launch and duplicate-instance behaviour passed with a disposable runtime.
- One-file archive contains Python and both Visual C++ runtime DLLs; ZIP CRC validation passed.
- Original running application still responded HTTP 200 after verification.

## Implementation

`app/database/sqlite_snapshot.py`, `scripts/export_portable_sqlite.py`, `scripts/verify_portable_snapshot.py`: verified read-only export and file/view verification. `deployment/flowlab_launcher.py`: single-file initialization, SQLite-only settings, shared persistent DB, cookies, startup/migration backups, mutex and diagnostics. `deployment/build_sqlite_windows.ps1`, `README-SQLite.txt`: private single-file build and usage. `app/database/database.py`, `jobrec-review/jobrec/settings.py`: SQLite timeout. `scripts/check_windows_bundle.py`, `tests/test_portable_deployment.py`: frozen runtime and unit coverage. No source personnel workflows were replaced.
