# Chief record removal and administrator recovery

Release: `release/EATL-Chief-Record-Recovery-20261015/EATL-Integrated-Lab.exe`

SHA-256: `286b3809e7e8b9732f1289aae33321b9bf0989f4e4e8bb5976bcb3501d0a8b7a`

## Behaviour

Small 28px trash controls appear at the lower-right edge of connected record areas for Chief/Administrator identities. Clicking reveals 16px per-record checkboxes, a selection count, Remove Selected and Cancel. Removal requires a meaningful reason and confirmation. Requests are CSRF-protected, validate a fixed record-type catalog, and commit the whole batch atomically (maximum 100 records). Ordinary staff cannot call removal endpoints.

Deletion is reversible removal from active use, not physical deletion. Original IDs, files, relationships, approval states and calculation snapshots stay stored. Approved/verified evidence can be removed without rewriting it. Immutable audit/revision history, accounts, permissions and internal system configuration are not offered as arbitrary deletion targets. User Management remains administrator-only.

The Administrator's Recycle Bin includes a Master Recycle Bin grouped by removal month. Administrator restoration requires a reason and reinstates the original record. Chief users cannot restore from this master bin. The previous FlowLab recycle/archive workflow is preserved for records previously removed there.

## Connected operational types

- FlowLab: projects, jobs, laboratory equipment, calibration/maintenance history, controlled documents, general quality records, CAPA, personnel documents, ISO clause evidence, uncertainty calculations, CMC revisions, conformity assessments, generated covers and lab service requests.
- E&I: jobs, clients, personnel, laboratory equipment and its supporting records, client received equipment/UUTs, waybills, environmental logs, pre-calibration and calibration logs, technical records, procedures, scopes, evidence/training, competencies, authorizations, job documents, CAPA and its documents, log templates and uncertainty budgets.

E&I default managers exclude retained tombstones from active queries; base managers retain historical FK resolution and recovery access. Explicit primary IDs are attached to nested evidence/assessment tables to prevent removing a linked parent by mistake. Ambiguous links without explicit primary IDs are deliberately not treated as deletable records. This is not a claim that every page layout or numerical child row has been interactively verified.

## Implementation and checks

Main implementation: `app/modules/record_maintenance.py`, `web_app.py`, `core/record_removal.py`, `core/apps.py`, `core/context_processors.py`, `core/urls.py`, `static/record-removal.js`, `static/record-removal.css`, shared layouts and operational record templates. New master-bin partial: `templates/_master_record_bin.html`.

No additional schema migration for this feature; it reuses migration 0053's retained-record registry. `makemigrations --check` reports no changes. Existing SQLite upgrade backup/reuse behaviour remains unchanged.

Passed: 76 FlowLab/integration regressions; 72 E&I acceptance tests; 89 shared-database account/removal/recovery checks, including missing-CSRF denial, ordinary-staff denial, mixed-invalid-batch rollback, related-manager hiding, unchanged approved evidence, administrator restoration, and Chief restoration denial. JavaScript syntax and Git whitespace checks passed. No destructive test was run against the deployed database.

Stop the old executable before updating. Back up and retain the full existing data directory. This release is private and embeds the verified historical lab snapshot only for first-time installations; existing installations keep their current database.
