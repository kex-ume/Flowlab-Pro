"""Additive E&I records; historical Job/Waybill/CalibrationLog keys are retained."""
import uuid
from django.db import models
from django.db.models import Q, deletion
from .private_storage import private_storage, private_upload


class ActorRecord(models.Model):
    created_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='+')
    actor_name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class AdminAccountLink(models.Model):
    flowlab_user_id = models.PositiveIntegerField(unique=True)
    user = models.OneToOneField(related_name='integrated_admin_link', on_delete=deletion.PROTECT, to='auth.user')
    enabled = models.BooleanField(default=True)
    previous_role_id = models.PositiveIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class AdministrativeArchive(models.Model):
    target_type = models.CharField(max_length=40)
    object_id = models.PositiveIntegerField()
    previous_state = models.JSONField(default=dict)
    reason = models.TextField()
    actor_name = models.CharField(max_length=200)
    archived_at = models.DateTimeField(auto_now_add=True)
    restored_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=('target_type', 'object_id'), name='ei_admin_archive_target')]


class CalibrationLogTemplate(ActorRecord):
    title = models.CharField(max_length=200)
    version = models.PositiveIntegerField()
    schema = models.JSONField(default=dict)
    scope = models.ForeignKey(related_name='log_templates', on_delete=deletion.PROTECT, to='core.calibrationtype')
    status = models.CharField(max_length=12, default='draft', choices=[('draft', 'Draft'), ('approved', 'Approved'), ('retired', 'Retired')])
    approved_by = models.ForeignKey(null=True, related_name='+', on_delete=deletion.PROTECT, to='auth.user')
    approved_at = models.DateTimeField(null=True)

    class Meta:
        ordering = ['scope_id', '-version']
        constraints = [models.UniqueConstraint(fields=('scope', 'version'), name='ei_template_scope_version')]


class JobUUT(models.Model):
    internal_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(related_name='uuts', on_delete=deletion.PROTECT, to='core.job')
    scope = models.ForeignKey(blank=True, null=True, on_delete=deletion.PROTECT, to='core.calibrationtype')
    template = models.ForeignKey(blank=True, null=True, on_delete=deletion.PROTECT, to='core.calibrationlogtemplate')
    legacy_item = models.ForeignKey(blank=True, null=True, related_name='job_uuts', on_delete=deletion.PROTECT, to='core.waybillitem')
    name = models.CharField(max_length=200)
    equipment_type = models.CharField(max_length=100, blank=True)
    manufacturer = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=100, blank=True)
    equipment_identifier = models.CharField(max_length=100, blank=True)
    duplicate_reason = models.TextField(blank=True)
    request_type = models.CharField(max_length=20, choices=[('calibration', 'Calibration'), ('repair', 'Repair'), ('calibration_repair', 'Calibration and Repair')])
    status = models.CharField(max_length=10, default='scheduled', choices=[('scheduled', 'Scheduled'), ('ongoing', 'Ongoing'), ('completed', 'Completed')])
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    assigned_to = models.ForeignKey(blank=True, null=True, on_delete=deletion.PROTECT, to='core.personnel')

    class Meta:
        ordering = ['pk']


class JobSubmission(ActorRecord):
    job = models.ForeignKey(related_name='submissions', on_delete=deletion.PROTECT, to='core.job')
    sequence = models.PositiveIntegerField()
    snapshot = models.JSONField(default=dict)

    class Meta:
        ordering = ['-sequence']
        constraints = [models.UniqueConstraint(fields=('job', 'sequence'), name='ei_submission_sequence')]


class JobReview(ActorRecord):
    submission = models.OneToOneField(related_name='review', on_delete=deletion.PROTECT, to='core.jobsubmission')
    branch = models.CharField(max_length=25)
    comment = models.TextField(blank=True)
    proposed_assignee = models.ForeignKey(on_delete=deletion.PROTECT, to='core.personnel')


class JobDecision(ActorRecord):
    submission = models.OneToOneField(related_name='decision', on_delete=deletion.PROTECT, to='core.jobsubmission')
    branch = models.CharField(max_length=25, choices=[('sender', 'Approve and assign to sender'), ('comment', 'Approve with comment'), ('revert', 'Revert with comment'), ('another', 'Approve and assign to another user')])
    comment = models.TextField(blank=True)
    assignments = models.JSONField(default=list)


class JobScheduleRevision(ActorRecord):
    job = models.ForeignKey(related_name='schedule_revisions', on_delete=deletion.PROTECT, to='core.job')
    previous_end_date = models.DateField()
    proposed_end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=12, default='pending', choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')])
    decided_by = models.ForeignKey(null=True, related_name='+', on_delete=deletion.PROTECT, to='auth.user')
    decided_at = models.DateTimeField(null=True)
    decision_comment = models.TextField(blank=True)


class JobDocument(ActorRecord):
    job = models.ForeignKey(related_name='job_documents', on_delete=deletion.PROTECT, to='core.job')
    uut = models.ForeignKey(blank=True, null=True, related_name='documents', on_delete=deletion.PROTECT, to='core.jobuut')
    token = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=30)
    title = models.CharField(max_length=200)
    original_name = models.CharField(max_length=200)
    file = models.FileField(storage=private_storage, upload_to=private_upload)
    mime_type = models.CharField(max_length=100)
    sha256 = models.CharField(max_length=64)
    revision = models.PositiveIntegerField(default=1)


class TechnicalRecord(ActorRecord):
    uut = models.ForeignKey(related_name='technical_records', on_delete=deletion.PROTECT, to='core.jobuut')
    template = models.ForeignKey(blank=True, null=True, on_delete=deletion.PROTECT, to='core.calibrationlogtemplate')
    document = models.ForeignKey(blank=True, null=True, on_delete=deletion.PROTECT, to='core.jobdocument')
    legacy_calibration = models.ForeignKey(blank=True, null=True, on_delete=deletion.PROTECT, to='core.calibrationlog')
    legacy_assessment = models.ForeignKey(blank=True, null=True, on_delete=deletion.PROTECT, to='core.precalibrationlog')
    previous = models.ForeignKey(blank=True, null=True, related_name='amendments', on_delete=deletion.PROTECT, to='core.technicalrecord')
    kind = models.CharField(max_length=20, choices=[('assessment', 'Pre-cal assessment'), ('calibration', 'Calibration log'), ('repair', 'Repair record'), ('uncertainty', 'Uncertainty link')])
    source = models.CharField(max_length=10, choices=[('digital', 'Digital'), ('upload', 'Hand-filled upload'), ('link', 'Existing record')])
    data = models.JSONField(default=dict)
    status = models.CharField(max_length=12, default='draft', choices=[('draft', 'Draft'), ('submitted', 'Submitted'), ('reviewed', 'Reviewed'), ('approved', 'Approved'), ('rework', 'Rework'), ('superseded', 'Superseded')])
    version = models.PositiveIntegerField(default=0)
    reviewed_by = models.ForeignKey(null=True, related_name='+', on_delete=deletion.PROTECT, to='auth.user')
    reviewed_at = models.DateTimeField(null=True)
    approved_by = models.ForeignKey(null=True, related_name='+', on_delete=deletion.PROTECT, to='auth.user')
    approved_at = models.DateTimeField(null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=('uut', 'kind', 'created_by', 'template'), condition=Q(source='digital') & Q(status='draft'), name='ei_one_open_digital_draft')]


class TechnicalRecordRevision(ActorRecord):
    record = models.ForeignKey(related_name='revisions', on_delete=deletion.PROTECT, to='core.technicalrecord')
    version = models.PositiveIntegerField()
    data = models.JSONField(default=dict)
    reason = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=('record', 'version'), name='ei_record_revision_version')]


class PersonnelEvidence(ActorRecord):
    personnel = models.ForeignKey(related_name='evidence', on_delete=deletion.PROTECT, to='core.personnel')
    previous = models.ForeignKey(blank=True, null=True, related_name='revisions', on_delete=deletion.PROTECT, to='core.personnelevidence')
    kind = models.CharField(max_length=25)
    title = models.CharField(max_length=200)
    details = models.JSONField(default=dict)
    file = models.FileField(storage=private_storage, upload_to=private_upload, blank=True)
    mime_type = models.CharField(max_length=100, blank=True)
    original_name = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=15, default='pending', choices=[('pending', 'Pending Review'), ('verified', 'Verified'), ('superseded', 'Superseded')])
    verified_by = models.ForeignKey(blank=True, null=True, related_name='+', on_delete=deletion.PROTECT, to='auth.user')
    verified_at = models.DateTimeField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)


class PersonnelCompetency(ActorRecord):
    personnel = models.ForeignKey(related_name='competencies', on_delete=deletion.PROTECT, to='core.personnel')
    scope = models.ForeignKey(on_delete=deletion.PROTECT, to='core.calibrationtype')
    evidence = models.ForeignKey(blank=True, null=True, on_delete=deletion.PROTECT, to='core.personnelevidence')
    previous = models.ForeignKey(blank=True, null=True, related_name='revisions', on_delete=deletion.PROTECT, to='core.personnelcompetency')
    method_reference = models.CharField(max_length=150)
    assessed_on = models.DateField()
    expires_on = models.DateField(null=True, blank=True)
    result = models.CharField(max_length=10, choices=[('competent', 'Competent'), ('reassess', 'Reassessment required')])


class PersonnelAuthorization(ActorRecord):
    personnel = models.ForeignKey(related_name='authorizations', on_delete=deletion.PROTECT, to='core.personnel')
    scope = models.ForeignKey(blank=True, null=True, on_delete=deletion.PROTECT, to='core.calibrationtype')
    memo = models.ForeignKey(blank=True, null=True, on_delete=deletion.PROTECT, to='core.personnelevidence')
    previous = models.ForeignKey(blank=True, null=True, on_delete=deletion.PROTECT, to='core.personnelauthorization')
    activity = models.CharField(max_length=15, choices=[('perform', 'Perform'), ('review', 'Review'), ('approve', 'Approve'), ('supervise', 'Supervise')])
    method_reference = models.CharField(max_length=150, blank=True)
    effective_from = models.DateField()
    expires_on = models.DateField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    reason = models.TextField(blank=True)
    revoked_by = models.ForeignKey(null=True, related_name='+', on_delete=deletion.PROTECT, to='auth.user')
    revoked_at = models.DateTimeField(null=True)
    revocation_reason = models.TextField(blank=True)
    suspended_by = models.ForeignKey(blank=True, null=True, related_name='+', on_delete=deletion.PROTECT, to='auth.user')
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.TextField(blank=True)


class PersonnelProfileRevision(ActorRecord):
    personnel = models.ForeignKey(related_name='profile_history', on_delete=deletion.PROTECT, to='core.personnel')
    snapshot = models.JSONField(default=dict)


class PersonnelCorrectionRequest(ActorRecord):
    personnel = models.ForeignKey(related_name='correction_requests', on_delete=deletion.PROTECT, to='core.personnel')
    details = models.TextField()
    status = models.CharField(max_length=15, default='pending')
    resolution = models.TextField(blank=True)
    resolved_by = models.ForeignKey(blank=True, null=True, related_name='+', on_delete=deletion.PROTECT, to='auth.user')
    resolved_at = models.DateTimeField(null=True, blank=True)


class PersonnelReviewReminder(models.Model):
    key = models.CharField(max_length=150, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)


class CAPARecord(ActorRecord):
    ncr_number = models.CharField(max_length=60, unique=True)
    title = models.CharField(max_length=200)
    source = models.CharField(max_length=100)
    clause_reference = models.CharField(max_length=100, blank=True)
    description = models.TextField()
    job = models.ForeignKey(blank=True, null=True, on_delete=deletion.PROTECT, to='core.job')
    owner = models.ForeignKey(related_name='corrective_actions', on_delete=deletion.PROTECT, to='core.personnel')
    issued_date = models.DateField()
    target_close_date = models.DateField()
    immediate_correction = models.TextField(blank=True)
    root_cause = models.TextField(blank=True)
    corrective_action = models.TextField(blank=True)
    effectiveness = models.TextField(blank=True)
    status = models.CharField(max_length=15, default='open', choices=[('open', 'Open'), ('submitted', 'Closure Review'), ('reverted', 'Reverted'), ('closed', 'Closed')])
    reviewer = models.ForeignKey(null=True, related_name='+', on_delete=deletion.PROTECT, to='auth.user')
    submitted_by = models.ForeignKey(null=True, related_name='+', on_delete=deletion.PROTECT, to='auth.user')
    submitted_at = models.DateTimeField(null=True)
    approved_by = models.ForeignKey(null=True, related_name='+', on_delete=deletion.PROTECT, to='auth.user')
    closed_at = models.DateTimeField(null=True)
    review_comment = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=0)
    archived = models.BooleanField(default=False)


class CAPADocument(ActorRecord):
    record = models.ForeignKey(related_name='documents', on_delete=deletion.PROTECT, to='core.caparecord')
    kind = models.CharField(max_length=15, choices=[('issued', 'Issued NCR'), ('closeout', 'Close-out report'), ('supporting', 'Supporting evidence')])
    file = models.FileField(storage=private_storage, upload_to=private_upload)
    original_name = models.CharField(max_length=200)
    mime_type = models.CharField(max_length=100)


class EquipmentRecord(ActorRecord):
    equipment = models.ForeignKey('core.Primary', on_delete=models.PROTECT, related_name='retained_records')
    kind = models.CharField(max_length=15, choices=[('calibration', 'Calibration'), ('maintenance', 'Maintenance')])
    performed_on = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    details = models.JSONField(default=dict)
    file = models.FileField(storage=private_storage, upload_to=private_upload)
    original_name = models.CharField(max_length=200)
    mime_type = models.CharField(max_length=100)
    status = models.CharField(max_length=12, default='pending', choices=[('pending', 'Pending Review'), ('approved', 'Approved'), ('rejected', 'Rejected')])
    approved_by = models.ForeignKey('auth.User', null=True, on_delete=models.PROTECT, related_name='+')
    approved_at = models.DateTimeField(null=True)
    review_comment = models.TextField(blank=True)


class WorkflowAudit(ActorRecord):
    created_by = models.ForeignKey('auth.User', null=True, on_delete=models.PROTECT, related_name='+')
    job = models.ForeignKey('core.Job', null=True, blank=True, on_delete=models.PROTECT, related_name='workflow_audit')
    uut = models.ForeignKey(JobUUT, null=True, blank=True, on_delete=models.PROTECT)
    event = models.CharField(max_length=60)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)

    class Meta:
        ordering = ['-created_at', '-pk']


class EquipmentCertificateTemplate(ActorRecord):
    """A per-equipment-group template: defines the test-table columns of its log records."""
    name = models.CharField(max_length=150, unique=True)
    original_name = models.CharField(max_length=200, blank=True, default='')
    original_file = models.FileField(storage=private_storage, upload_to=private_upload, null=True, blank=True)
    activities = models.JSONField(default=list, help_text='Activities-log field labels, in sheet order (e.g. Equipment Owner, Manufacturer, Serial/Tag Number)')
    columns = models.JSONField(default=list, help_text='Test-data table column names, in sheet order')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'equipment certificate templates'

    def __str__(self):
        return self.name


class EquipmentCertificateRecord(ActorRecord):
    PASS_FAIL = [('pass', 'Pass'), ('fail', 'Fail')]

    template = models.ForeignKey(EquipmentCertificateTemplate, on_delete=models.PROTECT, related_name='records')
    template_name = models.CharField(max_length=150, blank=True, default='')
    serial_no = models.CharField(max_length=100, db_index=True)
    year = models.PositiveIntegerField(db_index=True)
    model = models.CharField(max_length=150, blank=True, default='')
    certificate_no = models.CharField(max_length=100, blank=True, default='')
    test_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    environment = models.CharField(max_length=200, blank=True, default='')
    conclusion = models.CharField(max_length=4, choices=PASS_FAIL, blank=True, default='')
    columns = models.JSONField(default=list)
    rows = models.JSONField(default=list)
    field_values = models.JSONField(default=dict, help_text='Activities-log values keyed by slugified label')
    updated_at = models.DateTimeField(auto_now=True)
    change_history = models.JSONField(default=list)

    class Meta:
        ordering = ['-year', 'template_name', 'serial_no']
        unique_together = [('template', 'serial_no', 'year')]

    def __str__(self):
        return f'{self.serial_no} · {self.template_name} · {self.year}'
