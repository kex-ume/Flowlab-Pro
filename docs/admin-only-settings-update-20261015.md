# Administrator-only User Management

Superseding executable: `release/EATL-SQLite-AdminOnly-20261015/EATL-Integrated-Lab.exe`.

SHA-256: `5ed6dfa088422f8b0a355fa41e164286a7d2ee6c1fc33ffc7e29747350a6f1d4`.

User Management is opened from the administrator's Settings page, not the sidebar. Chief, HOD, Supervisor, Engineer, Technician and Guest roles cannot open either `/users` or `/settings/users` or submit account mutations. The endpoint enforces Administrator explicitly, independent of template visibility. E&I's sidebar shortcut has been removed; an administrator action is in its Settings content instead. No database migration is needed for this correction.

Validation: 76 FlowLab/integration regression tests, 43 shared account checks and 72 E&I acceptance tests passed. Added non-administrator GET/POST denial and Settings visibility coverage. Existing SQLite data is reused by the executable; stop the previous process before updating and retain the complete data folder.
