# Settings, Recycle Bin, user forms and module routing verification

Deployment executable: `release/EATL-Settings-Users-Fix-20261015/EATL-Integrated-Lab.exe`.

SHA-256: `3fcdf5d7093e09519c814f7305c05983d90d8fcb70e47b917f445a78951c6b66`.

## Confirmed cause of the live module-selection problem

Port 5050 was running Waitress with `web_app:app`, the Flask-only application, rather than `integrated_app:application`. Both laboratory entry choices could consequently reach FlowLab authentication. This was a server startup configuration issue, not identical module URLs.

Before the live correction, database and uploaded-file backups were saved under `data/migration_backups/ei_modernization_20261015_220555`. Pending migration `core.0053_integrated_administration` was applied successfully and Django checks passed. The verified Flask-only process was stopped and replaced by `scripts/run_integrated_server.py`. Live startup logs: `output/integrated-verification-4d7df068.*.log`.

Read-only checks on the live port confirmed: `/login` opens FlowLab login; `/ei-lab` and `/ei-lab/` open E&I login; `/ei-lab/settings/` requires E&I authentication, not FlowLab authentication. The integrated source app now uses its own FlowLab session cookie to avoid carrying old generic sessions across database/application changes. Users must sign in again.

Use `Start-EATL.ps1` for source startup. Do not launch the integrated application with `web_app:app`. The executable already launches the integrated WSGI application.

## Packaged application checks

`scripts/check_windows_bundle.py` ran the actual executable with an isolated SQLite database and synthetic administrator. Passed: both logins, authenticated FlowLab Settings and save, User Management, Record Maintenance, Recycle Bin, and E&I company/scopes/roles/permissions Settings tabs. Repeat-launch preservation and deployment checks passed. The real deployed database and user passwords were not changed by these tests.

The launcher now binds an exclusive Windows socket and warns when an older build is still running instead of silently reopening that build. Startup status includes build identity and PID; runtime logging is explicitly configured.

## User Management corrections

Edit/reset forms have a visible top close icon, Cancel control, scrollable content and a sticky close/action area. Opening an editor closes other user editors; opening an Add form closes other user forms. Escape closes the focused editor. User Management remains administrator-only.

Small trash controls beneath both user registers reveal selection checkboxes. Administrator account removal deactivates linked logins and hides them from active user registers while retaining identities and historical work. The administrator master recycle bin restores original access/passwords. Own-account and last-administrator protections, CSRF validation and atomic batch rollback remain enforced.

Prior completed checks: 101 account/removal/restoration checks, 76 FlowLab/integration regression tests, 72 E&I tests, and 7 portable deployment tests. A new landing-link regression also verifies that the actual two workspace links resolve to distinct login pages. No claim is made that every possible user workflow is bug-free or has received interactive browser testing.
