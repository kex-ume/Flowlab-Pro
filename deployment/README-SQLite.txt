EATL INTEGRATED LAB - SQLITE SINGLE-EXE EDITION

START
Run EATL-Integrated-Lab.exe. Python, Flask, Django, Waitress, SQLite and the application's templates are embedded. You do not need PostgreSQL, Python, a virtual environment or a separate _internal folder. This is a Windows x64 executable, not a macOS or Linux application.
The browser opens automatically. Port 5050 is preferred; if occupied, another free port between 5051 and 5070 is used. A second double-click reopens the already-running instance.

YOUR RECORDS
The verified PostgreSQL snapshot and associated uploaded files are embedded in this PRIVATE executable. Existing usernames and password hashes are retained; both module logins remain independent. PostgreSQL was not changed. Entries added later to PostgreSQL do not automatically synchronize with this offline copy.
On the first launch the embedded data is copied to:
%LOCALAPPDATA%\EATL-Integrated-Lab\data\eatl.sqlite3
Uploaded files remain in the subfolders beneath data. Future launches reuse this data and NEVER replace it with the embedded snapshot. Keep the data folder safe and back it up regularly. Copying only an updated EXE does not update or overwrite an already-installed database.
Do not distribute this executable publicly: it contains lab records and account password hashes.

STARTUP / ERRORS
UPDATE FROM AN EARLIER SQLITE EXE
Stop the old EATL-Integrated-Lab process in Task Manager before running this update. Keep your existing data folder; do not delete or replace it. Pending schema migrations make a backup before applying. User Management is in Administrator Settings, with Cancel/Close controls. Linked administrator accounts share credentials across both modules; linking an existing conflicting username requires explicit administrator confirmation. In E&I, Administrator/Chief now have full module access and role-based technical review/approval without an individual scope grant, as explicitly requested by the lab owner. Actual analyst assignments still validate current competence and scope authorization. Authors cannot approve their own records. Record Maintenance & Archive removes unwanted records from active use without destroying historical evidence. Existing PostgreSQL development data remains independent and is not synchronized.

THIS REVIEW UPDATE
FlowLab environmental records, live read-only Analytics, Chief personnel registration for either lab, and clickable breadcrumbs are included. New E&I job submissions require independent Supervisor review followed by independent Chief/Admin approval before assignment and commencement. Add a separate Supervisor and Chief/Administrator account for this workflow; one person cannot perform all stages. Existing historical approvals are preserved.
The accompanying workflow review identifies remaining design gaps: equipment, CAPA and some document workflows do not yet all have a separately persisted Supervisor-review stage before Chief approval. Work Instruction and Forms registers remain marked pending. This review build does not claim completion of those unimplemented stages or accreditation certification.

STARTUP / ERRORS
Startup errors show a visible dialog and are saved to:
%LOCALAPPDATA%\EATL-Integrated-Lab\startup-error.log
The active local URL is recorded in runtime-status.json in that same folder. Closing the browser does not stop the server; use Task Manager to end EATL-Integrated-Lab when finished.
For diagnostics from PowerShell: Start-Process .\EATL-Integrated-Lab.exe -ArgumentList '--check-deployment' -Wait -PassThru
For a specific port: .\EATL-Integrated-Lab.exe --port 5052
Pending local E&I migrations are backed up and applied at startup. Original PostgreSQL data is never modified by this executable.

WINDOWS SECURITY / DEPENDENCIES
This executable is unsigned and Windows may show a security warning. Verify its SHA-256 hash and source before running. If security software quarantines a runtime component, ask your IT administrator to review it; do not disable antivirus protection.
Controlled cover-page generation still requires Microsoft Excel installed on Windows. Its controlled workbook and helper are included; other PDF/Excel reporting uses the embedded libraries.
This is a local SQLite deployment. Do not put the live SQLite database on a shared network drive or treat this EXE as a public HTTPS host.
