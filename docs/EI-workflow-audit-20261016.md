# Integrated laboratory review — 16 October 2026

## Delivered in this source update

- FlowLab environmental register uses the E&I monitoring layout: daily 08:00/12:00/17:00 slots, location/date filters, dark 7/30/90-day charts, recorder attribution and Excel-compatible CSV export. Add forms stay closed until requested. Existing daily records remain visible and unchanged; multiple time-slot readings use an additive table. Chief removal uses the retained master archive.
- FlowLab Analytics is now read-only, backed by actual jobs, uncertainty point results, CMC comparisons, laboratory assets, CAPA and audit/PT records. No fabricated PT scores or cross-unit averages are shown. Date filters and CSV exports are available.
- Chief Metrologist role is available. FlowLab's dedicated Personnel Registration page registers personnel in either lab, while their identities and personnel systems remain separate. Global User Management remains in Administrator Settings.
- Existing Supervisor registration requests now reach a Chief-accessible pending queue and can be completed once without sending Chief users to an admin-only screen. Chief-specific navigation is checked separately from Administrator navigation.
- Clickable breadcrumbs identify module, record and open Add form in both applications.
- E&I Administrator/Chief have full module permissions. At the user's express direction, technical review/approval is allowed by these roles without individual scope grants. This exception does not fabricate analyst competency or authorization records. Actual restricted analyst assignment still validates competence and current activity authorization.
- E&I job submission now requires an independent Supervisor review before independent Chief/Admin approval. A retained `JobReview` stores the reviewer, timestamp, comment and proposed assignee for each submission. No assignment or commencement is permitted after review alone. Save & Assign no longer bypasses review. Existing historical approvals are preserved.
- Technical record submission notifies reviewers; completed technical review notifies Chief/Admin approvers. Actual author, reviewer and approver remain separate. The authority basis is retained in the workflow audit.
- Approved/reviewed legacy logs cannot be silently edited; an existing approved signed result cannot be replaced. Returned legacy logs re-enter review after correction. Native and API gates are aligned.
- API role checks are enforced; direct permanent deletion through generic record APIs is disabled. Staff cannot retrieve other people's private personnel API records.
- Independent-signature and controlled-revision protections remain. Role-only authority does not permit self-assessment, self-authorization or approval of one's own technical record. A job's reviewer cannot also give its final approval.

## Workflow trace and remaining gaps

| Area | Current initiation → review → approval | Gap / decision still needed |
| --- | --- | --- |
| Jobs and personnel assignment | Originator drafts and uploads required lab documents → Supervisor reviews proposed eligible assignee → Chief/Admin independently approves → assigned analyst commences | Operational job review and approval are now separate. Existing pre-upgrade approvals retain their original one-stage history; they are not rewritten. |
| Technical calibration / repair / assessment records | Actual analyst saves draft → independent authorized Supervisor reviews → Chief/Admin approves → controlled amendment for corrections | Some audit-history panels still show structured/raw snapshots rather than a comparison of revisions. |
| Personnel qualifications and training | Supporting evidence uploaded → independent records officer/Supervisor verifies → Chief/Admin issues scope/activity authorization | Verification and technical authorization are separate records, not one unified personnel onboarding progress screen. A mandatory evidence/competency checklist before issuing every non-role-based authorization should be defined; assignment currently checks competence independently. |
| Competency and authorization | Designated assessor records scope/method assessment → Chief/Admin issues/revises/suspends/revokes authorization | No assessment of one's own competency or authorization is permitted. A reassessment/renewal generates history, but there is no single guided renewal wizard. |
| Lab equipment and calibration programme | Calibration/maintenance evidence uploaded → independent Chief/Admin approves → programme dates update | A separately persisted Supervisor-review stage before equipment approval is not yet implemented. |
| CAPA / NCR | Owner records cause, actions, effectiveness and close-out evidence → independent Chief/Admin decides closure | CAPA still has a combined review/closure decision; a separate Supervisor review before Chief closure needs an additional workflow stage. |
| Procedures / scope templates | Assigned author prepares/submits → Chief/Admin approves controlled version | A separately retained Supervisor-review stage is not implemented for every document/template type. Work Instruction and Forms registers remain visibly marked pending. |
| Environmental monitoring | Actual recorder retains a reading → monitoring/trend register | This is a monitoring log, not an approval workflow. Define required limits and excursion/escalation rules before adding automated conformity decisions. No arbitrary environmental acceptance limits have been invented. |
| Shared administration / recovery | Administrator manages linked accounts and restores retained records; Chief removes records recoverably | Shared Administrator appointments remain global account administration, not ordinary E&I personnel registration. Chief cannot appoint a shared Administrator through the limited cross-lab registration form. |

These remaining items are functional workflow/design gaps, not evidence of HTTP failures. They are not represented as completed features or accreditation certification.

## Database preservation and deployment

- Source remains integrated PostgreSQL. The Windows executable uses its embedded SQLite seed installed into the user's persistent local data directory.
- New Django migrations: `0054_chief_metrologist`, `0055_ei_workflow_authority`, `0056_job_supervisor_review`. FlowLab environmental schema is additive.
- Backup: `data/migration_backups/ei_modernization_20261016_063415`.
- Preservation checks confirmed existing source personnel, jobs, calibration logs, qualification evidence, competency, authorization and laboratory assets were unchanged by migration. FlowLab jobs, uncertainty calculations, accounts, assets and prior environmental readings were checked separately.
- PostgreSQL-to-SQLite deployment snapshot: `release/SQLite-Snapshot-20261016-Review-R1`. It is private and includes retained application data and attachments; do not publish the snapshot or executable as a public download.
- An updated executable must not overwrite an existing installation's data directory. Existing installations keep their SQLite records and receive additive migrations on startup. PostgreSQL and an already deployed SQLite copy do not synchronize automatically.

## Verification scope

The automated checks exercise valid navigation, permissions, registration, assignment, calculation, review, approval, privacy, retention/recovery, document exports and portable startup. Deliberately invalid/unauthorized requests correctly return validation errors or access denials; these are not server failures. No finite test run proves every possible input and every future deployment environment is error-free.

Final test counts, portable verification and executable location are recorded in the release verification report after the build is tested.
