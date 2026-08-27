# FlowLab Pro PostgreSQL migration

PostgreSQL is now the production database option. SQLite remains available when no database URL is set, which keeps local development and the existing automated tests simple.

## 1. Back up the current system

Stop data entry, close the app, and copy these items to a safe location:

- `data/flowlab.db` — application records
- `data/documents` — uploaded files (these are files, not database rows)

The migration utility reads `data/flowlab.db` by default. It does not merge `.temporary_demo` or any other SQLite file automatically.

## 2. Install and create PostgreSQL

Install PostgreSQL 16 or newer on the server. In PostgreSQL, create a dedicated database and login. Example commands inside `psql`:

```sql
CREATE USER flowlab_app WITH PASSWORD 'replace-with-a-long-private-password';
CREATE DATABASE flowlab_pro OWNER flowlab_app;
```

Install the Python server dependencies in the FlowLab Pro virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-postgresql.txt
```

## 3. Inspect and migrate

The first command is read-only and reports the source inventory:

```powershell
.\.venv\Scripts\python.exe scripts\migrate_sqlite_to_postgres.py
```

Set the connection for the current PowerShell window, then perform the copy:

```powershell
$env:FLOWLAB_DATABASE_URL = "postgresql://flowlab_app:YOUR_PASSWORD@127.0.0.1:5432/flowlab_pro"
.\.venv\Scripts\python.exe scripts\migrate_sqlite_to_postgres.py --apply
```

The tool only accepts an empty target database by default. It creates the tables, copies every row, resets generated ID sequences, and compares every table's row count. `--drop-existing` is intentionally required if the target public schema must be erased and rebuilt.

## 4. Start the server

Keep `FLOWLAB_DATABASE_URL` as a protected machine-level environment variable on the server. Do not put the real password in Git. Start the web app with the same environment variable available to the process. For Windows Server:

```powershell
.\.venv\Scripts\waitress-serve.exe --listen=0.0.0.0:5050 web_app:app
```

Allow TCP port 5050 only from the reverse proxy or trusted network. For public use, put IIS, Nginx, or Cloudflare Tunnel in front of the app and use HTTPS.

## 5. Acceptance and rollback

Before allowing normal use, verify sign-in, users, projects/jobs, equipment history, uncertainty draft/approval, notifications, uploaded documents, PDF/CSV exports, and record counts. Keep the SQLite backup unchanged until acceptance is complete.

To roll back, stop the PostgreSQL-backed server, remove `FLOWLAB_DATABASE_URL`, restore `data/flowlab.db` and `data/documents`, then restart. Do not enter records in both databases during the acceptance period; changes made after migration will otherwise exist in only one database.
