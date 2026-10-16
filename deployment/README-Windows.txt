EATL INTEGRATED LAB MANAGEMENT SOFTWARE - WINDOWS DEPLOYMENT

Keep EATL-Integrated-Lab.exe and its _internal folder together. Extract the entire ZIP to a writable local folder, not Program Files or a temporary ZIP preview.
Python, Django, Flask, Waitress and the reporting libraries are bundled. No virtual environment is required.
The controlled FlowLab Excel-template cover-page generation still requires Microsoft Excel installed on Windows. Other PDF/Excel reports use bundled libraries. Supply the controlled cover template separately at data/templates/report_cover.xlsx (or set FLOWLAB_REPORT_COVER_TEMPLATE); it is not a customer-record export.

EXISTING DATABASE / RECORDS
Copy configuration.env.example to configuration.env and set FLOWLAB_DATABASE_URL to the existing PostgreSQL database URL. E&I uses the same database unless EI_LAB_DATABASE_URL is separately specified. PostgreSQL must be installed or reachable; the ZIP is NOT a database server.
Back up the database and uploaded files before an update. Transfer the original data folder separately beside the executable, preserving its directory structure. This ZIP deliberately contains no passwords, user accounts or private lab records.
Both module authentication systems remain independent. Existing account passwords are retained when connecting to the existing database. Do not use an empty database when expecting existing records.

PREPARE / CHECK (PowerShell in this folder)
.\EATL-Integrated-Lab.exe --prepare-database
This explicitly initializes FlowLab tables and applies E&I migrations. Run only after backing up an existing database. It does not create administrator accounts or copy records.
.\EATL-Integrated-Lab.exe --check-deployment
Success creates deployment-check.json with status "passed". Errors are recorded in startup-error.log and runtime.log. Because the executable has no console, use Start-Process -Wait -PassThru when checking its exit status.

START
Double-click EATL-Integrated-Lab.exe. Your browser opens http://127.0.0.1:5050/.
For another local port: .\EATL-Integrated-Lab.exe --port 5052
Stop an already-running instance before replacing files. Closing the browser does not stop the server; stop EATL-Integrated-Lab in Task Manager.
Dashboard reminders run while the executable is running.

FRESH LOCAL INSTALLATION
Blank database URLs use empty local SQLite databases. Prepare the database first; then an authorized administrator must provision module accounts. No default passwords are shipped. SQLite mode is not the shared PostgreSQL deployment.

BACKUP / SAFETY
Keep configuration.env, data (including installation-secrets.json), the databases, uploads and private files safe. Do not distribute those secrets with the ZIP.
This build listens on localhost for local deployment/review. Public hosting requires separate HTTPS, firewall, backup and security configuration.
The executable is unsigned; Windows may show a SmartScreen warning. Verify the supplied SHA-256 hash and source before running.
