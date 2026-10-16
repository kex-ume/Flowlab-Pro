"""Authoritative E&I workflow transactions, independent of Flask identities."""
from datetime import date, timedelta
import hashlib
import io
import json
import math
from pathlib import Path
import re
import uuid
import zipfile
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Q
from django.urls import reverse
from django.utils import timezone

from .auth_utils import has_perm, get_users_with_perm, lab_authority
from .models import (Job, Client, Personnel, CalibrationType, CalibrationLog,
    CalibrationLogTemplate, JobUUT, JobSubmission, JobReview, JobDecision, JobDocument,
    JobScheduleRevision, TechnicalRecord, TechnicalRecordRevision,
    PersonnelAuthorization, PersonnelCompetency, WorkflowAudit, Notification)
from .models import Primary
from .notifications import notify_users
from .uncertainty import evaluate_equation


class Conflict(ValidationError):
    pass


def actor_fields(user):
    try:
        name = user.personnel_profile.name
    except Personnel.DoesNotExist:
        name = user.get_full_name() or user.username
    return {'created_by': user, 'actor_name': name}


def supervisor(user):
    return bool(user.is_active and (user.is_superuser or has_perm(user, 'manage_ei_jobs')))


def active_personnel():
    return Personnel.objects.select_related('user', 'role').filter(user__is_active=True, employment_status='active')


def authorized(person, activity, scope=None, method=None):
    if not person or not person.user.is_active or person.employment_status != 'active':
        return False
    if activity in ('review','approve','supervise') and lab_authority(person.user):
        return True
    today = timezone.localdate()
    qs = person.authorizations.filter(activity=activity, revoked_at__isnull=True, suspended_at__isnull=True, effective_from__lte=today).filter(Q(expires_on__isnull=True) | Q(expires_on__gte=today))
    if method:
        qs = qs.filter(Q(method_reference='') | Q(method_reference__iexact=method))
    if scope:
        qs = qs.filter(Q(scope=scope) | Q(scope__isnull=True))
        if activity == 'perform':
            competencies = person.competencies.filter(scope=scope, revisions__isnull=True, result='competent', assessed_on__lte=today).filter(Q(expires_on__isnull=True) | Q(expires_on__gte=today))
            if method:
                competencies = competencies.filter(method_reference__iexact=method)
            if not competencies.exists():
                return False
    return qs.exists()


def eligible(person, job):
    if not person or not person.user.is_active or person.employment_status != 'active':
        return False
    for uut in job.uuts.filter(archived=False):
        permission = 'repair_equipment' if uut.request_type == 'repair' else 'edit_calibration'
        method = uut.template.schema.get('method_reference') if uut.template_id else None
        if not has_perm(person.user, permission) or not authorized(person, 'perform', uut.scope, method):
            return False
        if uut.request_type == 'calibration_repair' and not has_perm(person.user, 'repair_equipment'):
            return False
    return True


def visible_jobs(user):
    if not user.is_authenticated or not user.is_active:
        return Job.objects.none()
    if lab_authority(user):
        return Job.objects.filter(administratively_archived=False)
    base = Q(workflow_managed=False)
    own = Q(creator=user) | Q(assigned_to__user=user)
    if supervisor(user):
        own |= ~Q(approval_state='draft')
    # Formally authorized contributors may see submitted jobs in their own scopes.
    person = Personnel.objects.filter(user=user).first()
    if person:
        scope_ids = [scope.pk for scope in CalibrationType.objects.all() if authorized(person, 'perform', scope)]
        if scope_ids and has_perm(user, 'edit_calibration'):
            own |= Q(uuts__scope_id__in=scope_ids) & ~Q(approval_state='draft')
    return Job.objects.filter(base | (Q(workflow_managed=True) & own),administratively_archived=False).distinct()


def require_job_read(user, job):
    if not has_perm(user, 'view_jobs') or not visible_jobs(user).filter(pk=job.pk).exists():
        raise PermissionDenied('You do not have access to this E&I job.')


def audit(user, job, event, before=None, after=None, uut=None):
    return WorkflowAudit.objects.create(job=job, uut=uut, event=event, before=before or {}, after=after or {}, **actor_fields(user))


def snapshot(job):
    return {'id': str(job.public_id), 'client': job.client_id, 'po': job.purchase_order_number,
            'type': job.job_type, 'description': job.job_description,
            'received': str(job.received_started_date or ''), 'start': str(job.planned_start_date or ''),
            'end': str(job.scheduled_end_date or ''), 'assignees': list(job.assigned_to.values_list('id', flat=True)),
            'suggested_personnel':list(job.suggested_personnel.values_list('id',flat=True)),
            'uuts': list(job.uuts.filter(archived=False).values('id', 'name', 'serial_number', 'request_type', 'scope_id', 'template_id'))}


def parse_date(value, label, required=False):
    if not value:
        if required:
            raise ValidationError(f'{label} is required.')
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise ValidationError(f'{label} must be a valid date.')


@transaction.atomic
def save_job(user, payload, job=None):
    if not has_perm(user, 'create_jobs'):
        raise PermissionDenied('Job creation permission is required.')
    key = uuid.UUID(str(payload.get('creation_key'))) if payload.get('creation_key') else uuid.uuid4()
    if job is None:
        existing = Job.objects.filter(creation_key=key).first()
        if existing:
            require_job_read(user, existing)
            return existing
        client = Client.objects.filter(pk=payload.get('client')).first()
        if not client:
            raise ValidationError('Choose a registered E&I client to save the draft.')
        job = Job(client=client, creator=user, creation_key=key, workflow_managed=True, approval_state='draft')
    else:
        job = Job.objects.select_for_update().get(pk=job.pk)
        require_job_read(user, job)
        if job.creator_id != user.pk and not lab_authority(user):
            raise PermissionDenied('Only the draft owner may edit this job.')
        if job.approval_state not in ('draft', 'reverted'):
            raise ValidationError('Submitted or approved job details are controlled; revert before editing.')
        if int(payload.get('version', -1)) != job.lock_version:
            raise Conflict('This draft was changed elsewhere. Reload the latest version before saving.')
    before = snapshot(job) if job.pk else {}
    client = Client.objects.filter(pk=payload.get('client')).first()
    if not client:
        raise ValidationError('Choose a registered client.')
    job.client = client
    kind = payload.get('job_type', 'lab')
    if kind not in ('lab', 'field'):
        raise ValidationError('Job type must be Lab or Field.')
    job.job_type = kind
    job.purchase_order_number = str(payload.get('po', '')).strip() or None
    job.job_description = str(payload.get('description', ''))[:10000]
    job.received_started_date = parse_date(payload.get('received_date'), 'Received date')
    job.planned_start_date = parse_date(payload.get('start_date'), 'Planned start date')
    job.scheduled_end_date = parse_date(payload.get('end_date'), 'Scheduled end date')
    if job.planned_start_date and job.scheduled_end_date and job.scheduled_end_date < job.planned_start_date:
        raise ValidationError('Scheduled end date cannot precede planned start date.')
    if job.received_started_date and job.planned_start_date and job.planned_start_date < job.received_started_date:
        raise ValidationError('Planned start date cannot precede receipt.')
    job.remarks = str(payload.get('remarks', ''))[:10000]
    job.lock_version += 1
    job.save()
    ids = []
    for row in payload.get('uuts', []):
        uut = job.uuts.filter(pk=row.get('id'), archived=False).first() if row.get('id') else JobUUT(job=job)
        if uut is None:
            raise ValidationError('UUT does not belong to this job.')
        for field in ('name', 'equipment_type', 'manufacturer', 'model', 'serial_number', 'equipment_identifier', 'duplicate_reason'):
            length = 2000 if field == 'duplicate_reason' else uut._meta.get_field(field).max_length
            setattr(uut, field, str(row.get(field, ''))[:length])
        uut.request_type = row.get('request_type', 'calibration')
        if uut.request_type not in dict(Job.REQUEST_TYPE_CHOICES):
            raise ValidationError('Choose a valid request type for each UUT.')
        uut.scope = CalibrationType.objects.filter(pk=row.get('scope')).first() if row.get('scope') else None
        if row.get('scope') and not uut.scope:
            raise ValidationError('Select a registered scope.')
        if uut.scope and not uut.scope.active:
            raise ValidationError('This scope is archived. Select an active scope.')
        if row.get('scope') and not uut.scope:
            raise ValidationError('Select a valid E&I calibration scope.')
        uut.template = CalibrationLogTemplate.objects.filter(pk=row.get('template'), scope=uut.scope, status='approved').first() if row.get('template') else None
        if row.get('template') and not uut.template:
            raise ValidationError('The selected template must be approved for this UUT scope.')
        uut.save()
        ids.append(uut.pk)
    job.uuts.exclude(pk__in=ids).update(archived=True)
    people = list(active_personnel().filter(pk__in=payload.get('assignees', [])))
    if len(people) != len(set(payload.get('assignees', []))):
        raise ValidationError('An assigned person is disabled or unavailable.')
    for person in people:
        if not eligible(person, job):
            raise ValidationError(f'{person.name} is not authorized for the selected scope/work.')
    job.suggested_personnel.set(people)
    primary_id = payload.get('primary_assignee')
    job.suggested_primary = active_personnel().filter(pk=primary_id).first() if primary_id else None
    if primary_id and job.suggested_primary is None:
        raise ValidationError('Select an active registered person as primary responsible assignee.')
    lead_id = payload.get('supervisor')
    job.supervisor = active_personnel().filter(pk=lead_id).first() if lead_id else None
    if job.supervisor and not supervisor(job.supervisor.user):
        raise ValidationError('Select an authorized lab supervisor.')
    job.save()
    audit(user, job, 'draft_saved', before, snapshot(job))
    return job


def validate_submission(job):
    if not job.job_description.strip() or not job.received_started_date or not job.planned_start_date or not job.scheduled_end_date:
        raise ValidationError('Description, received date, planned start date and scheduled end date are required for submission.')
    rows = list(job.uuts.filter(archived=False))
    if not rows or any(not x.name.strip() or not x.serial_number.strip() for x in rows):
        raise ValidationError('Register each UUT with its name and serial number before submission.')
    seen = set()
    for row in rows:
        if row.request_type != 'repair' and not row.scope_id:
            raise ValidationError('Select the applicable E&I scope for each UUT requiring calibration.')
        serial = row.serial_number.strip().casefold()
        if serial in seen and not row.duplicate_reason.strip():
            raise ValidationError('Duplicate UUT serial numbers need a legitimate, documented override reason.')
        seen.add(serial)
    if job.job_type == 'lab':
        kinds = set(job.job_documents.values_list('kind', flat=True))
        if not {'service_request', 'waybill'} <= kinds:
            raise ValidationError('Lab jobs require actual uploaded Lab Service Request and Waybill files before submission.')


def job_recipients(job):
    recipients = [job.creator] if job.creator_id else []
    recipients += [p.user for p in job.assigned_to.select_related('user')]
    return recipients


def supervisors(job=None):
    users = list(get_users_with_perm('manage_ei_jobs').filter(is_active=True))
    if job and job.supervisor_id and job.supervisor.user.is_active:
        users.append(job.supervisor.user)
    return users


def notify_job(job, recipients, text):
    notify_users(recipients, text, reverse('job_detail', args=[job.pk]), 'job_updated')


@transaction.atomic
def submit_job(user, job, assign_now=False):
    job = Job.objects.select_for_update().get(pk=job.pk)
    require_job_read(user, job)
    if job.creator_id != user.pk:
        raise PermissionDenied('Only the sender may submit this draft.')
    if job.approval_state == 'awaiting':
        return job
    if job.approval_state not in ('draft', 'reverted'):
        raise ValidationError('This job cannot be submitted in its current state.')
    validate_submission(job)
    if assign_now and not supervisor(user):
        raise PermissionDenied('Only a lab supervisor may Save & Assign.')
    job.submitted_at = timezone.now()
    job.progress_status = 'scheduled'
    job.approval_state = 'awaiting'
    if job.original_end_date is None:
        job.original_end_date = job.scheduled_end_date
    job.lock_version += 1
    job.save()
    sequence = (job.submissions.aggregate(n=Max('sequence'))['n'] or 0) + 1
    JobSubmission.objects.create(job=job, sequence=sequence, snapshot=snapshot(job), **actor_fields(user))
    audit(user, job, 'submitted', after={'submission': sequence, 'submitted_at': job.submitted_at.isoformat()})
    notify_job(job, supervisors(job), f'E&I job {job.public_id} submitted by {user.get_full_name() or user.username} for commencement approval.')
    # Save & Assign must not bypass independent review and Chief approval.
    return job


@transaction.atomic
def decide_job(user, job, branch, comment='', assignee_id=None, creating_supervisor=False):
    if not supervisor(user):
        raise PermissionDenied('Lab supervisor permission is required.')
    job = Job.objects.select_for_update().get(pk=job.pk)
    require_job_read(user, job)
    submission = job.submissions.first()
    if not submission:
        raise ValidationError('This job has not been submitted.')
    if JobDecision.objects.filter(submission=submission).exists():
        return job
    if job.approval_state != 'awaiting':
        raise ValidationError('This job is not awaiting approval.')
    if branch not in dict(JobDecision._meta.get_field('branch').choices):
        raise ValidationError('Choose one of the four review decisions.')
    comment = comment.strip()
    if branch in ('comment', 'revert') and not comment:
        raise ValidationError('A comment is required for this decision.')
    before = snapshot(job)
    if branch == 'revert':
        job.approval_state = 'reverted'
    else:
        if branch == 'sender':
            person = active_personnel().filter(user_id=job.creator_id).first()
        else:
            person = active_personnel().filter(pk=assignee_id or job.suggested_primary_id).first()
            if person is None and branch == 'comment':
                person = active_personnel().filter(user_id=job.creator_id).first()
        if not person or not eligible(person, job):
            raise ValidationError('Select active personnel with valid scope competence and authorization.')
        if branch == 'another' and person.user_id == job.creator_id:
            raise ValidationError('Assign another user, or choose assign to sender.')
        review=JobReview.objects.filter(submission=submission).first()
        if not review:
            if user.pk==job.creator_id:
                raise PermissionDenied('An independent Supervisor must review this submission.')
            JobReview.objects.create(submission=submission,branch=branch,comment=comment,
                proposed_assignee=person,**actor_fields(user))
            job.lock_version+=1;job.save(update_fields=['lock_version'])
            audit(user,job,'job_reviewed',after={'submission':submission.pk,'assignee':person.pk,'comment':comment})
            notify_job(job,list(get_users_with_perm('approve_calibration')),
                f'Job {job.public_id}: Supervisor review complete; Chief / Administrator approval required.')
            return job
        if not lab_authority(user):
            raise PermissionDenied('Supervisor review is complete. Final approval requires Chief / Administrator.')
        if user.pk in (job.creator_id,review.created_by_id):
            raise PermissionDenied('The author and Supervisor reviewer cannot provide final job approval.')
        job.primary_assignee = person
        job.assigned_to.set([person])
        job.approval_state = 'approved'
    job.lock_version += 1
    job.save()
    assignments = list(job.assigned_to.values_list('pk', flat=True))
    decision = JobDecision.objects.create(submission=submission, branch=branch, comment=comment, assignments=assignments, **actor_fields(user))
    audit(user, job, 'supervisor_decision', before, {'decision': decision.pk, 'branch': branch, 'comment': comment, 'assignees': assignments})
    target = job.primary_assignee.name if job.primary_assignee_id and branch != 'revert' else 'Changes required'
    notify_job(job, job_recipients(job), f'{user.get_full_name() or user.username}: {decision.get_branch_display()} — {target}. {comment}')
    return job


@transaction.atomic
def commence_job(user, job):
    job = Job.objects.select_for_update().get(pk=job.pk)
    require_job_read(user, job)
    person = active_personnel().filter(user=user).first()
    if job.approval_state != 'approved' or not person or not job.assigned_to.filter(pk=person.pk).exists() or not eligible(person, job):
        raise PermissionDenied('Only an active, authorized assignee may commence an approved job.')
    if job.commenced_at:
        return job
    job.commenced_at = timezone.now()
    job.commenced_by = user
    job.progress_status = 'ongoing'
    job.lock_version += 1
    job.save()
    job.uuts.filter(archived=False).update(status='ongoing')
    audit(user, job, 'commenced', after={'actual_start': job.commenced_at.isoformat()})
    notify_job(job, supervisors(job), f'Job {job.public_id} commenced by {user.get_full_name() or user.username}.')
    return job


def can_contribute(user, uut, activity='perform'):
    permission = {'perform': 'repair_equipment' if uut.request_type == 'repair' else 'edit_calibration', 'review': 'review_calibration', 'approve': 'approve_calibration'}[activity]
    person = active_personnel().filter(user=user).first()
    method = uut.template.schema.get('method_reference') if uut.template_id else None
    if activity in ('review','approve') and lab_authority(user):
        return True
    return bool(person and has_perm(user, permission) and authorized(person, activity, uut.scope, method))


def require_work(user, uut, activity='perform'):
    uut.job = Job.objects.get(pk=uut.job_id)
    require_job_read(user, uut.job)
    if uut.archived or uut.status == 'completed' or uut.job.approval_state != 'approved' or not uut.job.commenced_at or uut.job.progress_status == 'completed':
        raise PermissionDenied('Approved commencement is required before technical work.')
    if not can_contribute(user, uut, activity):
        raise PermissionDenied('Active personnel authorization for this scope/activity is required.')


def sniff_upload(upload):
    if upload.size > settings.EI_UPLOAD_MAX_BYTES or upload.size <= 0:
        raise ValidationError('Choose a non-empty file of 20 MB or less.')
    raw = upload.read()
    upload.seek(0)
    ext = Path(upload.name.replace('\\', '/')).suffix.lower()
    allowed = {'.pdf': ('application/pdf', raw.startswith(b'%PDF-')),
               '.png': ('image/png', raw.startswith(b'\x89PNG\r\n\x1a\n')),
               '.jpg': ('image/jpeg', raw.startswith(b'\xff\xd8\xff')),
               '.jpeg': ('image/jpeg', raw.startswith(b'\xff\xd8\xff'))}
    if ext in ('.xlsx', '.docx'):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                if sum(x.file_size for x in z.infolist()) > 80 * 1024 * 1024:
                    raise ValidationError('The compressed document is too large.')
                required = 'xl/workbook.xml' if ext == '.xlsx' else 'word/document.xml'
                valid = required in z.namelist() and not any(x.lower().endswith('vbaproject.bin') for x in z.namelist())
            mime = 'application/vnd.openxmlformats-officedocument.' + ('spreadsheetml.sheet' if ext == '.xlsx' else 'wordprocessingml.document')
            allowed[ext] = (mime, valid)
        except (zipfile.BadZipFile, KeyError):
            raise ValidationError('Invalid Office document.')
    mime, valid = allowed.get(ext, ('', False))
    if not valid:
        raise ValidationError('File content does not match a supported PDF, image, XLSX or DOCX document.')
    return mime, hashlib.sha256(raw).hexdigest()


def upload_document(user, job, upload, kind, title='', uut=None):
    require_job_read(user, job)
    if job.progress_status == 'completed':
        raise ValidationError('Completed job documents require a controlled amendment.')
    if job.job_type == 'field' and kind == 'waybill':
        raise ValidationError('Field jobs do not request a waybill.')
    if job.job_type == 'field' and kind == 'service_request' and job.approval_state != 'approved':
        raise ValidationError('Optional Field Service Request upload is available after approval.')
    if uut:
        require_work(user, uut)
    elif job.creator_id != user.pk and not supervisor(user) and not job.assigned_to.filter(user=user).exists():
        raise PermissionDenied('Only the sender, supervisor or assignee may upload job documents.')
    mime, digest = sniff_upload(upload)
    doc = JobDocument(job=job, uut=uut, kind=kind, title=title or kind.replace('_', ' ').title(),
                      original_name=Path(upload.name.replace('\\', '/')).name[:200], mime_type=mime, sha256=digest, **actor_fields(user))
    doc.title = doc.title[:200]
    try:
        with transaction.atomic():
            doc.revision = (job.job_documents.filter(kind=kind, uut=uut).aggregate(n=Max('revision'))['n'] or 0) + 1
            doc.file.save(doc.original_name, upload, save=False)
            doc.save()
            audit(user, job, 'document_uploaded', after={'document': doc.pk, 'sha256': digest, 'revision': doc.revision}, uut=uut)
    except Exception:
        if doc.file.name:
            doc.file.storage.delete(doc.file.name)
        raise
    return doc


@transaction.atomic
def propose_schedule(user, job, proposed, reason):
    job = Job.objects.select_for_update().get(pk=job.pk)
    require_job_read(user, job)
    if not (supervisor(user) or job.assigned_to.filter(user=user).exists()):
        raise PermissionDenied('The responsible personnel or supervisor must propose a delay.')
    if not job.is_overdue or not reason.strip():
        raise ValidationError('An overdue job requires a reason and proposed revised completion date.')
    proposed = parse_date(proposed, 'Proposed end date', True)
    if proposed <= timezone.localdate() or proposed <= job.scheduled_end_date:
        raise ValidationError('Proposed end date must be after today and the existing deadline.')
    current = job.schedule_revisions.filter(status='pending').first()
    if current:
        return current
    change = JobScheduleRevision.objects.create(job=job, previous_end_date=job.scheduled_end_date, proposed_end_date=proposed, reason=reason.strip(), **actor_fields(user))
    audit(user, job, 'schedule_proposed', after={'revision': change.pk, 'proposed': str(proposed), 'reason': reason})
    notify_job(job, supervisors(job), f'Delay proposal for {job.public_id}: {reason}. Proposed completion {proposed}; approval required.')
    return change


@transaction.atomic
def decide_schedule(user, change, approve, comment=''):
    if not supervisor(user):
        raise PermissionDenied('Lab supervisor approval is required to change a deadline.')
    change = JobScheduleRevision.objects.select_for_update().get(pk=change.pk)
    if change.status != 'pending':
        return change
    if change.created_by_id == user.pk and not settings.EI_ALLOW_SELF_APPROVAL:
        raise PermissionDenied('Another supervisor must review your own schedule proposal.')
    job = Job.objects.select_for_update().get(pk=change.job_id)
    require_job_read(user, job)
    if approve:
        if change.proposed_end_date <= timezone.localdate():
            raise ValidationError('The proposed date has passed; request a new proposal.')
        job.scheduled_end_date = change.proposed_end_date
        job.delay_remark = change.reason
        job.delay_notified_on = None
        job.lock_version += 1
        job.save()
    elif not comment.strip():
        raise ValidationError('A rejection comment is required.')
    change.status = 'approved' if approve else 'rejected'
    change.decided_by = user
    change.decided_at = timezone.now()
    change.decision_comment = comment
    change.save()
    audit(user, job, 'schedule_decided', after={'revision': change.pk, 'decision': change.status, 'comment': comment})
    notify_job(job, job_recipients(job), f'Schedule proposal {change.status} by {user.get_full_name() or user.username}: {comment}')
    return change


def validate_schema(schema, columns=False):
    if not isinstance(schema, dict) or not isinstance(schema.get('fields'), list):
        raise ValidationError('A log template must define a fields array.')
    if not columns and (not isinstance(schema.get('method_reference'),str) or not schema['method_reference'].strip()):
        raise ValidationError('A calibration log template must identify its approved method reference.')
    names = set()
    for field in schema['fields']:
        name = field.get('name', '')
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,49}', name) or name in names:
            raise ValidationError('Template field names must be distinct lowercase identifiers.')
        names.add(name)
        if field.get('type') not in ('number', 'text', 'date', 'select'):
            raise ValidationError('Supported field types: number, text, date, select.')
        if field.get('type') == 'select' and not field.get('choices'):
            raise ValidationError('Select fields require choices.')
        if field.get('type') == 'select' and (not isinstance(field['choices'], list) or any(not isinstance(value, str) for value in field['choices'])):
            raise ValidationError('Select choices must be a list of text values.')
        for bound in ('min', 'max'):
            if bound in field and (not isinstance(field[bound], (int,float)) or not math.isfinite(field[bound])):
                raise ValidationError('Numerical field limits must be finite numbers.')
        if field.get('precision') is not None and (not isinstance(field['precision'],int) or not 0 <= field['precision'] <= 12):
            raise ValidationError('Decimal precision must be an integer from 0 to 12.')
    for table in schema.get('tables', []):
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,49}', table.get('name', '')) or table['name'] in names:
            raise ValidationError('Repeatable tables require unique lowercase identifiers.')
        names.add(table['name'])
        validate_schema({'fields': table.get('columns', [])}, columns=True)
    if not columns and not any(field.get('type')=='number' for field in schema['fields'] + [column for table in schema.get('tables',[]) for column in table.get('columns',[])]):
        raise ValidationError('A digital calibration template requires numerical measurement fields or repeatable readings.')
    if 'required_records' in schema and ('calibration' not in schema['required_records'] or any(x not in ('assessment', 'calibration', 'repair') for x in schema['required_records'])):
        raise ValidationError('Calibration scope requirements must include a calibration result and valid record types.')
    for formula in schema.get('formulas', []):
        result_name = formula.get('name','')
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,49}',result_name) or result_name in names:
            raise ValidationError('Calculated results require a unique identifier distinct from measured inputs.')
        names.add(result_name)
        expression = formula.get('expression', '')
        if len(expression) > 250 or '**' in expression:
            raise ValidationError('Formula is too complex; exponentiation is not supported in configurable templates.')
        try:
            evaluate_equation(expression, {field['name']:1 for field in schema['fields'] if field['type']=='number'})
        except (ValueError, SyntaxError, ArithmeticError):
            raise ValidationError('Formula must use configured numeric fields and safe arithmetic only.')
    return schema


def validate_record_data(record, data, complete=False):
    if not isinstance(data, dict) or len(json.dumps(data)) > 500000:
        raise ValidationError('Record data must be an object of at most 500 KB.')
    if record.kind == 'calibration' and data.get('calibration_phase', 'as_left') not in ('as_found', 'as_left'):
        raise ValidationError('Calibration phase must be As Found or As Left.')
    if record.kind == 'calibration' and record.source == 'digital':
        data.setdefault('calibration_phase', record.data.get('calibration_phase', 'as_left'))
        data.setdefault('method_reference', record.data.get('method_reference', ''))
        if not isinstance(data['method_reference'], str) or len(data['method_reference']) > 200:
            raise ValidationError('Method reference must be text of at most 200 characters.')
        expected_method = record.template.schema.get('method_reference')
        if expected_method and data['method_reference'] != expected_method:
            raise ValidationError('Use the approved method reference for this template version.')
        if complete and not str(data.get('method_reference', '')).strip():
            raise ValidationError('The calibration method reference must be recorded.')
        ids = data.get('reference_standards', [])
        if not isinstance(ids, list):
            raise ValidationError('Reference standards must be selected from the E&I equipment register.')
        standards = list(Primary.objects.filter(pk__in=ids, status='active',is_reference=True, scope=record.uut.scope))
        if len(standards) != len(set(map(str, ids))):
            raise ValidationError('One or more selected reference standards are inactive or outside the applicable E&I scope.')
        if complete and record.template.schema.get('requires_standards', True) and not standards:
            raise ValidationError('Select the actual reference standard(s) used for calibration.')
        data['reference_standards_snapshot'] = [{'id':s.pk, 'name':s.name, 'serial':s.serial_no, 'certificate':s.certificate_no,
            'calibrated':str(s.last_calibrated or ''), 'due':str(s.calibration_due_date or '')} for s in standards]
    if record.template_id:
        schema = record.template.schema
        def check(fields, values):
            for field in fields:
                name = field['name']; value = values.get(name)
                if value in (None, ''):
                    if complete and field.get('required'):
                        raise ValidationError(f'{field.get("label", name)} is required.')
                    continue
                if field['type'] == 'number':
                    try:
                        number = float(value)
                        if not math.isfinite(number) or ('min' in field and number < field['min']) or ('max' in field and number > field['max']):
                            raise ValueError()
                    except (ValueError, TypeError):
                        raise ValidationError(f'{name} must be a finite number within the configured limits.')
                    if 'precision' in field and field['precision'] is not None and max(0, -Decimal(str(value)).as_tuple().exponent) > int(field['precision']):
                        raise ValidationError(f'{name} exceeds the configured decimal precision.')
                elif field['type'] == 'date':
                    parse_date(value, name)
                elif field['type'] == 'text' and not isinstance(value, str):
                    raise ValidationError(f'{name} must be text.')
                elif field['type'] == 'select' and value not in field['choices']:
                    raise ValidationError(f'{name} is not an allowed choice.')
        check(schema.get('fields', []), data)
        for table in schema.get('tables', []):
            rows = data.get(table['name'], [])
            if not isinstance(rows, list) or len(rows) > 1000:
                raise ValidationError('Repeatable rows must be an array of at most 1000 rows.')
            if complete and table.get('required') and not rows:
                raise ValidationError(f'{table.get("label", table["name"])} requires at least one row.')
            for row in rows:
                if not isinstance(row, dict):
                    raise ValidationError('Each repeatable row must be an object.')
                check(table['columns'], row)
        for formula in schema.get('formulas', []):
            if all(data.get(field['name']) not in (None, '') for field in schema['fields'] if field['type'] == 'number'):
                try:
                    result = evaluate_equation(formula['expression'], {f['name']: data[f['name']] for f in schema['fields'] if f['type'] == 'number'})
                    if not math.isfinite(result):
                        raise ValidationError('The configured calculation exceeds finite numerical limits.')
                    data[formula['name']] = result
                except (ValueError, ArithmeticError, OverflowError):
                    if complete:
                        raise ValidationError('Configured formula cannot be calculated from these inputs.')
    if complete and record.source == 'digital' and record.kind == 'repair' and any(not str(data.get(k, '')).strip() for k in ('diagnosis', 'actions', 'parts', 'verification')):
        raise ValidationError('Repair records require diagnosis, actions, parts used and post-repair verification.')
    if complete and record.source == 'digital' and record.kind == 'assessment' and any(not str(data.get(k, '')).strip() for k in ('condition', 'as_found')):
        raise ValidationError('Assessment requires condition and as-found notes/results.')
    return data


@transaction.atomic
def start_record(user, uut, kind, source='digital', document=None, phase='as_left'):
    uut = JobUUT.objects.select_for_update().select_related('template').get(pk=uut.pk)
    require_work(user, uut)
    if kind == 'repair' and not has_perm(user, 'repair_equipment'):
        raise PermissionDenied('Repair-record permission is required.')
    if kind not in ('assessment', 'calibration', 'repair'):
        raise ValidationError('Choose assessment, calibration or repair.')
    if (kind == 'repair' and uut.request_type == 'calibration') or (kind == 'calibration' and uut.request_type == 'repair'):
        raise ValidationError('This record does not apply to the UUT request type.')
    if source not in ('digital', 'upload'):
        raise ValidationError('Choose digital entry or a hand-filled upload.')
    template = uut.template if kind == 'calibration' and source == 'digital' else None
    if kind == 'calibration' and source == 'digital' and (not template or template.status != 'approved'):
        raise ValidationError('Template Not Configured: select an approved scope template, or use an allowed hand-filled upload.')
    if source == 'upload' and not document:
        raise ValidationError('Upload a valid hand-filled document first.')
    if source == 'upload' and uut.template and uut.template.schema.get('allow_upload') is False:
        raise ValidationError('Hand-filled uploads are not allowed by the approved scope policy.')
    if source == 'digital':
        existing = TechnicalRecord.objects.filter(uut=uut, kind=kind, source=source, template=template, created_by=user, status='draft').first()
        if existing:
            return existing
    initial = {'calibration_phase': phase, 'method_reference':template.schema.get('method_reference', '') if template else ''} if kind == 'calibration' else {}
    if kind == 'calibration' and phase not in ('as_found', 'as_left'):
        raise ValidationError('Select As Found or As Left calibration phase.')
    record = TechnicalRecord.objects.create(uut=uut, kind=kind, source=source, template=template, document=document, data=initial, **actor_fields(user))
    audit(user, uut.job, 'technical_record_created', after={'record': record.pk, 'source': source, 'kind': kind}, uut=uut)
    return record


@transaction.atomic
def save_record(user, record, data, expected_version):
    record = TechnicalRecord.objects.select_for_update().get(pk=record.pk)
    require_work(user, record.uut)
    if record.kind == 'repair' and not has_perm(user, 'repair_equipment'):
        raise PermissionDenied('Repair-record permission is required.')
    if record.created_by_id != user.pk:
        raise PermissionDenied('Only this record author may edit the draft.')
    if record.status not in ('draft', 'rework'):
        raise ValidationError('Submitted/approved records are locked. Request controlled amendment.')
    if int(expected_version) != record.version:
        if validate_record_data(record, data) == record.data:
            return record
        raise Conflict('Another save changed this record. Your inputs are retained; reload or reconcile with the latest version.')
    record.data = validate_record_data(record, data)
    record.version += 1
    record.save()
    TechnicalRecordRevision.objects.create(record=record, version=record.version, data=record.data, **actor_fields(user))
    audit(user, record.uut.job, 'record_autosaved', after={'record': record.pk, 'version': record.version}, uut=record.uut)
    return record


@transaction.atomic
def transition_record(user, record, action, reason=''):
    record = TechnicalRecord.objects.select_for_update().get(pk=record.pk)
    activity = 'perform' if action == 'submit' else 'review' if action in ('review', 'reject') else 'approve'
    require_work(user, record.uut, activity)
    if action == 'submit' and record.kind == 'repair' and not has_perm(user, 'repair_equipment'):
        raise PermissionDenied('Repair-record permission is required.')
    previous = record.status
    if action == 'submit':
        if record.created_by_id != user.pk or record.status not in ('draft', 'rework'):
            raise PermissionDenied('Only the draft author may submit for review.')
        validate_record_data(record, record.data, complete=True)
        if record.kind == 'calibration' and record.uut.request_type == 'calibration_repair' and record.data.get('calibration_phase', 'as_left') == 'as_left':
            if not record.uut.technical_records.filter(kind='repair', status='approved').exists():
                raise ValidationError('Complete and approve the repair record before submitting the As Left calibration.')
        if record.source == 'upload' and not record.document_id:
            raise ValidationError('A hand-filled log file is required.')
        record.status = 'submitted'
    elif action in ('review', 'reject'):
        if record.created_by_id == user.pk and not settings.EI_ALLOW_SELF_APPROVAL:
            raise PermissionDenied('A separate authorized reviewer is required.')
        if record.status != 'submitted':
            raise ValidationError('Only submitted records can be reviewed.')
        if action == 'reject' and not reason.strip():
            raise ValidationError('A rework reason is required.')
        record.status = 'reviewed' if action == 'review' else 'rework'
        record.reviewed_by = user
        record.reviewed_at = timezone.now()
    elif action == 'approve':
        if record.created_by_id == user.pk and not settings.EI_ALLOW_SELF_APPROVAL:
            raise PermissionDenied('The author cannot approve their own technical record.')
        if record.status != 'reviewed':
            raise ValidationError('Technical review must precede approval.')
        record.status = 'approved'
        record.approved_by = user
        record.approved_at = timezone.now()
        if record.previous_id:
            TechnicalRecord.objects.filter(pk=record.previous_id).update(status='superseded')
    else:
        raise ValidationError('Unknown record action.')
    record.version += 1
    record.save()
    TechnicalRecordRevision.objects.create(record=record, version=record.version, data={'state': record.status, 'inputs': record.data}, reason=reason, **actor_fields(user))
    audit(user, record.uut.job, 'record_' + action, {'record': record.pk, 'status': previous},
        {'status': record.status, 'reason': reason,'authority_basis':'Chief/Admin role' if lab_authority(user) else 'Scope authorization'}, uut=record.uut)
    recipients = (list(get_users_with_perm('approve_calibration')) if record.status=='reviewed'
                  else list(get_users_with_perm('review_calibration')) if record.status=='submitted' else supervisors(record.uut.job))
    notify_job(record.uut.job, recipients + [record.created_by], f'{record.kind.title()} record {record.pk}: {record.status} by {user.get_full_name() or user.username}. {reason}')
    return record


@transaction.atomic
def amend_record(user, record, reason):
    record = TechnicalRecord.objects.select_for_update().get(pk=record.pk)
    require_work(user, record.uut, 'approve')
    if record.status != 'approved' or not reason.strip():
        raise ValidationError('An approved record and amendment reason are required.')
    existing = record.amendments.exclude(status='superseded').first()
    if existing:
        return existing
    new = TechnicalRecord.objects.create(uut=record.uut, kind=record.kind, source=record.source, template=record.template, data=record.data, document=record.document, legacy_calibration=record.legacy_calibration, legacy_assessment=record.legacy_assessment, previous=record, **actor_fields(user))
    audit(user, record.uut.job, 'controlled_amendment', after={'previous': record.pk, 'new': new.pk, 'reason': reason}, uut=record.uut)
    return new


@transaction.atomic
def close_uut(user, uut):
    uut = JobUUT.objects.select_for_update().select_related('job').get(pk=uut.pk)
    require_work(user, uut, 'approve')
    required = ['assessment'] + (['repair'] if uut.request_type in ('repair', 'calibration_repair') else []) + (['calibration'] if uut.request_type in ('calibration', 'calibration_repair') else [])
    if uut.template:
        required = list(set(uut.template.schema.get('required_records', required)) | ({'repair'} if uut.request_type in ('repair', 'calibration_repair') else set()) | ({'calibration'} if uut.request_type != 'repair' else set()))
    if not all(uut.technical_records.filter(kind=kind, status='approved').exists() for kind in required):
        raise ValidationError('All applicable UUT assessment, repair and calibration records must be approved before close-out.')
    if uut.request_type == 'calibration_repair' and not any(r.data.get('calibration_phase', 'as_left') == 'as_left' for r in uut.technical_records.filter(kind='calibration', status='approved')):
        raise ValidationError('Calibration and Repair requires an approved post-repair As Left calibration.')
    uut.status = 'completed'
    uut.save()
    audit(user, uut.job, 'uut_completed', after={'uut': str(uut.internal_id)}, uut=uut)
    job = Job.objects.select_for_update().get(pk=uut.job_id)
    if job.uuts.filter(archived=False).exists() and not job.uuts.filter(archived=False).exclude(status='completed').exists():
        job.progress_status = 'completed'
        job.completed_at = timezone.now()
        job.save()
        audit(user, job, 'job_completed', after={'actual_completion': job.completed_at.isoformat()})
        notify_job(job, job_recipients(job) + supervisors(job), f'Job {job.public_id} completed; all applicable UUT records approved.')
    return uut


def evaluate_clocks(now=None):
    now = now or timezone.now()
    cutoff = now - timedelta(hours=48)
    for job in Job.objects.filter(workflow_managed=True, approval_state='awaiting', progress_status='scheduled', submitted_at__lte=cutoff):
        with transaction.atomic():
            changed = Job.objects.filter(pk=job.pk, approval_state='awaiting', progress_status='scheduled').update(progress_status='pending')
            if changed:
                WorkflowAudit.objects.create(job=job, event='approval_48h_elapsed', created_by=None, actor_name='E&I workflow scheduler', after={'submitted_at': job.submitted_at.isoformat(), 'evaluated_at': now.isoformat(), 'originating_user':job.creator_id})
                notify_job(job, supervisors(job) + job_recipients(job), f'Job {job.public_id} remains awaiting approval after 48 elapsed hours; status is Pending.')
    today = timezone.localtime(now).date()
    for job in Job.objects.filter(workflow_managed=True, scheduled_end_date__lt=today).exclude(progress_status='completed').exclude(approval_state='draft').exclude(delay_notified_on=today):
        with transaction.atomic():
            claimed = Job.objects.filter(pk=job.pk).exclude(delay_notified_on=today).update(delay_notified_on=today)
            if claimed:
                notify_job(job, supervisors(job) + job_recipients(job), f'Job {job.public_id} is overdue (deadline {job.scheduled_end_date}). A delay reason and proposed revised date require supervisor approval.')
                WorkflowAudit.objects.create(job=job, event='overdue_notified', created_by=None, actor_name='E&I workflow scheduler', after={'deadline': str(job.scheduled_end_date), 'date': str(today), 'originating_user':job.creator_id})
