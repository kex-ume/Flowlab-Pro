# E&I modernization — discovery, 14 October 2026

The active web entry point is `integrated_app:application`: Werkzeug DispatcherMiddleware mounts the Django project `jobrec-review` at `/ei-lab` and Flask `web_app:app` at the root. `main.py` is the separate Qt desktop entry point. The preserved `jobrec-original` tree is reference-only. Both domains use PostgreSQL when configured, with separate tables, actor identities, permissions and cookies; Django's cookies are scoped to `/ei-lab/`. Flask administration calls Django ORM inside Django transactions for E&I accounts. This is an explicit administrative boundary, not shared login authority.

| Requirement | Current Django | Adjustment | Files / migration | Risk |
|---|---|---|---|---|
| Job Records / hidden Add form | New UI in progress; legacy job stages | Four-step private-draft wizard and independent status | job workflow views/templates; 0044–0045 | Additive |
| Per-UUT request types | WaybillItem and linked technical logs | JobUUT relation reuses existing item without requiring Field waybill | workflow models/services | Existing IDs retained |
| Submission / four decisions / commencement | No parent-job approval gate | Transactional E&I approval/assignment audit | workflow services and endpoints | Existing jobs remain legacy |
| Lab/Field documents | Uploaded waybill file; no job service request | Protected document records, conditional submit checks | document service | New protected storage |
| 48-hour / overdue / revised schedules | Reminder command; new overdue code unfinished | Idempotent worker and approved schedule revisions | workflow clock command/worker | No reinterpretation of historical results |
| Calibration templates / autosave | Per-scope labels, procedures, saved readings; no versioned draft API | Approved JSON schema templates and locked draft revisions | technical-record services/UI | Existing certified logs preserved |
| Repair / assessment / uncertainty | Existing pre-cal and calibration logs / uncertainty | Reuse links; add distinct uploaded/digital records and repair history | UUT worklist | No substituted uncertainty engine |
| Personnel / authorizations / QR | Linked Personnel, qualifications, scopes and signature | Controlled evidence, competency and authorization records, protected stable QR | personnel workspace | Separate E&I identities |
| APIs / audit / security | DRF APIs with authenticated but broad permissions | Managed-job guards, ownership and protected downloads | API guards/services | Legacy compatibility |

Backups are created with `scripts/backup_integrated_ei.py` before applying migrations. Baseline system check and migration consistency passed before this extension; current automated test output is recorded in the final delivery notes. Tests run against an isolated SQLite test database and temporary upload directory, never the live database.
