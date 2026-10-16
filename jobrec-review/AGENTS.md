## Project: JobRec — Django 6.0 + Tailwind CDN + Alpine.js + Chart.js

### Tech Stack
- Django 6.0 system install (`python3`, no venv, `--break-system-packages`), `jobrec.settings`
- Tailwind CSS via CDN with `darkMode: 'class'` in config script block, persisted in localStorage via Alpine.js
- Font Awesome via CDN for icons
- DRF API with TokenAuthentication + SessionAuthentication, all endpoints require `IsAuthenticated`
- Login page: gradient background, elevated card (`rounded-3xl shadow-xl p-10`), unicode icons in placeholders (`\uf007` / `\uf023`), inputs match button width (`w-full px-5 py-3`)
- `strip_page` template filter in `permission_tags.py` strips `page`, `incoming_page`, `outgoing_page` from QueryDict
- Settings are env-driven (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_DB_PATH`, `DJANGO_STATIC_ROOT`, `DJANGO_MEDIA_ROOT`), loaded from a `.env` file in the project root with no third-party dependency

### Completed

#### Phase 1 (Critical — 7/7)
- profile edit: removed duplicate location, added name field, removed silent username change, unused variable cleanup
- sidebar: `lg:ml-64` overlap fix in base.html
- jobs/create Alpine.js: `el.__x` → `Alpine.$data` v3 API
- QR card: FontAwesome CDN added
- pagination: `|strip_page` filter on all 9 list templates to fix duplicate params
- waybills/list: duplicate Alpine.js script removed
- ProfileForm dark mode classes on name widget

#### Phase 2 (High — 12/13)
- dashboard: status-filtered links (`?status=pending_review`/`?status=pending_approval`)
- sidebar: permission-gated items (Equipment, Pre-Cal, Environment, Calibration Logs)
- settings: role/scope deletion changed from GET to POST with CSRF + confirmation
- settings: form error display on all tabs
- personnel detail RBAC: `is_superuser` → `manage_personnel`
- calibration detail: confirmation dialogs on review/approve/reject
- pre-cal detail: "Create Calibration Log" CTA when status is cal_pending
- dark mode: 24 filter inputs in list templates + settings addresses
- environment graph: JS dark mode fix
- disable-submit: global script in base.html
- personnel/create: extra `</div>` removed
- QR: always-visible section + "Printable QR Card" button
- Deferred: dashboard role-scoped metrics (#8)

#### Phase 3 (Polish — 19 items)
- **Messages**: auto-dismiss (5s fade with 500ms transition) + close button (`onclick="this.parentElement.remove()"`)
- **Logo**: removed dark-mode toggle click handler
- **Logout**: confirmation dialog on both sidebar and mobile nav
- **Back links**: added to client, waybill incoming/outgoing, job detail pages
- **Client detail**: back-to-list link added
- **Review/Approve context**: readings table, as-found/as-left, notes, and env conditions shown in confirmation dialogs
- **Notifications**: "Mark All as Read" button with confirmation, plus new `notification_mark_all_read` view + URL
- **Profile**: role badge displayed next to name (`person.role.name`)
- **Repair complete**: Cancel links to `pre_calibration_list` instead of HTTP_REFERER
- **Waybill create**: dark mode error colors (`dark:text-red-400`), remove item confirmation
- **Calibration create**: loading spinner on unit selector during fetch, error handling on fetch failure
- **Result counts**: "Showing X-Y of Z" added to all 9 paginated list templates
- **Filters**: notifications search uses proper name filter (was using message, fixed)

#### Phase 4 (Accessibility)
- **Autocomplete**: added `autocomplete` attributes to LoginForm, CustomPasswordChangeForm, ProfileForm, ClientForm, PersonnelForm, CompanyAddressForm, CompanyProfileForm
- **Label association**: login form labels now use `for="id_username"`/`for="id_password"`
- **Aria-labels**: sidebar `<nav>` labeled "Main navigation"; all icon-only buttons have `aria-label` (dark mode toggle, profile, password, logout, sidebar close, hamburger menu)
- **Focus indicators**: global `a:focus-visible`/`button:focus-visible` CSS for keyboard navigation; `focus:ring-2` on sidebar links, nav buttons, and action icons

#### Production Readiness
- `jobrec/settings.py`: env-driven config (see Tech Stack), no hardcoded ngrok hosts, secure-cookie flags default to on when `DJANGO_DEBUG=0`
- `requirements.txt` trimmed: removed unused `crispy_forms`/`crispy_tailwind` and `psycopg2-binary`
- `STATIC_ROOT` + `collectstatic` for PythonAnywhere static-file mapping
- Job notifications: `new_job_created`/`job_updated` types notify managers (`approve_calibration` perm) and `assigned_to` personnel on job create/edit (migration `0021`)
- Client edit/delete views + templates; expanded 4in×6in QR card

#### Primaries & Job cleanup (latest)
- **Primaries log** (`core` app): new `Primary` model (company reference/standards) with `name`, `serial_no`, `manufacturer`, `model_no`, `scope`, `purchase_date`, `calibration_frequency`, `last_calibrated`, `calibration_due_date`, `status` (`active`/`pending_maintenance`/`inactive`), `is_due`/`due_in_days` helpers. Full CRUD (`/primaries/`, gated: list/detail by `view_equipment`, create/edit/delete by `approve_calibration`) + sidebar link.
- **Due reminders**: `create_reminders` management command now flags primaries due within 90 days (3 months advance); overdue/due-today primaries are set to `pending_maintenance` and managers are notified via `primary_due_reminder` notifications (migration `0023`).
- **Dashboard**: "Repair Due" card replaced with **Pending Maintenance** (counts due/maintenance primaries); added **Awaiting Pickup** count on the Pending Approval card (equipment with calibration completed but not dispatched).
- **CalibrationLog status**: `pending_approval` → `pending_pickup` → **back to `pending_approval`** ("Pending Approval") across statuses, views/gates, templates, API, dashboard card + `?status=pending_approval` filter (final state, migration `0031` data-flip + AlterField).
- **Purchase Order**: `Job.payment_order_number` → `purchase_order_number` (field rename + all templates/API/admin/views/messages).
- **Removed** from `Job`: `currency` and `job_amount` (model, form, admin, API, list/create/detail templates).

### Blocked
- Phase 2 deferred (#8): dashboard role-scoped metrics — complex redesign, separate effort
- No further phases remain

### OCR
JobRec ships **two OCR backends** selected by env `OCR_PROVIDER` (default `auto`);
both produce the same normalised output so `core/ocr_parser.py` works unchanged.

- **`paddle`** — the existing `ocr_service/` FastAPI microservice (`app.py`, PaddleOCR),
  used as-is on a host that can run an always-on service (local `docker compose`,
  VPS, Cloud). Called by `core/ocr_client.py` over HTTP (`/ocr/`, `/health/`).
- **`rapid`** — in-process RapidOCR (`onnxruntime`): PaddleOCR's own PP-OCR models
  exported to ONNX (~80 MB, pure pip wheels). **This is what runs on the
  PythonAnywhere free tier** (no second service, no `libGL`, <512 MB RAM), via
  `core/ocr_engine.py`.
- **`mock`** — graceful no-crash fallback (empty text) when neither is usable.

`auto` order: reach the paddle microservice → RapidOCR in-process → mock.

Real use is **incoming-waybill equipment extraction**: the user uploads the waybill
document (create page, file_upload field, or a saved waybill's file); the engine OCRs
it and `core/ocr_parser.py` extracts structured items (`equipment_description`,
`quantity`, `serial_no`, `model_no`, `manufacturer`, `range_field`) — one per serial,
matching the `WaybillItem` model. These items feed the downstream chain
(pre-calibration → calibration logs, which are already prefilled from `waybill_item`).

Endpoints:
- `GET  /ocr/health/`                              → `{ocr_available, provider}` (drives whether the server engine is used)
- `POST /ocr/parse-text/`                          → parse already-OCRed text → `{items}` (used by browser-side OCR)
- `POST /ocr/upload/`                              → scan an in-form file (used by the create-page autofill when a server engine is available)
- `GET  /ocr/scan/<pk>/`                           → scan a CalibrationLog's certificate (via engine)
- `POST /waybills/<pk>/ocr/`                        → scan a saved waybill, return parsed items (no DB write)
- `POST /waybills/<pk>/ocr/rescan/`                → scan a saved waybill and create missing `WaybillItem`s (dedupe by serial #; needs a server engine)

UI:
- Incoming waybill **create** page: a "Scan & Auto-fill" button is shown to anyone with
  `create_waybills`. If a server OCR engine is available (`/ocr/health/`), it POSTs the
  file to `/ocr/upload/`; **otherwise it runs OCR in the browser** (lazy loads
  `tesseract.js` from a CDN, recognizes the file, then POSTs the extracted text to
  `/ocr/parse-text/`). Both paths parse server-side and populate the equipment-item
  blocks via the existing `addItemBlock()` JS. On PythonAnywhere this means **no OCR
  packages installed on the server** — OCR runs in the user's browser.
- Incoming waybill **detail** page: a "Re-scan Document" button (when a file is attached,
  the user can edit waybills, and a server engine is available) creates the missing
  `WaybillItem`s. Hidden on the free tier (no server engine).

Run locally (any waybill image/PDF):
- Microservice: `cd ocr_service && uvicorn app:app --port 8000`, set
  `OCR_SERVICE_URL=http://127.0.0.1:8000 OCR_PROVIDER=paddle` (or `auto`).
- In-process: install `rapidocr-onnxruntime` + `opencv-python-headless` into the env and
  run with `OCR_PROVIDER=rapid` (or `auto` with the microservice down).
- Browser OCR (no server engine): just use `OCR_PROVIDER=auto` (or leave unset) and the
  create-page button falls back to tesseract.js in the browser — handy for a tight
  PythonAnywhere free-tier quota.

PythonAnywhere free tier:
- **No OCR packages required on the server.** Leave `OCR_PROVIDER` unset (or `auto`);
  `/ocr/health/` returns `ocr_available:false`, and the create-page Scan button runs
  tesseract.js in-browser + parses text server-side. Only `pip install -r requirements.txt`
  is needed (plus `requirements-pa.txt` is *optional* — only if you want the server-side
  RapidOCR engine, which is ~190 MB and may exceed a tight free-tier quota).
- Install order: `pip install -r requirements.txt`; optionally
  `pip install --no-deps rapidocr-onnxruntime && pip install -r requirements-pa.txt
  && pip uninstall -y opencv-python` (see the file header).
- `create_reminders` scheduled task and collectstatic are unaffected by OCR.

### Key Files
- `core/views.py`: notification_mark_all_read, job create/edit notifications, ClientUpdateView/ClientDeleteView, OCR endpoints (`ocr_health`, `ocr_parse_text`, `ocr_scan_upload`, `waybill_ocr_extract`, `waybill_ocr_rescan`), Primaries CRUD, `create_reminders` wiring
- `core/urls.py`: notification_mark_all_read, client_update/client_delete URLs, OCR routes, primaries routes
- `core/ocr_engine.py`: provider abstraction (paddle / rapid / mock / auto)
- `core/ocr_client.py`: HTTP client to the PaddleOCR microservice (unchanged)
- `core/ocr_parser.py`: waybill OCR -> structured `WaybillItem` fields (server-side parsing for both server-OCR results and browser text)
- `core/templates/core/waybills/incoming/create.html`: Scan & Auto-fill (server OCR, browser tesseract.js fallback) + JS
- `core/models.py`: `Primary` model, `Notification` types, `CalibrationLog.pending_approval`, `Job.purchase_order_number`
- `core/forms.py`: `JobForm`/`PrimaryForm`/`CalibrationLogForm`, autocomplete attrs
- `core/admin.py`: `PrimaryAdmin`, `JobAdmin`
- `core/management/commands/create_reminders.py`: extended primary reminders
- `core/templates/core/base.html`: logo click removed, logout confirmations, message auto-dismiss + close
- `core/templates/core/calibration_logs/review_confirm.html`: readings + notes context
- `core/templates/core/calibration_logs/approve_confirm.html`: readings + notes context
- `core/templates/core/notifications/list.html`: Mark All as Read button
- `core/templates/core/profile/profile.html`: role badge
- `core/templates/core/waybills/incoming/create.html`: Scan & Auto-fill button + JS
- `core/templates/core/waybills/incoming/detail.html`: Re-scan Document button
- `ocr_service/app.py`: PaddleOCR FastAPI microservice (used on better hosts)
- `requirements.txt` + `requirements-pa.txt`: app deps; RapidOCR + headless cv2 for PA free tier
- `jobrec/settings.py`: env-driven production config (`OCR_PROVIDER`, `OCR_SERVICE_URL`, …)

### Server
- Dev: `python3 manage.py runserver 0.0.0.0:8000`
- Dev logs: `/tmp/django.log`
- Database: SQLite (env-overridable via `DJANGO_DB_PATH`)

### Production (PythonAnywhere free tier) — deployment checklist
1. **Create a virtualenv** on PythonAnywhere, then:
   ```
   pip install -r requirements.txt
   pip install -r requirements-pa.txt   # RapidOCR (in-process, no libGL)
   ```
   > Use `pip install --no-deps rapidocr-onnxruntime && pip install -r requirements-pa.txt`
   > if `opencv-python` (needs `libGL`, unavailable on PA) is pulled in; then
   > `pip uninstall -y opencv-python`.
2. **Set environment variables**: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`,
   `DJANGO_ALLOWED_HOSTS=<you>.pythonanywhere.com`, `DJANGO_CSRF_TRUSTED_ORIGINS`,
   `DJANGO_SECURE_COOKIES=1`, and **`OCR_PROVIDER=rapid`** (forces the in-process
   RapidOCR engine — the PaddleOCR microservice cannot run on the free tier).
3. **Migrate + static**: `python manage.py migrate && python manage.py collectstatic --noinput`.
4. **WSGI**: point the WSGI file at `jobrec.settings` (`from jobrec.wsgi import application`).
5. **Static/media mapping**: `/static/`→`…/static`, `/media/`→`…/media`.
6. **Optional scheduled task** (daily): `python manage.py create_reminders`.
7. Not needed: OCR microservice, Postgres (SQLite only). DRF API is kept but the
   free tier is too constrained to host the OCR microservice — use the `rapid` provider.

## Follow-up (latest session)

- **Job status auto-reconciliation**: `Job.reconcile_status()` derives status from
  its incoming-waybill equipment items and is called after every item/status transition
  (pre-cal create, calibration-log create/update, review, approve, pre-cal review
  repair/dispatch, repair_complete). Progression: waybill captured → `pre_calibration_pending`
  (set on job creation when an incoming waybill is attached); pre-cal done for all →
  `calibration_pending`; cal-log created → `review_pending`; approve (cert) all-terminal →
  `completed`; all dispatched → `dispatched`; any `repair_due` (until resolved) → `repair_due`.
  It never regresses a `completed`/`dispatched` job. The PO/invoice guard on
  `JobForm.clean` still applies to manual status edits.
- **Calibration-log reference standard**: new `CalibrationLog.primary_equipment` FK →
  `Primary` (migration `0024`), rendered as a dropdown on the create/edit page filtered by
  the job's `scope`. The job's scope is also pre-selected on the log's scope picker.
- **Pre-cal list**: surfaces "Pending Pre-Calibration Tasks" — incoming-waybill items in
  `pre_cal_pending` (no pre-cal log yet, or awaiting review) — at the top of the page.
- **OCR on PA**: browser `tesseract.js` now renders PDF waybills to canvas (via `pdfjs-dist`
  ESM from jsdelivr) before recognizing, so scanned/PDF documents work without a server OCR
  engine. Word-level bounding boxes are sent to `/ocr/parse-text/` for accurate column parsing.

## Follow-up (alignment/enhancement plan — implemented)

Per-equipment scope re-architecture, outgoing-waybill pluralization, auto-populate, client
autofill, editable export filename, HTML certificates, environment conformity, and the
uncertainty engine. Migrations `0025`–`0029`:

- **Scope lives per-equipment, NOT on Job.** `Job.scope` and `Job.outgoing_waybill` removed;
  `Job.incoming_waybill` kept. `PreCalibrationLog.scope` and `WaybillItem.scope` FKs added;
  pre-cal `form_valid` mirrors its scope back onto the `WaybillItem`. `CalibrationLog.scope`
  converted M2M → single FK (data preserved — first M2M scope copied by migration `0025`).
  Primary dropdown on the cal log is filtered by the equipment's scope.
- **Outgoing waybills are plural** via `Waybill.job` FK (related_name `waybills`). The pre-cal
  `dispatch` decision creates the outgoing waybill with `job=` and copies the item (incl. scope);
  `Job.outgoing_waybill_no` (API) built from `obj.waybills.filter(waybill_type='outgoing')`.
  Job detail lists all outgoing waybills + "New Outgoing Waybill" `?job=` link;
  `OutgoingWaybillCreateView` accepts `?job=` and has a Job select.
- **Units-by-scope dropdown fix**: root cause was **zero `Unit` rows in the DB**, not JS.
  Migration `0026_seed_units` seeds units per scope (General/Pressure/Temperature), idempotent.
  JS rewritten to read `#id_scope` directly; URL built with `replace(/\/0\/$/, ...)` (multi-digit
  scope-safe). `calibration_logs/create.html` shows a single scope `Select`.
- **Client details autofill** (G8): `client_lookup` AJAX view+URL (`/api/client-lookup/?name=`);
  jobs/create has a client datalist + auto-populated client-details panel. Job create pre-fills
  from `?client=<name>` (client detail "New Job" link) and `?incoming=<id>` (incoming waybill
  detail "Create Job" link). Job detail shows full client details.
- **Auto-populate**: environment create auto-suggests time from the latest record (else nearest
  of 08/12/17); outgoing waybills from job; pre-cal scope inherited from waybill item; cal-log
  fields prefilled from pre-cal/waybill item.
- **Editable export filename** (G7): `environment_export` accepts `?filename=`, sanitized
  (path separators stripped, `.xlsx` forced); filename input added to the env list export form.
- **HTML certificates** (G3): `CompanyProfile.certificate_format` (placeholders `{year}`, `{seq}`,
  default `CERT-{year}-{seq:04d}`, editable in Settings) + `CalibrationLog.certificate_no`
  (auto-assigned on first certificate view via `build_certificate_no()`). New
  `calibration_certificate` view + `core/calibration_logs/certificate.html` (printable; company
  header/logo, addresses, readings, as-found/as-left, result, signatories, footer). Manual
  "Generate Certificate" button on the approved log detail page; `/calibration-logs/<pk>/certificate/`.
- **Environment conformity** (G6): `Primary.environment_conforms(temp, humidity)` compares the
  log's env against the primary's operating envelope; shown on cal-log detail (per-variable
  badges + overall verdict) and on the certificate. Operating-condition fields on Primary +
  create/edit form.
- **Uncertainty engine** (G2): `Primary.standard_uncertainty` (u_std %), `coverage_factor` (k,
  default 2), `tolerance` (%), `uncertainty_equation` (default `k * sqrt(u_std**2 + error_pct_max**2)`).
  `core/uncertainty.py` is an **AST-whitelist evaluator** (numbers, `+ - * / ** %`, `sqrt()`,
  variables `k`, `u_std`, `error_pct_max`, `tolerance`; rejects attribute/calls/imports).
  Auto-runs on CalibrationLog save and again after readings are saved (`_save_readings`
  recomputes), storing `expanded_uncertainty` + `uncertainty_in_tolerance`; displayed on
  cal-log detail and certificate.
- **Pending-maintenance notification fix** (done earlier session): `get_users_with_perm` returns
  User objects (role holders + superusers); all 6 notification call sites use `recipient=mgr`.

## Follow-up (Entry & Dispatch page)

- **Entry & Dispatch Log** (`/waybills/entry-dispatch/`, name `entry_dispatch`): read-only
  aggregation page, one row per **incoming-waybill equipment item**, collecting the lifecycle
  from jobs, pre-cal, cal logs, and outgoing waybills. Columns: Equipment Description, Serial No.,
  Model No., Range, Owner/Client (`Job.client`), Date Received (incoming waybill `created_at`),
  Incoming Waybill No. (link), Date Calibrated (latest log), Date Returned (outgoing waybill
  `created_at`), Outgoing Waybill No. (matched by serial in the job's outgoing waybills via
  `linked_incoming_waybill`), Certificate No. (latest log; links to certificate page when approved),
  Service (`Calibration` / `Calibration + Repair` when a pre-cal review decision was `repair`;
  responsive badge — full text `hidden sm:inline`, short label on small screens), Remarks (pre-cal
  remarks + cal-log notes joined, truncated with tooltip), Initial (initials of the latest
  calibrator `Personnel.name`), Category/Scope (`WaybillItem.scope`, fallback cal-log scope).
  Supports `?q=` search (description/serial/model/incoming waybill no) + `?status=` filter,
  paginated 25 with "Showing X-Y of Z". Links from the Waybills page header and sidebar nav.
  View: `core/views.py::entry_dispatch_log` (batched job/cal-log/pre-cal/outgoing maps, no N+1);
  template: `core/templates/core/waybills/entry_dispatch.html`. No schema changes.

## Follow-up (Waybills nav + calibration-log approval notifications)

- **Sidebar**: "Waybills" link added (`view_waybills`-gated, icon `fa-truck-fast`; active state
  excludes the `entry-dispatch` path so the Entry & Dispatch link doesn't double-highlight).
- **Calibration-log approval notifications** — four stages, all via `core/notifications.py`
  (`notify_users` — deduped/null-guarded; `calibration_log_recipients` — `recorded_by` +
  `calibrated_by.user`):
  - Log created → `pending_review` to `get_users_with_perm('review_calibration')`.
  - Log reviewed → `pending_approval` to `get_users_with_perm('approve_calibration')`.
  - Log approved → `log_approved` to the technicians (creator + calibrator).
  - Log rejected → `log_rejected` to the technicians (reason included).
  Hooks in `CalibrationLogCreateView.form_valid`, `calibration_log_review/approve/reject` in
  `core/views.py`, and mirrored in `core/api/views.py::CalibrationLogViewSet`
  (`perform_create`/`review`/`approve`/`reject`). New `Notification` types (`pending_review`,
  `pending_approval`, `log_approved`, `log_rejected`) via migration `0030` (choices-only
  AlterField — Django 6 generates it). **Note**: actual role→permission mapping is data-driven
  (Settings page); here Lab Lead/Lab Supervisor/Manager all hold `approve_calibration`.
- **API bugfix**: `CalibrationLogSerializer`/`CalibrationLogWriteSerializer` referenced a
  nonexistent `remarks` field → renamed to `notes` (API create/update was broken with
  ImproperlyConfigured). The CalibrationLogViewSet is `FormParser`/`MultiPartParser`-only, so
  API actions must be sent form-encoded (JSON posts return 415).

## Follow-up (waybill create → back to job form)

- **Return-to-job-form flow**: the "Create" link for an Incoming Waybill on the job
  create/edit form now carries the partially-filled fields (`purchase_order_number`,
  `client`, `job_description`) in a `?next=` param (JS builds it from the live form,
  same-tab navigation, no more `target="_blank"`). `IncomingWaybillCreateView.get_success_url`
  validates `next` with `url_has_allowed_host_and_scheme` (open-redirect safe — external,
  `//`, and `javascript:` schemes fall back to the waybill detail page), then redirects back
  to the job form with `?incoming=<pk>` appended. `JobCreateView.get_initial`/
  `JobUpdateView.get_initial` prefill PO/client/description + the new waybill from query params.

PA deploy note: `pip cache purge` needed on PythonAnywhere; **do NOT install `requirements-pa.txt`**
on the free tier (server-side RapidOCR is unnecessary — browser tesseract.js handles OCR, and
the tier is at quota cap).

## Follow-up (job status rework, assignments, environment notifications, Jobs nav)

Migrations `0031` (cal-log rename data-flip + AlterField, job_status choices, notification
choices) — all three AlterFields combined in one migration with a `RunPython` data flip:

- **CalibrationLog status** (final): `pending_pickup` → **`pending_approval`** ("Pending Approval"),
  flipped from existing rows in migration `0031`. Updated: `views.py` (dashboard count
  `pending_approval_logs`, review/approve/reject guards), `api/views.py` (review/approve/reject),
  dashboard card (renamed "Pending Approval", `?status=pending_approval`), cal-log list/detail badges.
- **Job status rework**: new `Job.approval_pending` ("Approval Pending") status.
  `Job._item_stage()` maps each item to a stage by consulting its **latest calibration-log status**
  (`result_pending` + log `pending_review`/`rejected`/none → `review`; log `pending_approval` or
  `approved`-but-not-completed → `approval`; `cal_pending` → `calibration`; `repair_due` → `repair`;
  terminal → `terminal`). `Job.derive_status_from_items()` aggregates the furthest incomplete stage.
  `Job.reconcile_status()` **snaps** non-terminal jobs to the derived status (so a rejected log pulls
  a job back to `review_pending`) and **never regresses** `completed`/`dispatched` jobs
  (`_STATUS_RANK` removed). New `reconcile_status()` calls added to `calibration_log_review`,
  `calibration_log_reject`, and API review/approve/reject (approve reconciles even without a cert so
  the job shows `approval_pending` during close-out). `approval_pending` badge (cyan) in job
  detail/list/dashboard; `job_by_status` accepts `approval-pending`.
- **Job assignment moved to job detail**: `assigned_to` removed from `JobForm` and the
  `jobs/create.html` Alpine multi-select. Job detail now has a managed panel (`edit_jobs`-gated):
  assign from a personnel select (`POST /jobs/<pk>/assign/`) and per-assignee remove
  (`POST /jobs/<pk>/unassign/<personnel_id>/`), both via `views.py::job_assign`/`job_unassign`;
  assigning notifies the assignee (`new_job_created`). Existing M2M data preserved.
- **Environment notifications to all personnel** (`environment_reminder` type):
  `create_reminders` now notifies **every Personnel-linked user** when a slot's reminder is first
  created ("due today at HH:00"), and re-notifies at each slot time if still unrecorded
  ("still pending"), deduped per date+slot by message marker (idempotent — re-running sends
  nothing new). PythonAnywhere Tasks should run the command at **01:00, 08:05, 12:05, 17:05**.
- **Environment-recorded pop-up** (`environment_recorded` type): saving an environment record
  (web `EnvironmentCreateView.form_valid` or API `EnvironmentRecordViewSet.perform_create`)
  notifies all personnel **except the recorder**. A polling toast shows these in-app:
  `GET /notifications/popups/?after=<id>` (`views.py::notification_popups`, URL `notification_popups`)
  returns unread `environment_recorded` notifications with `pk > after`; `base.html` JS polls
  every 30 s (first poll seeds a per-user `localStorage` pointer so old ones never replay) and
  renders auto-dismissing toasts (click → `/notifications/<id>/read/` → environment list).
- **API bugfix**: `EnvironmentRecordSerializer` referenced nonexistent `humidity`/`notes` →
  `relative_humidity` (env-record API was broken with ImproperlyConfigured).
- **Jobs sidebar link**: new `view_jobs`-gated "Jobs" link (`fa-briefcase`) after Dashboard with a
  **pending-count badge** (`pending_job_count` from `core/context_processors.py`; counts
  pre-cal/calibration/review/approval/repair-due). Job detail action links are now permission-gated:
  Pre-Cal→`perform_pre_calibration`, Review Pre-Cal→`review_pre_calibration`, Create Log→
  `edit_calibration`, Mark Repaired→`repair_equipment`, New Outgoing→`create_waybills`,
  Edit/Delete→`edit_jobs`. Job list/detail were already visible to all logged-in users.

## Follow-up (inline certificate upload, per-lab environment, print chrome, waybill client info)

- **Inline certificate upload** (no full-form edit needed): `calibration_log_upload_certificate`
  view (`POST /calibration-logs/<pk>/upload-certificate/`, `edit_calibration`-gated) saves the
  uploaded file to `log.certificate` and — when the log is `approved` — sets the waybill item to
  `completed` and calls `job.reconcile_status()` (mirrors the old CalibrationLogUpdateView behavior).
  The `certificate` field was **removed from `CalibrationLogForm`** and the create template; the
  detail page has an inline upload/replace form (file input `name="certificate"`).
- **Certificate print chrome removed**: `base.html` hides the mobile top bar, sidebar overlay/aside,
  and toast container with `print:hidden`; `<main>` gets `print:overflow-visible print:ml-0`.
  `certificate.html` uses `@page { size: A4 portrait; margin: 0; }` (suppresses the browser's
  print header/footer chrome) with a `.certificate-page { padding: 10mm; }` rule to restore margins.
- **Per-lab environment records** (migration `0032`): `EnvironmentRecord`/`EnvironmentReminder` now
  carry a `location` FK (labs = `Location`, synced from `CompanyAddress`; currently `E&I Lab`,
  `Flow Lab`) with `unique_together = ['location','date','time']`. Web form (`location` required) and
  DRF API (`EnvironmentRecordSerializer.location` required) both record per lab; creating a record
  updates the per-lab reminder + notifies all personnel **except the recorder** with the lab named
  in the message and a `?location=` link. List page has a lab filter dropdown (filter + export),
  a Lab/Location column, lab badges on reminders, and the graph/data endpoints filter by location;
  the Excel export adds a "Lab / Location" column. `create_reminders` creates one reminder per slot
  per lab (NULL-location fallback) with lab-specific nudge markers (idempotent).
- **Waybill client info**: waybills have no client field — client comes from the linked `Job`
  (`Job.incoming_waybill` FK → `Job.client`). `WaybillListView` prefetches `incoming_jobs`
  (`select_related('client')`) for both the incoming set and (via `linked_incoming_waybill`) the
  outgoing set, so the list tables show a **Client** column with zero N+1 queries.
  `WaybillDetailView`/`OutgoingWaybillDetailView` pass the resolved job/client into context and both
  detail pages show a "Client / Equipment Owner" card (`-` when no job/client). Outgoing waybills
  created from a job get `job=` set so the job detail lists them.
- **API bugfixes** (latent `ImproperlyConfigured`/`AttributeError` on `GET /api/clients/` and
  `/api/waybills/`): `ClientSerializer` referenced nonexistent `contact_person`; `WaybillItemSerializer`
  referenced nonexistent `waybill_item_id` lookup and `latest_log_status` (now a real
  `WaybillItem.latest_log_status` property) with a `calibration_logs` id list replacing the broken
  hyperlink. `CalibrationLogViewSet.perform_create` now advances the waybill item to
  `result_pending` and reconciles the job, mirroring the web `CalibrationLogCreateView`.

## Follow-up (calibration-workflow overhaul — R1–R5, migration `0033`)

- **R1 — Run Another Calibration**: rejected logs show a "Run Another Calibration" button on the
  detail page (gated `edit_calibration`), linking to `calibration_log_create` prefilled with the
  same `waybill_item` (new round instead of re-editing the rejected log).
- **R2 — Units per scope, online-first + cached**: new `core/unit_catalog.py` provides
  `BUNDLED_CATALOG` (General Calibration / Pressure Calibration / Temperature Calibration),
  `_fetch_online()` (JSON via `settings.UNITS_CATALOG_URL`, 8 s timeout, graceful None on
  failure), `units_for_scope(scope, refresh=False)` (lazy-populate, upsert by `(symbol, scope)`),
  and `refresh_all_units()`. `units_by_scope` view lazy-populates and honours `?refresh=1`;
  management command `python manage.py fetch_units` refreshes all scopes (idempotent).
  When `UNITS_CATALOG_URL` is unset/unreachable the bundled catalog is used — "online, cached,
  populated" works offline too.
- **R3 — Editable per-scope table template**: `CalibrationType` gains `instrument_column_label`,
  `uut_column_label`, `error_column_label` (defaults "Instrument Reading"/"UUT Reading"/"Error").
  Settings→Scopes tab shows a Table Template column with inline edit forms (`edit_scope` POST in
  `settings_view`); the calibration-log create/detail/certificate/review/approve templates use the
  per-scope labels via a JS `SCOPE_LABELS` map + `applyScopeLabels()` (create) and template
  references elsewhere. The Settings scopes delete check no longer references the removed
  `Job.scope` (FieldError); it checks `CalibrationLog`/`PreCalibrationLog`/`WaybillItem`/`Unit`/
  `Personnel`.
- **R4 — Plain error, not %**: `CalibrationLogReading.error_percentage` renamed to `error`
  (DecimalField 12,4, null/blank; migration `0033` copies data). Error = `instrument_reading -
  uut_reading` computed client-side on create (Error column = Inst − UUT) and submitted in
  `readings_found_json`/`readings_left_json`. `compute_uncertainty` feeds `error_max` from `abs(r.error)`, with
  `error_pct_max` kept as a backward-compat alias so stored equations keep working; new
  equation default/help-text/placeholder use `error_max`.
- **R5 — Technician picks reviewer → reviewer reviews → QHSE approves**:
  - New `CalibrationLog.reviewer` FK→User (`related_name='assigned_calibration_logs'`, null/blank);
    new status `pending_qhse` ("Pending QHSE Approval"); new `Notification` types
    `pending_qhse`; `Job._item_stage` maps `pending_qhse` → `'approval'`.
  - Create page has a reviewer `Select` (queryset = `get_users_with_perm('review_calibration')`)
    + a canvas **technician signature pad**; `technician_signature` is a base64 PNG data URL stored
    in a TextField (submitted hidden on save). `CalibrationLogCreateView.form_valid` saves the
    signature and notifies the selected reviewer (fallback: all `review_calibration` users).
  - Reviewer-only gating: review requires `review_calibration` AND (`log.reviewer_id` unset OR
    equals the current user OR superuser). Review POST → `pending_approval`, notifies technicians
    (`calibration_log_recipients`) to upload the signed result.
  - `calibration_log_upload_certificate` on `pending_approval` → `pending_qhse` + notifies
    `get_users_with_perm('approve_calibration')`; on an already-`approved` log it completes the
    item + reconciles the job. Detail page shows the inline upload form for `pending_approval`.
  - `calibration_log_approve` (gated `pending_qhse`/`pending_approval`) requires the
    `approver_signature` base64 POST field (canvas pad on `approve_confirm.html`; validation +
    no-signature confirmation), sets `approved`/`approved_by`/`approver_signature`, completes the
    item when a certificate is present, reconciles the job. Reject allowed from
    `pending_review`/`pending_approval`/`pending_qhse`.
  - Certificate page renders both signatures in the signatories block; detail page shows the
    signatures section (img src = data URL). `CalibrationLogUpdateView` preserves
    reviewer/signature/error on save.
- **Dashboard**: the Pending Approval card count includes `pending_qhse` logs.
- **API** (`core/api/views.py` `CalibrationLogViewSet`): `perform_create` saves
  `recorded_by` + reviewer, advances item to `result_pending`, reconciles job, notifies the
  selected reviewer; new `upload_certificate` action (`pending_approval` → `pending_qhse`,
  approved+item → complete); `review` gated to the assigned reviewer; `approve` requires
  `approver_signature` and accepts `pending_qhse`/`pending_approval`; `reject` allows
  `pending_qhse`. Serializers expose `reviewer`, `reviewer_name`, signatures; reading serializer
  uses `error`; `CalibrationTypeSerializer` includes the three labels.
- **Admin**: `CalibrationTypeAdmin` shows the column labels; `CalibrationLogAdmin` makes the two
  signature fields read-only.
- **Smoke tests**: `/tmp/opencode/smoke_workflow.py` (23 checks: R1–R5, reviewer gating incl.
  assigned-to-other block + superuser bypass). Full suite: `smoke_lab_cert.py` 37,
  `smoke_jobs.py` 53, `smoke_api.py` 28, `smoke_workflow.py` 23 — all green with
  `manage.py check` clean.
- **Migrations**: `core.0033_remove_calibrationlogreading_error_percentage_and_more.py`
  (AddField `error` → RunPython copy → RemoveField `error_percentage`; AlterField statuses/
  reviewer/notification types). `python3 manage.py makemigrations --check --dry-run` → no changes.

## Follow-up (profile signatures, outgoing-waybill PO guard, back navigation — migration `0034`)

- **Profile-stored signatures**: `Personnel.signature` ImageField (`upload_to='signatures/'`,
  null/blank; migration `0034`) + `signature_url` property. Upload via Profile → Edit
  (`enctype=multipart`, current-signature preview); shown on the profile page with a warning +
  upload link when missing (`core/auth_utils.py::get_user_signature_url`). Canvas signature pads
  REMOVED from calibration-log create and approve pages — signatures are auto-populated:
  - Technician: `CalibrationLogCreateView.form_valid` stamps `technician_signature` from the
    creator's profile (API `perform_create` mirrors this).
  - Approver: `calibration_log_approve` no longer reads a POST field; it stamps the approver's
    profile signature and **blocks approval** ("No signature on your profile…") when missing.
    API `approve` returns 400 with the same message. Create/approve templates show a preview of
    "your signature" or a yellow warning linking to Profile → Edit.
- **Outgoing waybill — auto-picked incoming waybill + PO gate**:
  - New `OutgoingWaybillForm` (forms.py): `job` is now REQUIRED and must have a non-empty
    `purchase_order_number` (`clean_job` error otherwise). View uses it; job select is ordered
    newest-first with client select_related.
  - Create page auto-fills the Incoming Waybill No from the selected job (context `jobs_data`
    JSON map id→{incoming_no, po, client}; JS fills on change/load and triggers the existing
    item fetch). Server-side fallback in `form_valid`: if no incoming waybill was typed, links
    `job.incoming_waybill`. A red warning disables submit when the job has no PO; hint shows
    Client · PO.
  - Pre-cal review dispatch decision is guarded too: if the item's job has no PO, the review is
    rejected with an error message BEFORE any mutation (reviewer adds the PO on the job, then
    re-reviews).
- **Back navigation everywhere**: new partial `core/templates/core/partials/back_link.html`
  included at the top of ~47 content templates (lists → Dashboard; detail/create/edit/delete →
  their list; confirm/review pages → their detail via `{% url ... as back_href %}`).
  Hybrid behaviour: `history.back()` when the referrer is same-origin, else falls back to the
  logical-parent href. Skipped: dashboard (root), login, certificate/QR print pages.
- **Latent template bug fixed**: `{{ x.get_full_name|default:x.username }}` raises
  VariableDoesNotExist (500) when `x` is None because filter ARGUMENTS don't swallow failed
  lookups. Replaced with safe `{% firstof x.get_full_name x.username "-" %}` in pre-cal
  detail (inspected_by, reviewed_by) and pre-cal review (inspected_by).
- **Verification**: `/tmp/opencode/verify_outgoing_back.py` (6 checks: create-page render,
  no-PO form block, dispatch blocked without PO with nothing mutated, auto-link fallback,
  dispatch succeeds after PO, back links render) + `/tmp/opencode/sweep_pages.py` render sweep
  over 30 URLs — all green; `manage.py check` clean; migrations clean.

## Follow-up (approved-log lock, certificate signature gate, admin dummy signature)

- **Approved logs are locked**: `CalibrationLogUpdateView.dispatch` redirects with
  "Approved calibration logs are locked…" when `log.status == 'approved'` (GET and POST both
  blocked, nothing mutates). Detail page Edit button now gated to
  `{% if log.status != 'approved' and user|has_perm_tag:'edit_calibration' %}` (was:
  draft/approved/superuser). API: `CalibrationLogViewSet.perform_update` raises DRF
  `ValidationError` (400) on approved logs. Reject/review/approve status guards already
  excluded `approved`.
- **Certificate signatures only after QHSE approval**: `certificate.html` renders the
  technician/approver signature `<img>`s only when `log.status == 'approved'`; otherwise an
  italic "Signature pending approval" placeholder shows in the signatories block.
- **Dummy signature for admins**: new management command
  `python manage.py create_dummy_signature` (`--username`, `--force`) generates a
  handwritten-style PNG (Pillow: rotated text + underline flourish) and attaches it to the
  Personnel profile of superusers — creating the profile if missing. Run once on a fresh
  deployment so admins can approve without uploading a real signature first.
- **Verification**: `/tmp/opencode/verify_lock.py` (9 checks: dummy signature attach,
  profile-stamped technician sig on create, cert placeholders before approval / imgs after,
  edit reachable pre-approval, web GET+POST edit blocked post-approval with no mutation,
  Edit button hidden, API PATCH → 400) — all green; `manage.py check` clean; migrations clean.

## Implemented (this session — migration `0035`): reviewer-only signatures, procedures, cert numbering, 2-page certificate

### 1. Reviewer-only signatures
- `CalibrationLog.reviewer_signature` (TextField) added; `technician_signature` and
  `approver_signature` fields REMOVED entirely (migration `0035` RemoveFields).
- Review is the signing moment: `calibration_log_review` stamps `reviewer_signature` from the
  reviewer's profile (`get_user_signature_url`) and BLOCKS ("No signature on your profile…",
  redirect to profile_edit) when missing — mirrored in API `review` (400). Approval no longer
  requires/stamps any signature (web + API); it sets `approved_by/at` and defaults
  `date_of_issue` to the approval date. Create/API create stop stamping technician signatures.
- Certificate signatory block shows ONLY the reviewer: name via `{% firstof %}`, signature img
  gated on `log.status == 'approved'`, italic "Signature pending approval" placeholder otherwise.
  Detail page mirrors this. Signature panel removed from create.html; approve_confirm.html has
  no signature UI. review_confirm.html shows the reviewer's own profile signature with a warning
  when missing.

### 2. Calibration Procedures
- New model `CalibrationProcedure`: scope FK (related_name='procedures'), title,
  manual_reference, instructions (one step/line), test_points_percent JSON list,
  tolerance_pct Decimal null, status draft/pending_approval/active/rejected, assigned_to
  FK→Personnel, created_by/approved_by FK→User, review_notes, version, timestamps.
- Workflow: supervisor assigns (`/procedures/assign/`, `approve_calibration` gate) → draft +
  `procedure_assigned` notification to the tech → assigned tech edits while draft/rejected
  (`procedure_edit`; Save Draft or Save & Submit) → submit → `pending_approval` +
  `procedure_submitted` to approvers → supervisor approves/rejects on the detail page
  (reject notes → back to draft). Gates enforced in views; non-assigned users blocked.
- Pages: `/procedures/` list (q/scope/status filters + pagination), detail, assign, edit;
  POST `/procedures/<pk>/submit/`; approve/reject POSTed to the detail view. Sidebar link
  "Procedures" (fa-book-open). New Notification types procedure_assigned/submitted/approved/
  rejected. Admin registered.
- Cal-log create integration: `GET /api/procedure-for-scope/<scope_id>/` (JSON:
  title/manual_reference/instructions/test_points_percent/tolerance_pct). On scope select the
  page shows an instructions panel with an "Apply Test Points" button; test points are resolved
  client-side across the parsed range (JS regex parser mirrors server logic). Specs block
  (`specs_json` hidden field → `CalibrationLogSpec` rows) for instrument-type key/value specs.

### 3. Certificate numbering + abbreviations
- `CalibrationLog.build_certificate_no()` v2: template chain scope.certificate_format →
  CompanyProfile.certificate_format → default `{company_abbr}/{client_abbr}/{scope_abbr}/{seq:04d}`;
  placeholders {company_abbr} {client_abbr} {scope_abbr} {seq} {seq:04d} {year}. Abbreviations:
  scopes REQUIRED manual entry (case-insensitive unique; validated in CalibrationTypeForm),
  seeded GCAL/PCAL/TCAL by migration; company/client optional manual entry, blank falls back
  to a derived code at render time (initials for ≥3 words, else first letters padded).
- `assign_certificate_no()`: called on FIRST certificate view inside a transaction
  (`select_for_update`); sets `cert_seq` = MAX(cert_seq)+1 over logs with the same
  equipment_owner+scope (separate series per client+scope) and stores the historical string.
- Settings Scopes tab: abbreviation column (required), per-scope Cert No. Template override and
  validity_months inline-edit columns. Company tab: abbreviation + accreditation_statement +
  narrative_template (+ traceability_body/compliance_standard/software placeholders).

### 4. Two-page certificate redesign (per EATL schema)
- Page 1: header (logo/company/addresses + CERTIFICATE OF CALIBRATION + cert no + Page x/y);
  Customer / Calibrating Laboratory blocks; equipment block incl. asset_id, procedure manual
  reference, location, date received (waybill created_at), last certificate no (latest prior
  approved log for the same serial); Instrument Specifications table (CalibrationLogSpec);
  Environmental Conditions table with tolerances + supply voltage/frequency rows; Traceability
  table (standards M2M: description/serial/cert no/cal date/cal due); narrative paragraph
  resolved from Settings template placeholders ({uuc_description} {standard_used}
  {standard_cert_no} {traceability_body} {compliance_standard} {software} {procedure_manual});
  accreditation statement; signatory (reviewer only) + calibrated-by/date-of-issue/result/
  calibration-due grid.
- Page 2 (page-break-after): repeated compact header strip; measurement results table (per-scope
  labels); As Found / As Left summaries; ISO GUM uncertainty statement (U%, k, 95%); notes;
  footer. `log.calibration_due` property = calibrated_at_date + scope.validity_months
  (month arithmetic clamped to month-end).

### 5. Other changes in migration `0035`
- `CalibrationLog.primary_equipment` FK → **M2M `standards`** (RunPython copies old values);
  all references updated (views conformity uses `log.primary` = standards.first(), uncertainty
  feeds off the first standard, admin autocomplete_fields='standards', API serializers expose
  standards). New fields: asset_id, date_of_issue, temp/rh tolerance, supply voltage/frequency
  ± tolerances. New models CalibrationProcedure + CalibrationLogSpec. Client/CompanyProfile
  abbreviation + certificate text fields. Primary.certificate_no (own cal cert number).
- Dashboard: "Awaiting pickup" sub-label + context var removed.

### Verification
- Smoke suite `/tmp/opencode/smoke_final.py` — **47 checks green**: review-time stamping +
  no-signature block (status unchanged), cert reviewer-only before/after approval, composite
  numbering EATL/ALP/PCAL/NNNN with sequence increment per client+scope + separate series +
  initials fallback, full procedure lifecycle (assign→edit→submit→reject→re-edit→resubmit→approve)
  with permission gates, procedure JSON endpoint + parse_range/test_point_values ('0–10 bar',
  negatives), dashboard cleanup, create-page render with new fields. 28-URL render sweep OK;
  `manage.py check` clean; `makemigrations --check` clean.
## Follow-up (per-scope custom certificate templates — migration `0036` + fixes)

- **Custom cert HTML per scope**: `CalibrationType.certificate_template` (TextField, blank;
  migration `0036`). When non-blank, the `calibration_certificate` view compiles it with the
  project Django engine (`engines['django'].from_string`) and renders it with the EXACT same
  context as the default certificate.html (log/company/addresses/readings/conformity/standards/
  specs/narrative/date_received/previous_log/total_pages) — so a scope can have a completely
  different certificate layout. Blank = default two-page certificate.
- **Editor page** `/settings/scopes/<pk>/certificate-template/` (`scope_cert_template`,
  `approve_calibration`-gated): big monospace textarea; Save validates by compiling first
  (TemplateSyntaxError shown inline, field untouched on error); "Use Default Layout" clears
  the field (confirm dialog); Preview link to the latest log in that scope that is past review
  (hidden until one exists); reference lists of available variables + starter snippet
  (uses `{% verbatim %}` — note `{{ '{{' }}` idiom BREAKS: the lexer cuts at inner `}}`).
  Settings → Scopes tab gained a "Cert Layout" column (Custom/Default badge linking to the
  editor); edit-row colspan bumped to 7.
- **`_save_specs` AttributeError fix**: `CalibrationLogCreateView.form_valid` called
  `self._save_specs()` but only the UpdateView had it — added `_save_specs` to the create view.
  Also removed a stray approved/certificate block + undefined `return response` from the
  update view's `_save_specs` (NameError landmine).
- **`+`-for-spaces encoding fix (return-to-job-form flow)**: root cause was JS
  `URLSearchParams.toString()` encoding spaces as `+`, combined with views.py re-quoting the
  whole URL string (`unquote`→`quote(safe="/?&=")`) which froze `+` into `%2B` AND left raw
  `&`/`=` inside values (e.g. job_description "R&D work" corrupted into separate params).
  Fix: jobs/create.html builds qs via per-pair `encodeURIComponent`; `get_success_url` now
  parses `next` with `partition('?')` + `QueryDict` + `urlencode()` (no unquote/quote round
  trip; legacy `+` links even recover to spaces). DB scan found zero corrupted rows.
## Follow-up (certificate-number re-issue)

- **Why numbers "don't update" after Settings changes**: `certificate_no` is assigned ONCE
  (first certificate view) and stored as a historical string; later edits to per-scope/global
  numbering templates or abbreviations only affect logs that have not been issued yet.
- **Re-issue action**: `CalibrationLog.reissue_certificate_no()` regenerates from CURRENT
  settings while keeping the log's slot in its client+scope series (`cert_seq` unchanged;
  never-issued logs take the next slot). POST
  `/calibration-logs/<pk>/reissue-cert-no/` (`calibration_log_reissue_cert`,
  `approve_calibration`-gated, statuses past review, GET rejected) → messages show old → new.
  Log detail page now shows a Certificate No. field ("Not issued yet" when blank) + a
  "Re-issue No." button next to Generate Certificate (confirm dialog).

## Follow-up (latest session — per-scope pressure certificate + dynamic units)

- **Pressure certificate template** (migration `0037` + `0038`): `PreCalibrationLog` gains a `unit` FK
  (related_name `pre_calibration_logs`) — the **unit of measurement of the equipment, determined during
  pre-calibration** (`PreCalibrationForm.unit`, scope-filtered; JS reloads units on scope change via the
  existing `units_by_scope` endpooint; shown on pre-cal list/detail + `PreCalibrationLogSerializer`
  exposes `unit`/`unit_symbol`/`scope_name`). `CalibrationLogCreateView` seeds the readings unit selector
  from the pre-cal unit (`context['initial_unit_id']` → template `INITIAL_UNIT_ID`, applied in
  `loadUnitSelector`). The certificate view computes `reporting_unit` (first reading unit → pre-cal unit →
  first scope unit) and passes it to both cert templates.
- **PCAL custom cert layout** (migration `0038_seed_pressure_certificate_template`): base64-embedded
  Django template stored in `CalibrationType.certificate_template` for the Pressure scope, faithfully
  reproducing the EATL "Pressure Gauge Cert Template" Word doc: two-line doc header (EATL logo via
  `company.logo`, else `core/images/image2.jpeg`; company address; `ISO/IEC 17025:2017 ACCREDITED
  LABORATORY` badge), centered `ISO/IEC 17025 CALIBRATION CERTIFICATE` title + ISSUED BY + CERTIFICATE
  NUMBER + DATE OF ISSUE; the 8-row equipment table (Owner/Model/Range/Address/Env/Equipment/Date
  Received/Manufacturer/Calibration Date/Accuracy(specs)/Next Due/Serial/Calibrated at); Method paragraph
  (`log.procedure.manual_reference` fallback `EATL-E&I-PR-005`, DKD-R6-1:2014/ISO/IEC17025, first
  standard cert no + `company.traceability_body` fallback NVLAP); accreditation + validity disclaimers;
  Physical Inspection (`log.physical_condition`); Standard Reference Instrument table (`standards`
  M2M, columns Description/Make/Model/Serial/Cert Number/Cal Date); 9-column Calibration Data grid
  (REF + As Found READ/ERR + As Left READ/ERR + S-Dev + MPE + Uncertainty + Remark) with per-cell
  unit headers **always driven by `{{ reporting_unit }}` — never hardcoded**; REMARK + decision-rule +
  ISO GUM/NIST SOP 29 K=2 uncertainty paragraphs; two-column signature table (Calibrated By = `log.calibrated_by`,
  Authorized By = reviewer name + `log.reviewer_signature` img when `status == 'approved'`); `END OF REPORT`;
  footer `EATL/LMS/F/01 Rev 04` + date. Print CSS: A4, `@page margin:0`, black single-border tables.
  The template uses `{% verbatim %}` around the `&lt;style&gt;` block (`{% raw %}` is NOT a Django tag).
  Editable live in Settings → Scopes → Cert Layout; other scopes keep the default two-page certificate.
- **Verification**: `manage.py check` clean, `makemigrations --check` clean, migrations `0037`/`0038`
  applied; end-to-end test client flow green — pre-cal POST with unit → cal-log create seeds
  `INITIAL_UNIT_ID` → certificate renders the PCAL custom template with dynamic unit (MPa, not PSI).
  Extracted Word logos saved to `core/static/core/images/image1.png` (NiNAS seal) + `image2.jpeg` (EATL logo).

## Follow-up (multi-unit/multi-scope overhaul + ISO 17025 doc numbering + yearly ZIP export — migration `0039`)

- **Multi-scope / multi-unit** (migration `0039_multi_scope_multi_unit`): `PreCalibrationLog` gains **M2M
  `scopes` → `CalibrationType` and `units` → `Unit`** (legacy single FKs kept as mirrors = first). The pre-cal
  create form renders **multi-select checkbox grids** (scope- and unit-filtered), POST handled by
  `PreCalibrationForm` (`scopes`/`units` cleaned as `.filter(pk__in=[...])`), and the pre-cal views
  (`PreCalibrationLogCreateView`, `PreCalibrationLogUpdateView`, list/detail context) `.set()` the M2M then
  mirror the first onto `scope`/`unit` — overriding the initial mirror from `waybill_item.scope`. `WaybillItem`
  scope is mirrored from `precal.scope` when the pre-cal is created (`waybill_item.update(scope=first_scope)`)
  but never overwritten on later edits. `CalibrationLog` gains M2M `scopes` (legacy `scope` FK = first),
  `CalibrationLogForm` populates the scopes checkbox grid from pre-cal scopes (POST `.set()`), and readings
  are per-unit via `CalibrationLogReading.unit` FK → `Unit` (`device_unit` legacy TextField retained empty).
  `Primary` gains **`range_min`/`range_max`** — `Primary.is_range_compatible(min, max)` requires the primary
  range (when both bounds set) to *fully contain* the equipment range (allow policy for no-bounds standards).
  `Primary.scope`/`unit` populated the same smart-mirror way on API create/update. Templates: pre-cal
  list/detail + cal-log list/detail show Scope(s)/Unit(s) badges, cal-log detail shows the Primary
  range-compatibility verdict (per-standard `check`, overall `union` verdict); pre-cal list columns replaced
  with "Scope(s) / Unit(s)" + Doc No. `PrimaryAdmin` gained unit/range columns; `CalibrationLogAdmin`/
  `PreCalibrationLogAdmin` use `filter_horizontal` for the scopes/units grids.
- **ISO 17025 document numbering** (migration `0039`): new **`doc_no` + `doc_seq`** columns on
  `PreCalibrationLog`, `EnvironmentRecord`, `CalibrationProcedure` (stored historical string + ever-incrementing
  sequence). Per-year series with `TransactionTestCase`-style ordering, assigned via **`assign_doc_no()`**
  (**`seq = max(seq for same year) + 1` inside `select_for_update`; overwrite only when unset**) — schemes:
  `PRE-{year}-{seq:04d}`, `ENV-{lab}-{year}-{seq:04d}` (lab = `abbreviation_for(None, location.name)`),
  `PROC-{scope_abbr}-{year}-{seq:04d}`. Wired into: `PreCalibrationLogViewSet.perform_create` (web create
  view already had it), `EnvironmentCreateView.form_valid` + `EnvironmentRecordViewSet.perform_create`,
  `procedure_assign` (web + API). Backfill: `python manage.py assign_doc_numbers` (fills blank `doc_no`
  only, for all three models). Displayed: environment list (`Doc No` column), procedures list + detail,
  pre-cal list + detail. Admin read-only `doc_no` on PreCalibrationLog/EnvironmentRecord/CalibrationProcedure.
- **Documents archive + yearly ZIP export**: new `/documents/` page (sidebar "Documents" link,
  `view_waybills` **or** `approve_calibration` gate; skipped on mobile nav) listing each year with counts;
  `GET /documents/<year>/export/` → `EATL-Documents-{year}.zip`.
  - **Zip layout**: `Year/{ClientAbbr}/{ScopeAbbr}/{equipment}_{serial}/certificates/` (cert no HTML rendered
    via `_render_certificate_html` — per-scope custom `certificate_template` or default two-page — plus the
    uploaded certificate file verbatim), `Year/waybills/{ClientAbbr}/{waybill_no}/uploaded_waybills/`,
    `Year/env/{Location.name}/{slot}/` (HTML per record), `Year/procedures/{ScopeAbbr}/{doc_no}/`,
    and `Year/registers.xlsx` (5 sheets: Certificates/Waybills/Env/Procedures/Primaries, styled headers).
  - **`abbreviation_for(explicit, name)`** helper in `core/models.py` reused for folder abbreviations:
    explicit abbr uppercased, else initials of ≥3 words (max 4 chars), else first 3 letters padded.
  - **`_sanitize_fs_part`** strips `/ \ : * ? " < > |` → `_`. `_document_years()` samples all four
    date-bearing models (sorted desc). Zip entry writing uses `engines['django'].get_template(...).render(...)`
    (strings) — the cert default template is rendered via `_render_certificate_html(log, context, request)`
    which returns a `str` (export) while `calibration_certificate` still returns an `HttpResponse`.
  - Certificate context extracted into `_certificate_context(log)` (no decorators — helper, not a view)
    shared by `calibration_certificate` and the export.
- **API**: `CalibrationLogSerializer` + `CalibrationLogWriteSerializer` expose `scopes` (and read-only
  `scope_names`); `standards` is a writable M2M in the write serializer (`PrimaryKeyRelatedField`) with
  custom create/update (M2M popped then `.set()`, scope mirrored from first). `PreCalibrationLogSerializer`
  exposes writable `scopes`/`units` + read-only `scope_names`/`unit_symbols`/`range_value`/`doc_no` with
  custom create/update (mirror from M2M firsts, fallback `waybill_item.scope`). Fixed latent
  ImproperlyConfigured: `PreCalibrationLogSerializer` no longer references nonexistent `updated_at`.
- **Verification**: `/tmp/opencode/smoke_multiscope.py` — **43 checks green** (transactional rollback):
  pre-cal create page + POST (2 scopes, 2 units, doc_no), item scope mirror + `cal_pending`, cal-log create
  page (INITIAL_UNIT_ID, scope pre-tick) + POST with per-unit readings, multi-scope badges on list/detail,
  env + procedure POST assign doc_no, documents list + export ZIP structure (registers.xlsx, cert/env/proc
  HTML, `SCL/SS1` abbr path, lab+slot env path), API scopes/symbols/doc_no exposure. `manage.py check` clean;
  `makemigrations --check --dry-run` → no changes; migration `0039` applied. Relevant reqs: cal-log POST needs
  `pass_fail`, `equipment_owner`, `calibrated_at_date`, `physical_condition`; DRF list responses are
  paginated (`results` key).

## Follow-up (site brand logo = calibration-certificate logo)

- **`company_logo` context processor** (`core/context_processors.py`): mirrors the certificate logic exactly —
  returns the uploaded `CompanyProfile.logo` URL when set (Settings → Company tab), else falls back to the EATL
  logo asset `core/static/core/images/image2.jpeg`. Registered in `jobrec/settings.py` TEMPLATES context_processors.
- **Using it**: `base.html` (mobile top bar + sidebar brand) and `auth/login.html` now render
  `<img src="{{ company_logo }}">` instead of the old `core/images/logo.png`. So the site chrome and the
  calibration certificate always share the same logo; uploading a company logo in Settings updates both.

## Follow-up (EATL uncertainty budgets — migration `0040`)

- **Models** (migration `0040_uncertaintybudget_uncertaintybudgetcomponent`): `UncertaintyBudget` (scope FK →
  `CalibrationType`, related_name `uncertainty_budgets`; title, doc_ref, revision, revised_on, source `file`
  `upload_to='uncertainty_budgets/'`, `active` bool, `expanded_k` default 2.00, component_count, parse_status
  pending/ok/error, parse_error, created_at) and `UncertaintyBudgetComponent` (budget FK related_name
  `components_ordered`, position, symbol, source, method, value CharField, distribution, divisor, std_uncertainty).
  `combined_std_uncertainty()` = √(Σ uᵢ²) over stored components; `expanded_uncertainty()` = k × u. A scope keeps
  revisions but exactly one is `active` and drives the uncertainty engine + certificate annex.
- **Parser** `core/uncertainty_budget.py::parse_budget_file(path)` locates the workbook's header (title, doc ref,
  Rev, date) and the Type-B table by scanning cell text — not fixed coordinates — plus the per-point grid.
  Doc-ref is resolved slash-first (`EATL/LAB/UNC/01` preferred over a bare `UNC…` word so title text like
  "UNCERTAINTY BUDGET…" is never mistaken for the reference). Component methods, frequently shifted one row up in
  the EATL template, are collected in order and paired positionally. Returns header/components/points/warnings;
  components carry Decimal divisor + std (derived as value/divisor when the workbook leaves std blank).
- **Upload UI — Settings → Scopes → Unc. Budget** (`/settings/scopes/<pk>/uncertainty-budget/`, view
  `scope_uncertainty_budget`, `approve_calibration`-gated; URL mirrors `scope_cert_template`): upload an .xlsx →
  saved to media → parsed → `UncertaintyBudgetComponent` rows bulk-created → prior revisions deactivated, new one
  activated; per-revision Activate/Download/Delete + component table + combined/expanded preview. Settings scopes
  tab gained a "Unc. Budget" column (badge link; table colspan bumped 7→8).
- **Uncertainty engine wiring** (`CalibrationLog.compute_uncertainty`): BUDGET PATH (active scope budget with
  components) — u_comb = √(static_comb² + error_max²) (error_max = max |reading.error|), k = primary.coverage_factor
  if set else budget.expanded_k, U = k × u_comb; EQN PATH unchanged as fallback. Both call
  `_finalize_uncertainty_result()` which auto-derives pass/fail from uncertainty_in_tolerance (only when the manual
  verdict is pass/fail; 'conditional'/'not_applicable' preserved).
- **Certificate annex**: `_certificate_context` adds `budget` (active scope budget); default `certificate.html` page 2
  renders an "Uncertainty Budget — {doc_ref} Rev {rev}" table (Symbol/Source/Value/Distribution/Divisor/Std Unc/
  Method + combined footer + k) under Notes. Custom per-scope templates share the same context and may use `budget`.
- **Admin**: `UncertaintyBudgetAdmin` + `UncertaintyBudgetComponentInline` (parse fields read-only).
- **Management command** `python3 manage.py import_uncertainty_budget <budget.xlsx> --scope <pk> [--title "..."]
  [--deactivate-existing]` — uploads, parses, activates, screens output.
- **Provided workbook imported**: `Pressure Uncert Budget - 2 Ups.xlsx` (EATL/LAB/UNC/01 Rev 02, 24/08/2026) is the
  ACTIVE budget for the **Pressure Calibration** scope (id 2): 9 components (UPind, Uhys, Udrift-std, Ures-ut, Uref,
  Urep-DKD, Ureprod-DKD, UHd, Uzero-dev — dynamic reading/repeatability terms left blank per EATL practice),
  combined static u = 0.040825, points 0/175/350/525/700. Future budgets in the same format are uploaded via
  Settings → Scopes (or the command); saving a new workbook version automatically deactivates the previous revision.
- **Verification**: `/tmp/opencode/smoke_budget.py` — **26 checks green** (web upload→parse→activate, header/component
  fidelity incl. positional method pairing, second-upload deactivation, budget-driven expanded uncertainty arithmetic
  incl. pass/fail auto-derivation and 'conditional' preservation, cert annex render, scopes-tab link, command
  importable). Prior suites still green (`smoke_multiscope.py` 43). `manage.py check` clean; `makemigrations --check`
  → no changes. Parser regression-checked against the real Pressure workbook (EATL/LAB/UNC/01 Rev 02, 9 comps, 5 pts).

## Follow-up (As Found / As Left reading tables + MPE + majority Pass/Fail — migration `0041`)

- **Split readings into two tables**: `CalibrationLogReading` gains `reading_type`
  (`as_found`/`as_left`, db_index, default `as_found`), `maximum_permissible_error`
  (Decimal 12,4), and `remark` (Accepted/Rejected). Web create/edit renders separate **As Found**
  (4-col: #, Instrument, UUT, Error) and **As Left** (6-col: adds MPE ± and Remark) tables; the
  reference instrument column is copied between the two via "Copy refs…" buttons;
  Error = Instrument − UUT computed live client-side (and backend fallback).
- **MPE**: per-log default `CalibrationLog.maximum_permissible_error` (form field, added to
  `CalibrationLogForm.Meta.fields`) + per-row override; blank As-Left rows inherit the log default
  (`_save_log_readings` and API `_after_readings`). Remark rule: `abs(error) <= MPE → Accepted`
  else `Rejected`, computed in `CalibrationLogReading.save()` (which force-persists `remark` even
  under `update_fields`). `standard_uncertainty` property = MPE/√3 shown below the As-Left table
  (detail + certificate).
- **Pass/Fail from majority**: `CalibrationLog.derive_pass_fail_from_remarks()` uses strict
  majority over judged As-Left rows (`accepted * 2 > total` → Pass, tie → Fail); manual
  `conditional`/`not_applicable` preserved. Called from `_save_log_readings` (web create/edit) and
  API `_after_readings`; create-page JS auto-sets the Result select from the live remark count.
- **Comments, not free-text**: `CalibrationLog.as_found`/`as_left` TextFields removed (migration
  `0041` folds old text into `notes`). `notes` relabeled "Comments"; rendered once on detail,
  certificate, review/approve confirm pages.
- **Templates/context**: create/update views swap `readings_json` for
  `readings_found_json`/`readings_left_json` (hidden fields); `_parse_readings_payload` keeps a
  legacy `readings_json` fallback (treated as As-Found) for old API clients. Detail + certificate
  contexts add `readings_found`, `readings_left`, `remarks_accepted`, `remarks_total`,
  `remarks_majority_pass`. review/approve confirm pages take the split querysets and no longer
  touch the removed text fields.
- **API**: `CalibrationLogReadingSerializer` exposes `reading_type`/`maximum_permissible_error`/
  `remark`/`standard_uncertainty`; `CalibrationLogWriteSerializer` accepts per-row `reading_type`
  (default `as_found`) in `readings_data`, computes `error = inst − uut` when missing
  (`_normalize_readings`), backfills row MPE from the log default, derives majority Pass/Fail.
  (Latent fixes: `Decimal` now imported in both models.py and serializers.py — the former for the
  MPE/√3 property, the latter guards the API MPE-fill path.)
- **Migration `0041`**: RunPython folds as_found/as_left text into `notes` before drop; backfills
  existing reading rows to `reading_type='as_found'`; applied on dev.
- **Verification**: `/tmp/opencode/smoke_readings.py` — **42 checks green** (create POST with
  found/left payloads, remark/majority derivation, MPE inheritance, std-unc arithmetic, detail/
  review/approve/certificate split-table renders, review POST signature stamping, reject then
  re-edit round-trip) plus an inline API serializer check. `manage.py check` clean;
  `makemigrations --check --dry-run` → no changes.
## Follow-up (pre-cal unit dropdown fix — no migration)

- **Pre-cal units now come from `units_by_scope`** (the same AJAX source the calibration-log
  page uses) instead of the old server-side `unit_availability_json`/`unit_scope_map_json` maps +
  DOM filter. `PreCalibrationLogCreateView.get_context_data` dropped the map/availability
  computation; the `pre_calibration/create.html` JS fetches
  `GET /api/units-by-scope/0/?scopes=1,2&range=…` (lazy-seeds the `Unit` catalog via
  `units_for_scope`, so a fresh/custom scope self-heals), re-renders the checkbox grid from the
  JSON, and shows a **Refresh button** (`?refresh=1`) + loading spinner. `range_value` changes
  trigger a debounced reload so `range_ok` badges track the typed range.
- **Unavailable units are shown disabled, never hidden** (root cause of the report): a unit with
  no active `Primary` gets a "no reference standard" badge, and one whose active standards don't
  contain the equipment range gets "range mismatch" (both `opacity-60` + `input.disabled`). Only
  `available && range_ok` units are selectable — this matches `PreCalibrationForm.clean`'s gate
  exactly. The old silent `e.preventDefault()` submit block was removed; scope errors surface via
  `#scope-error` and `form.units.errors`.
- **`range_value` prefilled from the waybill item** (`waybill_item.range_field`) on unbound GET,
  mirroring `CalibrationLogForm`.
- **`parse_range` ASCII-hyphen fix** (`core/procedures.py`): `'0-10 bar'` now parses to `(0, 10)`
  instead of `(-10, 0)` (the hyphen was being read as a minus sign). When exactly two numbers are
  found, the second is negative, the first isn't, and there's no `'to'`, the hyphen is treated as a
  separator — so OCR-style ASCII ranges (`0-10 bar`) match `Primary.contains_range` correctly;
  `'-5 to 25 °C'` keeps its negative low bound. This propagates to pre-cal containment,
  `units_by_scope` `range_ok`, `suggested_primaries`, and procedure test points.
- **Verification**: `/tmp/opencode/smoke_precal_units.py` — **31 checks green** (create page
  renders fetch-based UI without stale maps, `units_by_scope` lazy-seed, disabled-badge flags
  `available`/`range_ok` for no-primary / in-range / out-of-range, pre-cal POST with scopes+units
  → M2M + legacy mirrors + `doc_no`, `range_field` prefill, ASCII-hyphen containment). Existing
  `/tmp/opencode/smoke_readings.py` (42) still green; `parse_range` edge-case table passes;
  `manage.py check` clean; `makemigrations --check` → no changes.
