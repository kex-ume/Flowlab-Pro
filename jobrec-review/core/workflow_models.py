"""Additive E&I records; historical Job/Waybill/CalibrationLog keys are retained."""
import uuid
from django.db import models
from django.db.models import Q
from .private_storage import private_storage, private_upload


class ActorRecord(models.Model):
    created_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='+')
    actor_name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class AdminAccountLink(models.Model):
    flowlab_user_id = models.PositiveIntegerField(unique=True)
    user = models.OneToOneField('auth.User', on_delete=models.PROTECT, related_name='integrated_admin_link')
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
        constraints = [models.UniqueConstraint(fields=['target_type', 'object_id'], name='ei_admin_archive_target')]


class CalibrationLogTemplate(ActorRecord):
    scope = models.ForeignKey('core.CalibrationType', on_delete=models.PROTECT, related_name='log_templates')
    title = models.CharField(max_length=200)
    version = models.PositiveIntegerField()
    schema = models.JSONField(default=dict)
    status = models.CharField(max_length=12, default='draft', choices=[('draft', 'Draft'), ('approved', 'Approved'), ('retired', 'Retired')])
    approved_by = models.ForeignKey('auth.User', null=True, on_delete=models.PROTECT, related_name='+')
    approved_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['scope', 'version'], name='ei_template_scope_version')]
        ordering = ['scope_id', '-version']

    def __str__(self):
        return f'{self.title} · v{self.version} · {self.status}'


class JobUUT(models.Model):
    internal_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    job = models.ForeignKey('core.Job', on_delete=models.PROTECT, related_name='uuts')
    legacy_item = models.ForeignKey('core.WaybillItem', null=True, blank=True, on_delete=models.PROTECT, related_name='job_uuts')
    name = models.CharField(max_length=200)
    equipment_type = models.CharField(max_length=100, blank=True)
    manufacturer = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=100, blank=True)
    equipment_identifier = models.CharField(max_length=100, blank=True)
    duplicate_reason = models.TextField(blank=True)
    request_type = models.CharField(max_length=20, choices=[('calibration', 'Calibration'), ('repair', 'Repair'), ('calibration_repair', 'Calibration and Repair')])
    scope = models.ForeignKey('core.CalibrationType', null=True, blank=True, on_delete=models.PROTECT)
    template = models.ForeignKey(CalibrationLogTemplate, null=True, blank=True, on_delete=models.PROTECT)
    assigned_to = models.ForeignKey('core.Personnel', null=True, blank=True, on_delete=models.PROTECT)
    status = models.CharField(max_length=10, default='scheduled', choices=[('scheduled', 'Scheduled'), ('ongoing', 'Ongoing'), ('completed', 'Completed')])
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['pk']


class JobSubmission(ActorRecord):
    job = models.ForeignKey('core.Job', on_delete=models.PROTECT, related_name='submissions')
    sequence = models.PositiveIntegerField()
    snapshot = models.JSONField(default=dict)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['job', 'sequence'], name='ei_submission_sequence')]
        ordering = ['-sequence']


class JobReview(ActorRecord):
    submission = models.OneToOneField(JobSubmission,on_delete=models.PROTECT,related_name='review')
    branch = models.CharField(max_length=25)
    comment = models.TextField(blank=True)
    proposed_assignee = models.ForeignKey('core.Personnel',on_delete=models.PROTECT)


class JobDecision(ActorRecord):
    submission = models.OneToOneField(JobSubmission, on_delete=models.PROTECT, related_name='decision')
    branch = models.CharField(max_length=25, choices=[('sender', 'Approve and assign to sender'), ('comment', 'Approve with comment'), ('revert', 'Revert with comment'), ('another', 'Approve and assign to another user')])
    comment = models.TextField(blank=True)
    assignments = models.JSONField(default=list)


class JobScheduleRevision(ActorRecord):
    job = models.ForeignKey('core.Job', on_delete=models.PROTECT, related_name='schedule_revisions')
    previous_end_date = models.DateField()
    proposed_end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=12, default='pending', choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')])
    decided_by = models.ForeignKey('auth.User', null=True, on_delete=models.PROTECT, related_name='+')
    decided_at = models.DateTimeField(null=True)
    decision_comment = models.TextField(blank=True)


class JobDocument(ActorRecord):
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    job = models.ForeignKey('core.Job', on_delete=models.PROTECT, related_name='job_documents')
    uut = models.ForeignKey(JobUUT, null=True, blank=True, on_delete=models.PROTECT, related_name='documents')
    kind = models.CharField(max_length=30)
    title = models.CharField(max_length=200)
    original_name = models.CharField(max_length=200)
    file = models.FileField(storage=private_storage, upload_to=private_upload)
    mime_type = models.CharField(max_length=100)
    sha256 = models.CharField(max_length=64)
    revision = models.PositiveIntegerField(default=1)


class TechnicalRecord(ActorRecord):
    uut = models.ForeignKey(JobUUT, on_delete=models.PROTECT, related_name='technical_records')
    kind = models.CharField(max_length=20, choices=[('assessment', 'Pre-cal assessment'), ('calibration', 'Calibration log'), ('repair', 'Repair record'), ('uncertainty', 'Uncertainty link')])
    source = models.CharField(max_length=10, choices=[('digital', 'Digital'), ('upload', 'Hand-filled upload'), ('link', 'Existing record')])
    template = models.ForeignKey(CalibrationLogTemplate, null=True, blank=True, on_delete=models.PROTECT)
    data = models.JSONField(default=dict)
    document = models.ForeignKey(JobDocument, null=True, blank=True, on_delete=models.PROTECT)
    legacy_calibration = models.ForeignKey('core.CalibrationLog', null=True, blank=True, on_delete=models.PROTECT)
    legacy_assessment = models.ForeignKey('core.PreCalibrationLog', null=True, blank=True, on_delete=models.PROTECT)
    status = models.CharField(max_length=12, default='draft', choices=[('draft', 'Draft'), ('submitted', 'Submitted'), ('reviewed', 'Reviewed'), ('approved', 'Approved'), ('rework', 'Rework'), ('superseded', 'Superseded')])
    version = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_by = models.ForeignKey('auth.User', null=True, on_delete=models.PROTECT, related_name='+')
    reviewed_at = models.DateTimeField(null=True)
    approved_by = models.ForeignKey('auth.User', null=True, on_delete=models.PROTECT, related_name='+')
    approved_at = models.DateTimeField(null=True)
    previous = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='amendments')

    @property
    def uncertainty_result(self):
        return self.data.get('expanded_uncertainty')

    @property
    def uncertainty_unit(self):
        if self.data.get('unit'):
            return self.data['unit']
        if self.template_id:
            for field in self.template.schema.get('fields', []) + self.template.schema.get('formulas', []):
                if field.get('name') == 'expanded_uncertainty':
                    return field.get('unit', '')
        return ''

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['uut', 'kind', 'created_by', 'template'], condition=Q(status='draft', source='digital'), name='ei_one_open_digital_draft')]


class TechnicalRecordRevision(ActorRecord):
    record = models.ForeignKey(TechnicalRecord, on_delete=models.PROTECT, related_name='revisions')
    version = models.PositiveIntegerField()
    data = models.JSONField(default=dict)
    reason = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['record', 'version'], name='ei_record_revision_version')]


class PersonnelEvidence(ActorRecord):
    status = models.CharField(max_length=15, default='pending', choices=[('pending','Pending Review'),('verified','Verified'),('superseded','Superseded')])
    expires_on = models.DateField(null=True, blank=True)
    verified_by = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    verified_at = models.DateTimeField(null=True, blank=True)
    previous = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='revisions')
    personnel = models.ForeignKey('core.Personnel', on_delete=models.PROTECT, related_name='evidence')
    kind = models.CharField(max_length=25)
    title = models.CharField(max_length=200)
    details = models.JSONField(default=dict)
    file = models.FileField(storage=private_storage, upload_to=private_upload, blank=True)
    mime_type = models.CharField(max_length=100, blank=True)
    original_name = models.CharField(max_length=200, blank=True)


class PersonnelCompetency(ActorRecord):
    previous = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='revisions')
    personnel = models.ForeignKey('core.Personnel', on_delete=models.PROTECT, related_name='competencies')
    scope = models.ForeignKey('core.CalibrationType', on_delete=models.PROTECT)
    method_reference = models.CharField(max_length=150)
    assessed_on = models.DateField()
    expires_on = models.DateField(null=True, blank=True)
    result = models.CharField(max_length=10, choices=[('competent', 'Competent'), ('reassess', 'Reassessment required')])
    evidence = models.ForeignKey(PersonnelEvidence, null=True, blank=True, on_delete=models.PROTECT)


class PersonnelAuthorization(ActorRecord):
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspended_by = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    suspension_reason = models.TextField(blank=True)
    personnel = models.ForeignKey('core.Personnel', on_delete=models.PROTECT, related_name='authorizations')
    scope = models.ForeignKey('core.CalibrationType', null=True, blank=True, on_delete=models.PROTECT)
    activity = models.CharField(max_length=15, choices=[('perform', 'Perform'), ('review', 'Review'), ('approve', 'Approve'), ('supervise', 'Supervise')])
    method_reference = models.CharField(max_length=150, blank=True)
    effective_from = models.DateField()
    expires_on = models.DateField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    memo = models.ForeignKey(PersonnelEvidence, null=True, blank=True, on_delete=models.PROTECT)
    revoked_at = models.DateTimeField(null=True)
    revoked_by = models.ForeignKey('auth.User', null=True, on_delete=models.PROTECT, related_name='+')
    reason = models.TextField(blank=True)
    revocation_reason = models.TextField(blank=True)
    previous = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT)


class PersonnelProfileRevision(ActorRecord):
    personnel = models.ForeignKey('core.Personnel', on_delete=models.PROTECT, related_name='profile_history')
    snapshot = models.JSONField(default=dict)


class PersonnelCorrectionRequest(ActorRecord):
    personnel = models.ForeignKey('core.Personnel', on_delete=models.PROTECT, related_name='correction_requests')
    details = models.TextField()
    status = models.CharField(max_length=15, default='pending')
    resolution = models.TextField(blank=True)
    resolved_by = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.PROTECT, related_name='+')
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
    owner = models.ForeignKey('core.Personnel', on_delete=models.PROTECT, related_name='corrective_actions')
    job = models.ForeignKey('core.Job', null=True, blank=True, on_delete=models.PROTECT)
    issued_date = models.DateField()
    target_close_date = models.DateField()
    immediate_correction = models.TextField(blank=True)
    root_cause = models.TextField(blank=True)
    corrective_action = models.TextField(blank=True)
    effectiveness = models.TextField(blank=True)
    status = models.CharField(max_length=15,default='open',choices=[('open','Open'),('submitted','Closure Review'),('reverted','Reverted'),('closed','Closed')])
    reviewer = models.ForeignKey('auth.User',null=True,on_delete=models.PROTECT,related_name='+')
    submitted_by = models.ForeignKey('auth.User',null=True,on_delete=models.PROTECT,related_name='+')
    submitted_at = models.DateTimeField(null=True)
    approved_by = models.ForeignKey('auth.User',null=True,on_delete=models.PROTECT,related_name='+')
    closed_at = models.DateTimeField(null=True)
    review_comment = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=0)
    archived = models.BooleanField(default=False)


class CAPADocument(ActorRecord):
    record = models.ForeignKey(CAPARecord,on_delete=models.PROTECT,related_name='documents')
    kind = models.CharField(max_length=15,choices=[('issued','Issued NCR'),('closeout','Close-out report'),('supporting','Supporting evidence')])
    file = models.FileField(storage=private_storage,upload_to=private_upload)
    original_name = models.CharField(max_length=200)
    mime_type = models.CharField(max_length=100)


class EquipmentRecord(ActorRecord):
    equipment = models.ForeignKey('core.Primary',on_delete=models.PROTECT,related_name='retained_records')
    kind = models.CharField(max_length=15,choices=[('calibration','Calibration'),('maintenance','Maintenance')])
    performed_on = models.DateField()
    due_date = models.DateField(null=True,blank=True)
    details = models.JSONField(default=dict)
    file = models.FileField(storage=private_storage,upload_to=private_upload)
    original_name = models.CharField(max_length=200)
    mime_type = models.CharField(max_length=100)
    status = models.CharField(max_length=12,default='pending',choices=[('pending','Pending Review'),('approved','Approved'),('rejected','Rejected')])
    approved_by = models.ForeignKey('auth.User',null=True,on_delete=models.PROTECT,related_name='+')
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
