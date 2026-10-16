# Integrated E&I delivery — 14 October 2026

## Installed implementation

The integrated Flask/Django application remains on port 5050, with E&I under `/ei-lab/`. Its separate authentication and laboratory records are retained. The original comparison application on port 8000 is not modified by this delivery.

| Area | Delivered |
|---|---|
| Job Records | Horizontal searchable register; Lab/Field, per-UUT request types, statuses and record view |
| New jobs | Click-to-open four-step form below records; private saved drafts; optimistic edit conflict checks |
| Documents | Lab submission requires uploaded service request and waybill; Field optional request; protected file access and Excel preview |
| Approval | Sender, sender with comment, revert, or another person; actual assignments separate from suggestions; commencement gate |
| Timing | 48 elapsed hours awaiting approval becomes Pending; overdue notifications; reasoned schedule proposals preserve original deadline |
| Technical work | Per-UUT assessment/calibration/repair/uncertainty records; upload or approved digital template; server draft autosave/recovery; controlled review/amendment |
| Completion | Required approved records checked per UUT; all UUTs must close before managed job completion |
| Personnel | Profile history, evidence, competency assessments, method/scope authorizations, revisions/revocation, protected QR verification |
| Scope settings | Maintained register; create/edit; archive/restore without removing existing references; active scopes selectable in new jobs; audit snapshots |
| Reports | Retained PDF/Excel technical-record exports, EATL logo and method/reference snapshots; idempotent export |
| Existing records | Historical jobs retain legacy workflow; no historical calculation results fabricated or reinterpreted |

## Files

- `jobrec-review/core/models.py`, `workflow_models.py`, migrations `0044`–`0048`: additive records and workflow state.
- `ei_workflow.py`: submission, authorization, calculation-record persistence, decisions, timing and close-out rules.
- `ei_views.py`, `urls.py`, `views.py`, `forms.py`: protected endpoints and Settings/Scope maintenance.
- `private_storage.py`, `ei_reports.py`: controlled uploads and retained exports.
- `templates/core/jobs/`, personnel competency and settings templates, `ei-workflow.js`, `flowlab-theme.css`, `base.html`: user-facing workflow and navigation.
- `workflow_worker.py`, reminder command and `scripts/run_integrated_server.py`: deadline evaluation.
- `deployment/flowlab_launcher.py`, `build_windows.ps1`: packaged-launcher support. A new executable bundle has **not** been built.

## Roles and status rules

Creators edit their private draft/reverted submission. Suggested personnel do not gain draft access. Supervisors decide submitted jobs; the actual eligible assigned person commences an approved job. Technical authors cannot approve their own records. Active scoped competency/authorization and permissions are required for controlled technical work. Settings remain administrator-permission protected.

New submitted jobs are Scheduled while awaiting approval; after 48 elapsed hours they become Pending. Commencement makes them Ongoing. All required UUT close-outs make them Completed. Approval state remains distinct from progress status. The deadline worker runs every minute with the integrated launcher. Notifications are in-app; outbound email delivery is not configured here.

## Verification

- 39 isolated E&I acceptance tests passed, including scope creation, archive/restore, selection retention, approval branches, conditional documents, clock boundaries, autosave/conflicts, report retention and mixed-UUT completion.
- 75 isolated existing-platform/uncertainty/equipment regression tests passed.
- Migration consistency check passed; production migrations through `0048` applied.
- Browser QA on a separate disposable instance exercised the job register, click-to-open wizard and digital draft save/reload. It did not use production credentials or records.

## Operations (PowerShell, project directory)

```powershell
.venv\Scripts\python.exe scripts\run_integrated_server.py
.venv\Scripts\python.exe scripts\run_ei_acceptance.py
.venv\Scripts\python.exe scripts\run_isolated_regressions.py
.venv\Scripts\python.exe scripts\backup_integrated_ei.py
```

Pre-migration backup: `data/migration_backups/ei_modernization_20261014_113402` contains the PostgreSQL dump, uploaded records and SQLite snapshots. New controlled files live under `data/private/ei-lab` and are included by the updated backup script.

Rollback must first be rehearsed on a copy. Reversing core migrations to `0043` removes the new workflow tables/fields and does not reconstruct all converted suggestion data. Full rollback requires restoration of the database dump and matching uploaded/private files together. No rollback was executed.

## Configuration / limitations

Administrators must enter the real laboratory scopes and approve their real method-specific digital templates. Supervisors must record actual personnel competency and authorization evidence. Test method fixtures were confined to isolated QA databases. No real calibration formula or uncertainty value was invented.

Digital schema arithmetic and stored table inputs are supported; arbitrary spreadsheet/workbook execution and automatic conversion of every legacy form into a validated digital template are not supplied. Historical linked uncertainty records that lack original coverage-factor/unit metadata need verification before issued reporting. Current report exports use captured technical-record data, not a replacement uncertainty engine. Executable distribution rebuild and outbound email configuration remain separate deployment tasks.
