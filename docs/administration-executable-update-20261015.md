# SQLite administration update — 15 October 2026

Release: `release/EATL-SQLite-Admin-Update-20261015/EATL-Integrated-Lab.exe`

SHA-256: `9ebbe2472e95388877b5dc3bcd8de72d49b6b09d38751745aabab59c376ef7d5`

This executable includes Settings-based User Management, close/cancel controls, shared linked administrator credentials, password-change synchronization, an E&I Administrator role without automatic technical authorization, recoverable administrative record archiving, and cached FlowLab schema initialization. Shared SQLite account changes use one transaction instead of competing connections.

New Django migration: `0053_integrated_administration`. Startup backs up an existing SQLite database before applying pending migrations. The executable reuses `%LOCALAPPDATA%\EATL-Integrated-Lab\data\eatl.sqlite3`; it does not replace an existing database with embedded seed data. PostgreSQL development data remains independent and is not synchronized by this release.

Validation on disposable databases: 75 FlowLab/integration regression tests, 43 shared-database account/password/archive checks, and 5 portable deployment tests passed. The earlier E&I acceptance run passed 72 tests. No numerical performance benchmark on the user's deployed computer has been performed.

Stop the old executable's process before replacing it. Back up the complete existing runtime data directory. Do not delete the database, uploaded files, or installation secrets. This is a private release containing the previously verified laboratory snapshot; do not publish it openly.
