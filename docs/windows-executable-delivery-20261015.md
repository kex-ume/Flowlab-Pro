# Windows executable delivery — 15 October 2026

Artifact: `release/EATL-Windows-20261015/EATL-Integrated-Lab-Windows.zip` (51,403,191 bytes).

Extract the entire ZIP and keep `EATL-Integrated-Lab.exe` beside `_internal`. It bundles the Windows x64 Python runtime, Flask, Django, Waitress, PostgreSQL driver, reporting libraries, current templates, E&I migrations and frontend assets. It is unsigned, not an installer or public-hosting service.

## Deployment

Read the included README. Configure `configuration.env` to connect to the existing shared PostgreSQL database; that database server remains an external requirement. Copy existing uploaded files separately into the installation's data folder. Back up databases and files before updates or explicit `--prepare-database`. `--check-deployment` validates packaged resources, Django checks and migration state. The default origin is `http://127.0.0.1:5050/`; `--port` supports local alternatives.

No Python or virtual environment installation is needed on the destination. Controlled FlowLab cover-page rendering still uses Microsoft Excel and the separately supplied controlled cover template. Other reporting uses bundled libraries. No private records, user passwords, database exports or configured connection secrets are shipped. Empty SQLite mode does not reproduce existing PostgreSQL records or provision accounts.

## Implementation

- `deployment/flowlab_launcher.py`: explicit preparation/check commands, port selection, installation-specific secrets, stable local databases outside bundled resources, windowed logging.
- `deployment/build_windows.ps1`: versioned release, refuses to overwrite an existing installation, packages required assets and cover helper, does not copy lab data.
- `deployment/configuration.env.example`, `README-Windows.txt`: configuration and deployment steps.
- `web_app.py`: optional `FLOWLAB_SECRET_KEY`; existing source-mode default unchanged.
- `scripts/check_windows_bundle.py`: isolated frozen executable smoke test.

## Verification

- 7 source integration tests passed.
- Frozen executable prepared disposable SQLite databases and applied all packaged migrations.
- Frozen executable deployment check passed.
- Frozen server on port 5052 returned successful landing page, both module login pages, E&I CSS and workflow JavaScript.
- Packaged PostgreSQL driver connected to the existing configured database for a read-only check: passed, zero pending migrations. No production migration was applied by this check.
- ZIP CRC validation passed across 6,850 entries; no databases, connection configuration or installation secrets included.
- SHA-256 hashes are beside the ZIP in `SHA256SUMS.txt`.

Tests used disposable data for writes; the running source application and port 8000 comparison app were not replaced. Full clean-machine installation, code signing, Excel COM rendering and public HTTPS deployment were not tested by this smoke test.
