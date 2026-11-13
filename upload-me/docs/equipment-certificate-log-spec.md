# Equipment Logs — Feature Specification (v3)

Status: **building**. Extraction = local text parsing + offline local OCR fallback.

## 1. Purpose

Replace the physical certificate logbook / per-type Excel files with **Equipment Logs**,
one new section under RECORDS in the E&I Lab (Django app under `jobrec-review/`).

**The system reads the certificate itself** (no user re-typing): text-based PDF/DOCX
are parsed with local libraries; scanned/image PDFs are read with the existing local
RapidOCR. No AI, no LLM, no external API. The operator only *verifies and corrects*
what was extracted — which is what the Preview step is for.

## 2. Hard constraints (carried over)

- Certificates arrive as **PDF or DOCX**.
- The uploaded certificate file is **never stored** — it exists only for the
  on-screen viewer during the entry session; deleted on Save / Cancel and by the
  stale-file purge.
- **Administrator-only** (superuser or active personnel role `Administrator`) for
  every new page, mutation and export. Sidebar hidden otherwise.
- The log is a **backup / record** — **no approval workflow** on save.
- Extraction is **exact or blank**: values are taken from the document text/tables;
  what cannot be found is left blank. Nothing is invented. Every value the system
  writes is editable in Review; the Preview re-shows everything before saving.
- Lab Equipment columns: Equipment / ID · Serial / Model · E&I Scope · Range /
  Unit · Interval · Last Calibration · Due Date · Status · Record.
  No certificate record yet ⇒ **NIL** in the Record column.
- Year rollover = a new year folder; previous years never overwritten.

## 3. Navigation (single new item)

RECORDS sidebar (`jobrec-review/core/templates/core/base.html`):

```
RECORDS
  …
  Lab Equipment             (unchanged)
  Lab Calibration Programme (unchanged)
  Equipment Logs            ← NEW (exact label)
```

JOB WORKFLOW → `Certificates` is **not touched**.

## 4. Equipment Logs page (`/ei-lab/equipment-logs/`)

Header: `Equipment Logs` + two buttons, top-right:
**`Upload certificate`** · **`Upload template`**

Body: folder grid — each year folder (current year always present) plus one
**Templates** folder.

### 4.1 Year view → equipment type → serial numbers → record
- Year view: equipment types found in the log for that year with counts;
  **Download <year> log (Excel)** button per year.
- Type view: serial number list panel; record pane with chips
  `Model` · `Certificate` · `Test date` · `Due date` · `Environment` · `Conclusion`,
  the editable test-table grid, change history, `Download this sheet`.
- Edits on saved records require a **reason** (unlock flow) and are recorded in
  change history (`when`, `who`, `reason`).
- Serial deep-link from Lab Equipment opens that serial's record directly.

### 4.2 `Upload certificate`
Chips: **Upload → Review → Preview → Save to log**

1. **Upload**: choose a template (the equipment group, e.g. Grinding Machine,
   Chart Recorder — from already-uploaded templates) + one certificate file
   (`.pdf` / `.docx`).
   The file goes to a **private temp dir**, session-bound, never `media/`.
   Server immediately runs the **extraction pipeline** (section 5).
2. **Review & fix** (nothing requires full typing; everything editable):
   - Left pane: certificate viewer. PDF → `<iframe>` from the session-bound temp
     view. DOCX → rendered read-only HTML via `python-docx`.
   - Right pane: form pre-filled with extracted values:
     `Serial number`, `Model`, `Certificate no.`, `Test date`, `Due date`,
     `Environment`, `Conclusion` (Pass/Fail select) + test-table grid
     (columns from the chosen template, rows from the detected table).
   - Fields the system could not find are blank (never guessed) and visually
     flagged for attention. A short notice lists what was found/missed.
3. **Preview**: read-only recap exactly as the log record will look.
   Back to Review, or continue.
4. **Save** — modal:
   > **Are you sure? The certificate file will not be kept after saving.**
   `Cancel` · `Preview` · **`Yes, Done`**
   On Yes: create/update `EquipmentCertificateRecord` (upsert on
   template+serial+year; on update append `change_history`), update Lab
   Equipment on exact serial match (`last_calibrated`, `calibration_due_date`,
   `certificate_no`, `status→active` unless inactive), **delete temp file**,
   redirect to the log record with a toast.

### 4.3 Templates folder
Lists uploaded templates: `Equipment type | test-table columns | Created | actions`
- `Download original` (`.xlsx` kept in private storage — it is a template, not a
  customer record), `Deactivate` / `Reactivate`.

### 4.4 `Upload template`
Templates are **Excel files**, one per equipment group.

1. Pick `.xlsx` + **equipment name** (default: filename stem, editable, unique).
2. Server parses the file with `openpyxl` and renders a **read-only sheet
   preview**; user picks the worksheet (default first/active) and **clicks the
   row to use as column headers**; or edits the detected names as comma-separated.
3. Confirm → stores `EquipmentCertificateTemplate` (`name`, `columns`,
   `original_file` (private storage key), `active`, timestamps, `created_by`).
4. Nothing is guessed: every stored column came from the picked row.

## 5. Extraction pipeline (`core/cert_extract.py`)

Deterministic, label/table-driven (never position-assuming):

1. **Get content**
   - PDF: `pdfplumber` → full text + detected tables.
     If extracted text < ~20 chars ⇒ scanned/image PDF ⇒ render pages via
     **PyMuPDF** → PNG per page → **RapidOCR** (`core/ocr_engine.py::extract`)
     → lines with bboxes; tables reconstructed from line grouping
     (fallback: user fills the grid by hand — grid is still editable).
   - DOCX: `python-docx` → paragraphs + tables.
2. **Common fields** — matched against label patterns (case-insensitive), e.g.
   `Serial No/Number/S/N`, `Certificate No/Date`, `Model`, `Test/Calibration date`,
   `Due date/Valid until/Next calibration due`, `Environment/Temperature`,
   `Humidity`. Dates parsed from common formats to ISO. Conclusion: explicit
   `Pass`/`Fail` near a result/conclusion label, else a standalone Pass/Fail line;
   else left blank. `environment` composed as `<temp> °C · <RH> %RH` when both found.
3. **Test table** — find the detected table whose header cells best match the
   template's `columns` (score = matched columns, case-insensitive contains).
   Require ≥ 50 % of columns matched, else leave the grid empty with a notice.
   Map columns → rows as-is.
4. Output: `{fields: {...}, columns: [...], rows: [[...]], found: [...], missing: [...], raw_text}`.
   `found`/`missing` drive the Review notice — **no confidence scores** anywhere;
   the user decides what to correct.

Dependencies (local, no services): `pdfplumber`, `PyMuPDF`, `python-docx`,
`rapidocr-onnxruntime==1.4.4 --no-deps` + `opencv-python-headless`, `onnxruntime`,
`numpy<3`, `Shapely!=2.0.4`, `six`, `tqdm`, `pyclipper`, `PyYAML` (per
`jobrec-review/requirements-pa.txt`). All are lazy-imported; missing engines
degrade to blank fields + notice, never to a crash.

## 6. File lifecycle

Upload → private temp dir (`<EI_PRIVATE_STORAGE_ROOT>/tmp/cert_upload/<uuid><ext>`)
→ session-bound viewer → deleted on Yes/Done, Cancel, and stale-purge of files
older than 24 h (piggy-backed on the workflow worker). Never in `MEDIA_ROOT`;
records hold data only.

## 7. Data model (migration 0057)

As v2: `EquipmentCertificateTemplate`, `EquipmentCertificateRecord`
(`unique_together = (template, serial_no, year)`; `columns`/`rows`/`change_history`
JSON; FK template PROTECT). No `FileField` for certificates.

## 8. Lab Equipment (`Primary`) write contract

On certificate save, match `serial_no` (case-insensitive, exact):
`last_calibrated=test_date`; `calibration_due_date=due_date` (fallback:
`test_date + calibration_frequency` months); `certificate_no`; `status='active'`
unless inactive. No match ⇒ nothing created/changed (logged only).

### Lab Equipment Record column (existing page)
`Record` = `View record` link → latest log record for that serial (deep link to
the type view anchored to the serial) — or plain **NIL**.

## 9. Permissions

`ei_admin_only`: `user.is_superuser` OR active personnel role `Administrator`.
403 otherwise; sidebar hidden otherwise.

## 10. Out of scope / later

Client/in-house split; linking to client jobs/waybills; batch upload; certificate
storage; template Quality approval; auto-creating missing Lab Equipment;
uncertainty-budget extraction; `NEW` tag.
