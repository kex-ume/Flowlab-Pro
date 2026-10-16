# E&I personnel update — 14 October 2026

## Delivered

Existing Django Personnel identities, role permissions, QR tokens and job/log relationships were reused. No Flask personnel models, routes, credentials or workflows were changed.

- Horizontal searchable/filterable personnel register: Name/ID, Qualification, Competency, Authorization, Training, View. Text colours: green Active, grey Not Uploaded, red Expired, amber Pending Review.
- Personnel card: personal details, separate qualifications/training/supporting evidence, scope/method assessments, technical authorizations, linked job/UUT/calibration history, correction requests and revision history. Add/revise forms open only on request.
- Qualification/training evidence starts Pending Review and becomes Active only after independent verification. No expiry is assigned to permanent academic qualifications. Explicit certificate/reassessment/authorization dates determine expiry. Missing records are not inferred from free-text summaries.
- Verified evidence is view-only; a replacement file creates a pending revision. The old approved version stays retained until independent verification supersedes it. Competency and authorization revisions preserve their predecessor and actual officer attribution.
- Staff can request corrections to permitted records without altering the approved record. Maintaining officers resolve requests separately from record revisions.
- Suspension/revocation blocks restricted work; renewal uses a formal authorization revision. Administrative superuser status no longer substitutes for technical competence or authorization.
- Active E&I personnel populate assignment controls. Managed and legacy restricted assignments/analyst selections validate actual scope authorization. Actual analysts, uploaders/recorders, reviewers and approvers remain separately linked; read-only counts come from existing relations, not duplicated jobs.
- Stable QR link requires E&I authentication and displays only personnel ID, name, position, scope specialty, authorized scope/activity and current authorization status. It never renders qualifications, CVs, contacts or private files. Direct private-file access remains permission checked.
- The existing integrated deadline worker now sends deduplicated in-app reminders 30 days before applicable evidence/competency/authorization reviews and after expiry. Suspension/revocation and correction requests also notify responsible people. No outbound email service was introduced.

## Required officer designation

In E&I Settings → Roles, assign these new permissions to the institution's actual designated officers:

| Permission | Authority |
|---|---|
| `verify_personnel_records` | Independently verify qualifications, training and experience evidence |
| `assess_personnel_competency` | Record/revise scope-specific competency assessments |
| `authorize_personnel` | Approve/revise/suspend/revoke technical authorizations |

These permissions are **not automatically granted to administrators**. `manage_personnel` / supervisor privileges retain basic registration and record-maintenance rights, but do not confer the three technical officer functions. Self-verification, self-assessment and self-authorization are denied. Staff must have real assessment and authorization records before restricted assignment; none were fabricated for the live personnel.

## Files modified / added

- `jobrec-review/core/models.py`, `workflow_models.py`: extend existing evidence, competency and authorization records; correction requests and reminder deduplication.
- `jobrec-review/core/personnel_records.py`: explicit officer permissions, compliance status rules, actual analyst checks and reminder evaluation.
- `jobrec-review/core/ei_views.py`, `views.py`: record card, minimal QR verification, protected actions, directory filters and legacy assignment/review controls.
- `jobrec-review/core/api/views.py`: equivalent legacy analyst/reviewer/approver checks on APIs.
- `jobrec-review/core/workflow_worker.py`: personnel review reminders alongside existing job clocks.
- `jobrec-review/core/ei_workflow.py`: remove technical superuser bypass; reject suspended authorization and superseded competency for restricted work.
- `jobrec-review/core/admin.py`: controlled history models are read-only; basic admin profile edits produce history and personnel hard deletion is disabled.
- `jobrec-review/core/templates/core/personnel/{list,competency,verification,status,evidence_form,job_history}.html`, `templates/core/base.html`, `static/core/flowlab-theme.css`: integrated UI and coloured status text.
- `jobrec-review/core/tests.py`: officer, evidence, privacy, assignment, reminders, counts and revision tests.
- `scripts/apply_ei_personnel_migration.py`: migrate plus assert original personnel/job/log/evidence/competency/authorization snapshots remain unchanged.

## Migrations and preservation

- `0049_personnel_records`: additive evidence verification/expiry/revision fields, competency predecessor, authorization suspension, correction request and reminder tables; creates officer permission definitions without assigning them.
- `0050_personnel_review_notification`: names the personnel review notification category.
- Both migrations applied successfully; migration consistency check passed.
- Before/after preservation comparison passed for all existing live E&I data: 2 personnel, 3 jobs, 0 calibration logs, 0 evidence records, 0 competency assessments and 0 authorization records. Existing IDs, basic data, QR tokens and job status were unchanged.
- Pre-migration backup: `data/migration_backups/ei_modernization_20261014_193422`.

## Tests

The isolated E&I suite covers registration/credential preservation; private drafts and job approval; designated officers and blocked administrator/self-approval bypass; evidence verification/revision; permanent qualifications; actual expiry; superseded/reassessment competency; suspended job assignment; actual author/uploader identities; read-only counts; minimal QR verification, anonymous access and document privacy; correction requests; deduplicated review reminders; report exports and page rendering.

Commands:

```powershell
.venv\Scripts\python.exe scripts\run_ei_acceptance.py
.venv\Scripts\python.exe scripts\run_isolated_regressions.py
```

Final results: **54 E&I acceptance tests passed**, **75 existing-platform regression tests passed**. Django system checks and migration consistency checks passed. Tests use isolated databases and disposable files, not the live personnel records. The final E&I suite additionally verifies legacy web/API technical privilege restrictions, correct Personnel-vs-User identity relationships, and renewal after revocation without erasing the original reason.
