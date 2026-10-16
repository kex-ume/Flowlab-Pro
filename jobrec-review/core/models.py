from datetime import date
from decimal import Decimal
import uuid

from django.db import models, transaction
from django.db.models import Max
from django.contrib.auth.models import User
from django.utils import timezone


def abbreviation_for(explicit, name):
    """Return the explicit abbreviation, else derive 3-4 letters from name, else '-'."""
    explicit = (explicit or '').strip()
    if explicit:
        return explicit.upper()
    words = [w for w in ''.join(c if c.isalpha() else ' ' for c in (name or '')).split()]
    if not words:
        return '-'
    if len(words) >= 3:
        derived = ''.join(w[0] for w in words[:4]).upper()
    else:
        joined = ''.join(words)
        derived = (joined[:3] if len(joined) >= 3 else joined.ljust(3, joined[-1])).upper()
    return derived or '-'


class Client(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('pending_info', 'Pending Info'),
        ('inactive', 'Inactive'),
    ]

    name = models.CharField(max_length=200)
    abbreviation = models.CharField(
        max_length=10, blank=True, default='',
        help_text='Short code used in certificate numbers (e.g. ABC). Entered at client setup; derived from the name when left blank.'
    )
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Waybill(models.Model):
    WAYBILL_TYPE_CHOICES = [
        ('incoming', 'Incoming'),
        ('outgoing', 'Outgoing'),
    ]

    waybill_no = models.CharField(max_length=50, unique=True)
    waybill_type = models.CharField(max_length=10, choices=WAYBILL_TYPE_CHOICES)
    file_upload = models.FileField(upload_to='waybills/', blank=True, null=True)
    linked_incoming_waybill = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='outgoing_waybills'
    )
    job = models.ForeignKey(
        'Job', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='waybills', help_text='Job this outgoing waybill belongs to.'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.waybill_no} ({self.get_waybill_type_display()})"

    class Meta:
        ordering = ['-created_at']


class WaybillItem(models.Model):
    WAYBILL_ITEM_STATUS_CHOICES = [
        ('pre_cal_pending', 'Pre-Cal Pending'),
        ('cal_pending', 'Cal Pending'),
        ('result_pending', 'Result Pending'),
        ('repair_due', 'Repair Due'),
        ('completed', 'Completed'),
        ('dispatched', 'Dispatched'),
    ]

    waybill = models.ForeignKey(Waybill, on_delete=models.CASCADE, related_name='items')
    equipment_description = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField()
    serial_no = models.CharField(max_length=50)
    model_no = models.CharField(max_length=50, blank=True, null=True)
    manufacturer = models.CharField(max_length=100, blank=True, null=True)
    range_field = models.CharField(max_length=100, blank=True, null=True, verbose_name='Range')
    scope = models.ForeignKey('CalibrationType', on_delete=models.SET_NULL, null=True, blank=True, related_name='waybill_items')
    status = models.CharField(max_length=20, choices=WAYBILL_ITEM_STATUS_CHOICES, default='pre_cal_pending')

    def __str__(self):
        return f"{self.equipment_description} ({self.serial_no})"

    @property
    def latest_log_status(self):
        log = self.calibration_logs.order_by('-created_at').first()
        return log.status if log else None


class Location(models.Model):
    name = models.CharField(max_length=200, unique=True)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class CalibrationType(models.Model):
    active = models.BooleanField(default=True)
    name = models.CharField(max_length=100, unique=True)
    abbreviation = models.CharField(
        max_length=10, blank=True, default='',
        help_text='Short code used in certificate numbers (e.g. PCAL for Pressure Calibration). Set at scope setup.'
    )
    description = models.TextField(blank=True, null=True)
    certificate_format = models.CharField(
        max_length=100, blank=True, default='',
        help_text='Certificate numbering template override for this scope. Placeholders: {company_abbr} {client_abbr} {scope_abbr} {seq} {year}. Blank = use the global template.'
    )
    validity_months = models.PositiveIntegerField(
        default=12, help_text='Calibration validity period in months; certificate due date = calibration date + this.'
    )
    instrument_column_label = models.CharField(
        max_length=100, blank=True, default='Instrument Reading',
        help_text='Column label for the instrument reading in the calibration table for this scope.'
    )
    uut_column_label = models.CharField(
        max_length=100, blank=True, default='UUT Reading',
        help_text='Column label for the UUT reading in the calibration table for this scope.'
    )
    error_column_label = models.CharField(
        max_length=100, blank=True, default='Error',
        help_text='Column label for the error in the calibration table for this scope.'
    )
    certificate_template = models.TextField(
        blank=True, default='',
        help_text=(
            'Custom Django template overriding the certificate layout for this scope. '
            'Blank = use the default two-page certificate. Edited in Settings → Scopes.'
        )
    )

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Permission(models.Model):
    codename = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['codename']


class Role(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')
    permissions = models.ManyToManyField(Permission, blank=True, related_name='roles')

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Personnel(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='personnel_profile')
    name = models.CharField(max_length=200)
    position = models.CharField(max_length=120, blank=True, default='')
    department = models.CharField(max_length=120, blank=True, default='')
    employment_status = models.CharField(max_length=20, default='active', choices=[('active', 'Active'), ('inactive', 'Inactive')])
    contact_phone = models.CharField(max_length=40, blank=True, default='')
    experience_as_of = models.DateField(null=True, blank=True)
    verification_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name='personnel', null=True)
    location_text = models.CharField(max_length=200, blank=True, default='')
    qualifications = models.TextField()
    years_of_experience = models.PositiveIntegerField()
    scope_of_expertise = models.ManyToManyField(CalibrationType, related_name='personnel', blank=True)
    signature = models.ImageField(
        upload_to='signatures/', null=True, blank=True,
        help_text='Uploaded signature image, auto-applied to calibration logs this user creates or approves.'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def signature_url(self):
        return self.signature.url if self.signature else ''

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Personnel'


class Job(models.Model):
    administratively_archived = models.BooleanField(default=False)
    JOB_TYPE_CHOICES = [('lab', 'Lab'), ('field', 'Field')]
    REQUEST_TYPE_CHOICES = [
        ('calibration', 'Calibration'),
        ('repair', 'Repair'),
        ('calibration_repair', 'Calibration and Repair'),
    ]
    JOB_STATUS_CHOICES = [
        ('not_received', 'Not Received'),
        ('pre_calibration_pending', 'Pre-calibration Pending'),
        ('calibration_pending', 'Calibration Pending'),
        ('review_pending', 'Review Pending'),
        ('approval_pending', 'Approval Pending'),
        ('repair_due', 'Repair Due'),
        ('completed', 'Completed'),
        ('dispatched', 'Dispatched'),
    ]

    INVOICE_STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
    ]

    purchase_order_number = models.CharField(max_length=50, unique=True, blank=True, null=True, verbose_name='Purchase Order Number')
    serial_no = models.CharField(max_length=50)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='jobs')
    job_description = models.TextField()
    job_type = models.CharField(max_length=10, choices=JOB_TYPE_CHOICES, default='lab')
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPE_CHOICES, default='calibration')
    received_started_date = models.DateField(null=True, blank=True)
    scheduled_end_date = models.DateField(null=True, blank=True)
    delay_remark = models.TextField(blank=True, default='')
    delay_notified_on = models.DateField(null=True, blank=True)
    record_status_override = models.CharField(max_length=10, blank=True, default='', choices=[('scheduled', 'Scheduled'), ('pending', 'Pending'), ('ongoing', 'Ongoing')])
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    creation_key = models.UUIDField(null=True, blank=True, unique=True)
    workflow_managed = models.BooleanField(default=False)
    creator = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='ei_created_jobs')
    progress_status = models.CharField(max_length=10, default='scheduled', choices=[('scheduled', 'Scheduled'), ('pending', 'Pending'), ('ongoing', 'Ongoing'), ('completed', 'Completed')])
    approval_state = models.CharField(max_length=15, default='legacy', choices=[('legacy', 'Historical'), ('draft', 'Draft'), ('awaiting', 'Awaiting Approval'), ('approved', 'Approved'), ('reverted', 'Changes Required')])
    planned_start_date = models.DateField(null=True, blank=True)
    original_end_date = models.DateField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    commenced_at = models.DateTimeField(null=True, blank=True)
    commenced_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='ei_commenced_jobs')
    completed_at = models.DateTimeField(null=True, blank=True)
    primary_assignee = models.ForeignKey(Personnel, null=True, blank=True, on_delete=models.PROTECT, related_name='ei_responsible_jobs')
    suggested_personnel = models.ManyToManyField(Personnel, blank=True, related_name='suggested_ei_jobs')
    suggested_primary = models.ForeignKey(Personnel, null=True, blank=True, on_delete=models.PROTECT, related_name='suggested_primary_ei_jobs')
    supervisor = models.ForeignKey(Personnel, null=True, blank=True, on_delete=models.PROTECT, related_name='ei_supervised_jobs')
    lock_version = models.PositiveIntegerField(default=0)
    incoming_waybill = models.ForeignKey(
        Waybill, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='incoming_jobs'
    )
    job_status = models.CharField(max_length=30, choices=JOB_STATUS_CHOICES, default='not_received')
    invoice_status = models.CharField(max_length=20, choices=INVOICE_STATUS_CHOICES, default='unpaid')
    assigned_to = models.ManyToManyField(Personnel, blank=True, related_name='assigned_jobs')
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        po = self.purchase_order_number or "No PO"
        return f"{po} - {self.client.name}"

    @property
    def job_code(self):
        return f'EI-JOB-{self.pk:06d}'

    @property
    def request_type_label(self):
        if self.workflow_managed:
            types = {x.request_type for x in self.uuts.all() if not x.archived}
            return 'Mixed' if len(types) > 1 else dict(self.REQUEST_TYPE_CHOICES).get(next(iter(types), ''), 'Not recorded')
        return self.get_request_type_display()

    @property
    def record_status(self):
        if self.workflow_managed:
            return self.progress_status
        if self.job_status in ('completed', 'dispatched'):
            return 'completed'
        if self.job_status not in ('not_received', 'pre_calibration_pending'):
            return 'ongoing'
        if self.record_status_override:
            return self.record_status_override
        if self.job_status == 'not_received':
            return 'pending' if self.incoming_waybill_id else 'scheduled'
        return 'pending'

    @property
    def is_overdue(self):
        return bool(self.scheduled_end_date and self.scheduled_end_date < timezone.localdate()
                    and self.record_status != 'completed')

    def _item_stage(self, item):
        """Map a single equipment item to a job-stage key by consulting its
        latest calibration-log status (when one exists)."""
        if item.status == 'repair_due':
            return 'repair'
        if item.status in ('completed', 'dispatched'):
            return 'terminal'
        if item.status == 'result_pending':
            log = item.calibration_logs.order_by('-created_at').first()
            if log:
                if log.status == 'pending_review':
                    return 'review'
                if log.status in ('pending_approval', 'pending_qhse', 'approved'):
                    return 'approval'
                if log.status == 'rejected':
                    return 'review'
            return 'review'
        if item.status in ('cal_pending', 'completed'):
            return 'calibration'
        return 'pre_calibration'

    def derive_status_from_items(self):
        """Derive the Job status from the collective state of its incoming
        waybill's equipment items (or None if the job has no items yet).

        Per-item stage comes from `_item_stage` (cal-log aware). The job is
        pushed to the furthest incomplete stage among its items."""
        if not self.incoming_waybill:
            return None
        stages = [self._item_stage(item) for item in self.incoming_waybill.items.all()]
        if not stages:
            return None
        if 'repair' in stages and not all(s == 'terminal' for s in stages):
            return 'repair_due'
        if all(s == 'terminal' for s in stages):
            return 'dispatched' if all(i.status == 'dispatched' for i in self.incoming_waybill.items.all()) else 'completed'
        if 'approval' in stages:
            return 'approval_pending'
        if 'review' in stages:
            return 'review_pending'
        if 'calibration' in stages:
            return 'calibration_pending'
        return 'pre_calibration_pending'

    def reconcile_status(self):
        """Bring the job status in line with its equipment progression.

        Non-terminal jobs are snapped to the derived status (so a rejected
        log pulls the job back to review_pending, etc.). A `completed` or
        `dispatched` job is terminal and never regresses."""
        if self.workflow_managed:
            # Managed jobs close only through their approved per-UUT worklist.
            return
        derived = self.derive_status_from_items()
        if derived is None:
            return
        if self.job_status in ('completed', 'dispatched'):
            return
        if self.job_status != derived:
            self.job_status = derived
            self.save(update_fields=['job_status'])

    class Meta:
        ordering = ['-created_at']


# ─── Primary equipment (company's reference / calibration standards) ─────────

class Primary(models.Model):
    asset_number = models.CharField(max_length=100,unique=True,null=True,blank=True)
    equipment_type = models.CharField(max_length=100,blank=True)
    laboratory_location = models.CharField(max_length=150,blank=True)
    is_reference = models.BooleanField(default=True)
    include_programme = models.BooleanField(default=True)
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('pending_maintenance', 'Pending Maintenance'),
        ('inactive', 'Inactive'),
    ]

    name = models.CharField(max_length=200)
    serial_no = models.CharField(max_length=50, blank=True)
    certificate_no = models.CharField(
        max_length=50, blank=True, default='',
        help_text="Certificate number of this standard's own calibration (shown in the certificate traceability table)."
    )
    manufacturer = models.CharField(max_length=100, blank=True)
    model_no = models.CharField(max_length=50, blank=True)
    scope = models.ForeignKey(CalibrationType, on_delete=models.SET_NULL, null=True, blank=True, related_name='primaries')
    unit = models.ForeignKey(
        'Unit', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='primaries',
        help_text='Primary unit of measurement of this reference standard (first of `units`; e.g. bar, °C).'
    )
    units = models.ManyToManyField(
        'Unit', blank=True, related_name='primaries_m2m',
        help_text='Unit(s) of measurement this reference standard serves. A rich digital pressure calibrator '
                  'can serve several units (bar, psi, MPa); the legacy `unit` FK mirrors the first.'
    )
    range_min = models.CharField(
        max_length=40, blank=True, default='',
        help_text='Minimum of this standard\'s calibrated range (numeric, e.g. 0.0).'
    )
    range_max = models.CharField(
        max_length=40, blank=True, default='',
        help_text='Maximum of this standard\'s calibrated range (numeric, e.g. 100).'
    )
    purchase_date = models.DateField(blank=True, null=True)
    calibration_frequency = models.PositiveIntegerField(default=12, help_text='Recalibration interval in months')
    last_calibrated = models.DateField(blank=True, null=True)
    calibration_due_date = models.DateField(blank=True, null=True, help_text='Next recalibration due date')
    operating_temp_min = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, help_text='Minimum operating temperature (°C)')
    operating_temp_max = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, help_text='Maximum operating temperature (°C)')
    operating_humidity_min = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, help_text='Minimum operating humidity (%)')
    operating_humidity_max = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, help_text='Maximum operating humidity (%)')
    standard_uncertainty = models.DecimalField(max_digits=8, decimal_places=4, blank=True, null=True, help_text='Combined standard uncertainty u_std (in %) used in the uncertainty budget')
    coverage_factor = models.DecimalField(max_digits=5, decimal_places=2, default=2.00, help_text='Coverage factor k (typically 2 for ~95% confidence)')
    tolerance = models.DecimalField(max_digits=8, decimal_places=4, blank=True, null=True, help_text='Acceptance tolerance (in %) used to judge the expanded uncertainty')
    uncertainty_equation = models.CharField(
        max_length=200, blank=True, default='',
        help_text='Uncertainty budget equation. Variables: k, u_std, error_max (alias error_pct_max), tolerance. Example: k * sqrt(u_std**2 + error_max**2)'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.serial_no})"

    @property
    def is_due(self):
        return bool(self.calibration_due_date and self.calibration_due_date <= date.today())

    @property
    def due_in_days(self):
        if not self.calibration_due_date:
            return None
        return (self.calibration_due_date - date.today()).days

    @property
    def range_bounds(self):
        try:
            if self.range_min and self.range_max:
                return (float(self.range_min), float(self.range_max))
        except (TypeError, ValueError):
            return None
        return None

    def contains_range(self, lo, hi):
        """True when this standard's calibrated range fully contains [lo, hi].

        Standards without numeric bounds are treated as compatible (allow),
        so pre-existing data never blocks matching."""
        b = self.range_bounds
        if b is None or lo is None or hi is None:
            return True
        return bool(b[0] <= lo and hi <= b[1])

    def environment_conforms(self, temperature=None, humidity=None):
        """Compare environment values against this primary's operating envelope.

        Returns a dict with overall conformity and per-variable results, or None
        when no operating limits are defined.
        """
        has_limits = (
            self.operating_temp_min is not None or self.operating_temp_max is not None
            or self.operating_humidity_min is not None or self.operating_humidity_max is not None
        )
        if not has_limits:
            return None

        results = {}
        if temperature is not None:
            t = float(temperature)
            if self.operating_temp_min is not None and self.operating_temp_max is not None:
                ok = self.operating_temp_min <= t <= self.operating_temp_max
                results['temperature'] = {
                    'ok': ok,
                    'value': t,
                    'min': float(self.operating_temp_min),
                    'max': float(self.operating_temp_max),
                }
        if humidity is not None:
            h = float(humidity)
            if self.operating_humidity_min is not None and self.operating_humidity_max is not None:
                ok = self.operating_humidity_min <= h <= self.operating_humidity_max
                results['humidity'] = {
                    'ok': ok,
                    'value': h,
                    'min': float(self.operating_humidity_min),
                    'max': float(self.operating_humidity_max),
                }
        return {
            'conforms': all(r['ok'] for r in results.values()) if results else None,
            'variables': results,
        }


class EnvironmentRecord(models.Model):
    TIME_CHOICES = [
        ('08', '08:00 Hrs'),
        ('12', '12:00 Hrs'),
        ('17', '17:00 Hrs'),
    ]

    date = models.DateField()
    time = models.CharField(max_length=2, choices=TIME_CHOICES)
    relative_humidity = models.DecimalField(max_digits=5, decimal_places=2)
    temperature = models.DecimalField(max_digits=5, decimal_places=2)
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    doc_no = models.CharField(
        max_length=50, blank=True, default='',
        help_text='Lab accreditation document number (ENV-{lab}-{year}-{seq:04d}).'
    )
    doc_seq = models.PositiveIntegerField(null=True, blank=True, help_text='Sequence within the per-year environment register.')

    def build_doc_no(self):
        year = self.date.year
        lab = abbreviation_for(None, self.location.name) if self.location_id else ''
        seq = self.doc_seq if self.doc_seq is not None else (self.pk or 0)
        suffix = seq if self.location_id else (self.pk or 0)
        if lab:
            return f'ENV-{lab}-{year}-{suffix:04d}'
        return f'ENV-{year}-{seq:04d}'

    def assign_doc_no(self):
        if self.doc_no:
            return False
        with transaction.atomic():
            locked = type(self).objects.select_for_update().filter(
                date__year=self.date.year, location=self.location,
                doc_no__gt='', doc_seq__isnull=False,
            ).aggregate(m=Max('doc_seq'))['m'] or 0
            self.doc_seq = locked + 1
            self.doc_no = self.build_doc_no()
            self.save(update_fields=['doc_no', 'doc_seq'])
        return True

    class Meta:
        unique_together = ['location', 'date', 'time']
        ordering = ['-date', '-time']

    def __str__(self):
        lab = f" ({self.location.name})" if self.location_id else ""
        return f"{self.date} {self.get_time_display()}{lab} - {self.temperature}\u00b0C, {self.relative_humidity}%"


class EnvironmentReminder(models.Model):
    date = models.DateField()
    time = models.CharField(max_length=2, choices=EnvironmentRecord.TIME_CHOICES)
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True)
    is_recorded = models.BooleanField(default=False)
    recorded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['location', 'date', 'time']
        ordering = ['-date', '-time']

    def __str__(self):
        status = "Recorded" if self.is_recorded else "Pending"
        lab = f" ({self.location.name})" if self.location_id else ""
        return f"{self.date} {self.get_time_display()}{lab} - {status}"


class PreCalibrationLog(models.Model):
    PHYSICAL_CONDITION_CHOICES = [
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('damaged', 'Damaged'),
    ]

    REVIEW_DECISION_CHOICES = [
        ('repair', 'Approve Repair'),
        ('dispatch', 'Approve Dispatch'),
    ]

    waybill_item = models.ForeignKey(WaybillItem, on_delete=models.CASCADE, related_name='pre_calibration_logs')
    scope = models.ForeignKey(CalibrationType, on_delete=models.SET_NULL, null=True, blank=True, related_name='pre_calibration_logs', help_text='Primary scope of calibration determined during inspection (first of `scopes`).')
    scopes = models.ManyToManyField(
        CalibrationType, blank=True, related_name='pre_calibration_logs_m2m',
        help_text='Scope(s) of calibration identified during inspection. One pre-calibration can cover multiple scopes.'
    )
    unit = models.ForeignKey(
        'Unit', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pre_calibration_logs',
        help_text='Primary unit of measurement of the equipment, determined during inspection (first of `units`).'
    )
    units = models.ManyToManyField(
        'Unit', blank=True, related_name='pre_calibration_logs_m2m',
        help_text='Unit(s) of measurement of the equipment, determined during inspection and matched against available reference standards.'
    )
    range_value = models.CharField(
        max_length=100, blank=True, default='',
        help_text='Measurement range of the equipment under inspection (e.g. 0–10 bar). Used to match reference standards by range.'
    )
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True)
    physical_condition = models.CharField(max_length=20, choices=PHYSICAL_CONDITION_CHOICES, default='good')
    visual_inspection_notes = models.TextField(blank=True, default='')
    ready_for_calibration = models.BooleanField(default=True)
    issues_found = models.TextField(blank=True, default='')
    environmental_condition = models.ForeignKey(EnvironmentRecord, on_delete=models.SET_NULL, null=True, blank=True)
    manual_temperature = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    manual_humidity = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    use_manual_env = models.BooleanField(default=False)
    remarks = models.TextField(blank=True, default='')
    inspected_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Review fields
    review_decision = models.CharField(max_length=20, choices=REVIEW_DECISION_CHOICES, null=True, blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='pre_cal_reviews')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    repair_notes = models.TextField(blank=True, default='')
    outgoing_waybill = models.ForeignKey(Waybill, on_delete=models.SET_NULL, null=True, blank=True, related_name='failed_pre_cal_items')
    doc_no = models.CharField(
        max_length=50, blank=True, default='',
        help_text='Lab accreditation document number (PRE-{year}-{seq:04d}).'
    )
    doc_seq = models.PositiveIntegerField(null=True, blank=True, help_text='Sequence within the per-year pre-calibration register.')

    def build_doc_no(self):
        year = self.created_at.year if self.created_at else date.today().year
        return f'PRE-{year}-{(self.doc_seq if self.doc_seq is not None else (self.pk or 0)):04d}'

    def assign_doc_no(self):
        if self.doc_no:
            return False
        with transaction.atomic():
            locked = type(self).objects.select_for_update().filter(
                created_at__year=self.created_at.year if self.created_at else date.today().year,
                doc_no__gt='', doc_seq__isnull=False,
            ).aggregate(m=Max('doc_seq'))['m'] or 0
            self.doc_seq = locked + 1
            self.doc_no = self.build_doc_no()
            self.save(update_fields=['doc_no', 'doc_seq'])
        return True

    def __str__(self):
        return f"Pre-Cal: {self.waybill_item} ({self.get_physical_condition_display()})"

    class Meta:
        ordering = ['-created_at']


class CalibrationLog(models.Model):
    PASS_FAIL_CHOICES = [
        ('pass', 'Pass'),
        ('fail', 'Fail'),
        ('conditional', 'Conditional Pass'),
        ('not_applicable', 'N/A'),
    ]

    CALIBRATION_LOG_STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending_review', 'Pending Review'),
        ('pending_approval', 'Pending Approval'),
        ('pending_qhse', 'Pending QHSE Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    waybill_item = models.ForeignKey(WaybillItem, on_delete=models.CASCADE, related_name='calibration_logs')
    scope = models.ForeignKey(CalibrationType, on_delete=models.SET_NULL, null=True, blank=True, related_name='calibration_logs', help_text='Primary scope of calibration (first of `scopes`). Carried down from the equipment\'s pre-calibration.')
    scopes = models.ManyToManyField(
        CalibrationType, blank=True, related_name='calibration_logs_m2m',
        help_text='Scope(s) covered by this calibration log. A single log may span several scopes.'
    )
    standards = models.ManyToManyField(
        'Primary', blank=True, related_name='calibration_logs',
        help_text='Reference standard(s) (Primaries) used for this calibration.'
    )
    procedure = models.ForeignKey(
        'CalibrationProcedure', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='calibration_logs', help_text='Active procedure followed for this calibration.'
    )
    equipment_owner = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True)
    equipment_desc = models.CharField(max_length=200, blank=True)
    asset_id = models.CharField(max_length=100, blank=True, default='', help_text='Instrument/asset ID of the unit under calibration.')
    manufacturer = models.CharField(max_length=100, blank=True)
    model_no = models.CharField(max_length=50, blank=True)
    serial_no = models.CharField(max_length=50, blank=True)
    range_value = models.CharField(max_length=100, blank=True)
    physical_condition = models.TextField()
    status = models.CharField(max_length=20, choices=CALIBRATION_LOG_STATUS_CHOICES, default='draft')
    certificate = models.FileField(upload_to='certificates/', blank=True, null=True)
    certificate_no = models.CharField(max_length=50, blank=True, default='')
    cert_seq = models.PositiveIntegerField(null=True, blank=True, help_text='Sequence number within this client+scope certificate series.')
    expanded_uncertainty = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True, help_text='Expanded uncertainty U (in %) computed from the uncertainty budget equation')
    uncertainty_in_tolerance = models.BooleanField(null=True, blank=True, help_text='True when the expanded uncertainty is within the primary tolerance')
    environmental_condition = models.ForeignKey(EnvironmentRecord, on_delete=models.SET_NULL, null=True, blank=True)
    manual_temperature = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    manual_humidity = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    use_manual_env = models.BooleanField(default=False)
    temp_tolerance = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text='Allowed temperature deviation (°C)')
    rh_tolerance = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text='Allowed relative humidity deviation (%RH)')
    supply_voltage = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, help_text='Supply voltage during calibration (V)')
    supply_voltage_tolerance = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    supply_frequency = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text='Supply frequency (Hz)')
    supply_frequency_tolerance = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    calibrated_at_location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True)
    calibrated_at_date = models.DateField()
    date_of_issue = models.DateField(null=True, blank=True, help_text='Certificate issue date; defaults to approval date.')
    calibrated_by = models.ForeignKey(Personnel, on_delete=models.SET_NULL, null=True, blank=True)
    pass_fail = models.CharField(max_length=20, choices=PASS_FAIL_CHOICES, default='pass')
    notes = models.TextField(blank=True, null=True)
    reviewer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_calibration_logs',
        help_text='The person selected by the technician to review this calibration data.'
    )
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_logs')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_logs')
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default='')
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    reviewer_signature = models.TextField(
        blank=True, default='',
        help_text='Signature of the reviewer (media URL), stamped automatically from their profile at review time.'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Calibration: {self.equipment_desc or 'N/A'} ({self.serial_no or 'N/A'})"

    @property
    def primary(self):
        """The main reference standard (first selected). Used by the uncertainty budget."""
        return self.standards.first()

    def build_certificate_no(self):
        company = CompanyProfile.objects.first()
        scope_fmt = self.scope.certificate_format if self.scope else ''
        fmt = (scope_fmt
               or (company.certificate_format if company and company.certificate_format else '')
               or '{company_abbr}/{client_abbr}/{scope_abbr}/{seq:04d}')
        year = self.calibrated_at_date.year if self.calibrated_at_date else date.today().year
        ctx = {
            'year': year,
            'seq': self.cert_seq if self.cert_seq is not None else (self.pk or 0),
            'company_abbr': abbreviation_for(company.abbreviation if company else '', company.company_name if company else '') if company else '-',
            'client_abbr': abbreviation_for(self.equipment_owner.abbreviation, self.equipment_owner.name) if self.equipment_owner else '-',
            'scope_abbr': abbreviation_for(self.scope.abbreviation, self.scope.name) if self.scope else '-',
        }
        try:
            return fmt.format(**ctx)
        except (KeyError, ValueError, IndexError):
            return f'CERT-{year}-{(self.pk or 0):04d}'

    def assign_certificate_no(self):
        """Assign cert_seq + certificate_no on first issue (per client+scope series)."""
        if self.certificate_no:
            return False
        with transaction.atomic():
            locked = type(self).objects.select_for_update().filter(
                equipment_owner=self.equipment_owner, scope=self.scope,
                certificate_no__gt='', cert_seq__isnull=False,
            ).aggregate(m=Max('cert_seq'))['m'] or 0
            self.cert_seq = locked + 1
            self.certificate_no = self.build_certificate_no()
            self.save(update_fields=['certificate_no', 'cert_seq'])
        return True

    def reissue_certificate_no(self):
        """Regenerate certificate_no from the CURRENT numbering settings
        (per-scope format → global template → abbreviations), keeping this
        log's slot in its client+scope series so sequences stay stable."""
        with transaction.atomic():
            locked = type(self).objects.select_for_update().filter(
                equipment_owner=self.equipment_owner, scope=self.scope,
                certificate_no__gt='', cert_seq__isnull=False,
            ).exclude(pk=self.pk).aggregate(m=Max('cert_seq'))['m'] or 0
            if self.cert_seq is None:
                # never issued properly — take the next free slot in the series
                self.cert_seq = locked + 1
            old = self.certificate_no
            self.certificate_no = ''
            self.certificate_no = self.build_certificate_no()
            self.save(update_fields=['certificate_no', 'cert_seq'])
        return bool(old != self.certificate_no)

    @property
    def calibration_due(self):
        if not self.calibrated_at_date:
            return None
        months = self.scope.validity_months if self.scope and self.scope.validity_months else 12
        y, m = divmod((self.calibrated_at_date.month - 1) + months, 12)
        try:
            return self.calibrated_at_date.replace(year=self.calibrated_at_date.year + y, month=m + 1)
        except ValueError:
            # e.g. Jan 31 + 1 month → clamp to Feb 28/29
            import calendar
            y2 = self.calibrated_at_date.year + y
            return self.calibrated_at_date.replace(year=y2, month=m + 1, day=calendar.monthrange(y2, m + 1)[1])

    @property
    def previous_certificate_log(self):
        if not self.serial_no:
            return None
        return (type(self).objects
                .filter(serial_no=self.serial_no, status='approved', certificate_no__gt='')
                .exclude(pk=self.pk).order_by('-approved_at').first())

    def compute_uncertainty(self):
        """Auto-run the uncertainty budget on save.

        Two paths:
        * Budget path — when the log's scope has an active `UncertaintyBudget`,
          the combined standard uncertainty comes from the budget's static
          components (u_comb = sqrt(Σ u_i²)) plus this log's measured term
          (max |error| across readings). Expanded U = k × u_comb. This makes the
          uploaded EATL workbook the authoritative basis for the calculation.
        * Equation path — otherwise uses the first selected standard's stored
          equation and variables (k, u_std, error_max, tolerance).

        Stores expanded_uncertainty and uncertainty_in_tolerance on the log.
        Fails silently when nothing can be evaluated.
        """
        primary = self.primary

        from .uncertainty import evaluate_equation

        error_max = 0.0
        for r in self.readings.all():
            if r.error is not None:
                error_max = max(error_max, abs(float(r.error)))
        error_max = round(error_max, 6)

        budget = None
        if self.scope_id:
            budget = self.scope.uncertainty_budgets.filter(active=True).first()

        if budget is not None and budget.combined_std_uncertainty() is not None:
            # Budget-driven: static components + this log's measured error term
            u_comb = (budget.combined_std_uncertainty() ** 2 + error_max ** 2) ** 0.5
            k = float(budget.expanded_k or 2.00)
            if primary and primary.coverage_factor is not None:
                k = float(primary.coverage_factor)
            result = k * u_comb
            self.expanded_uncertainty = round(result, 4)
            tolerance = float(primary.tolerance) if primary and primary.tolerance is not None else None
            if tolerance is not None:
                self.uncertainty_in_tolerance = result <= tolerance
            else:
                self.uncertainty_in_tolerance = None
            self._finalize_uncertainty_result()
            return

        if not primary or not primary.standard_uncertainty:
            self.expanded_uncertainty = None
            self.uncertainty_in_tolerance = None
            return

        equation = primary.uncertainty_equation or 'k * sqrt(u_std**2 + error_max**2)'
        variables = {
            'k': float(primary.coverage_factor or 2.00),
            'u_std': float(primary.standard_uncertainty),
            'error_max': error_max,
            'error_pct_max': error_max,  # backward-compat alias for older equations
            'tolerance': float(primary.tolerance) if primary.tolerance is not None else None,
        }
        try:
            result = evaluate_equation(equation, variables)
            self.expanded_uncertainty = round(result, 4)
            if primary.tolerance is not None:
                self.uncertainty_in_tolerance = result <= float(primary.tolerance)
            else:
                self.uncertainty_in_tolerance = None
        except (ValueError, TypeError, ZeroDivisionError):
            self.expanded_uncertainty = None
            self.uncertainty_in_tolerance = None
        self._finalize_uncertainty_result()

    def _finalize_uncertainty_result(self):
        """Auto-derive pass/fail from the budget (respects manual 'conditional'/'not_applicable')."""
        if self.uncertainty_in_tolerance is not None and self.pass_fail in ('pass', 'fail'):
            self.pass_fail = 'pass' if self.uncertainty_in_tolerance else 'fail'

    def derive_pass_fail_from_remarks(self):
        """Derive the ultimate Pass/Fail from the As-Left remarks (majority rule).

        Only As-Left rows that carry a Maximum Permissible Error take part in the
        decision. A strict majority (more than half) of 'Accepted' remarks → Pass,
        otherwise Fail (including ties). Manual 'conditional'/'not_applicable'
        choices are preserved.
        """
        left = self.readings.filter(
            reading_type='as_left', maximum_permissible_error__isnull=False
        )
        total = left.count()
        if total == 0:
            return
        if self.pass_fail not in ('pass', 'fail'):
            return
        accepted = left.filter(remark='Accepted').count()
        self.pass_fail = 'pass' if accepted * 2 > total else 'fail'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.pk and self.standards.exists():
            self.compute_uncertainty()
            fields = []
            if self.expanded_uncertainty is not None or self.uncertainty_in_tolerance is not None:
                fields += ['expanded_uncertainty', 'uncertainty_in_tolerance']
            if self.pass_fail in ('pass', 'fail'):
                fields += ['pass_fail']
            if fields:
                super().save(update_fields=fields)

    class Meta:
        ordering = ['-created_at']


class CompanyProfile(models.Model):
    company_name = models.CharField(max_length=200, default='My Company')
    abbreviation = models.CharField(
        max_length=10, blank=True, default='',
        help_text='Short code used in certificate numbers (e.g. EATL). Set in Settings.'
    )
    phone = models.CharField(max_length=30, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    logo = models.ImageField(upload_to='company/', blank=True, null=True)
    certificate_footer = models.TextField(blank=True, default='')
    certificate_format = models.CharField(
        max_length=100, blank=True, default='{company_abbr}/{client_abbr}/{scope_abbr}/{seq:04d}',
        help_text='Certificate number template. Placeholders: {company_abbr} {client_abbr} {scope_abbr} {seq} {year}. Per-scope overrides win when set.'
    )
    accreditation_statement = models.TextField(
        blank=True, default='',
        help_text='Fixed legal/accreditation boilerplate printed on the certificate first page.'
    )
    narrative_template = models.TextField(
        blank=True, default='',
        help_text='Narrative paragraph on the certificate. Placeholders: {uuc_description} {standard_used} {standard_cert_no} {traceability_body} {compliance_standard} {software} {procedure_manual}.'
    )
    traceability_body = models.CharField(max_length=100, blank=True, default='', help_text='e.g. UKAS')
    compliance_standard = models.CharField(max_length=150, blank=True, default='', help_text='e.g. EURAMET cg-15 version 3.0 (02/2015)')
    software = models.CharField(max_length=100, blank=True, default='', help_text='e.g. EasyCal V6.82.3')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.company_name

    class Meta:
        verbose_name = 'Company Profile'
        verbose_name_plural = 'Company Profile'


class Unit(models.Model):
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=20)
    scope = models.ForeignKey(CalibrationType, on_delete=models.CASCADE, related_name='units')

    class Meta:
        unique_together = ['symbol', 'scope']
        ordering = ['name']

    def __str__(self):
        return f'{self.symbol} ({self.scope.name})'


class CalibrationLogReading(models.Model):
    READING_TYPE_CHOICES = [
        ('as_found', 'As Found'),
        ('as_left', 'As Left'),
    ]

    calibration_log = models.ForeignKey(CalibrationLog, on_delete=models.CASCADE, related_name='readings')
    reading_type = models.CharField(
        max_length=10, choices=READING_TYPE_CHOICES, default='as_found', db_index=True,
        help_text='Whether the reading was taken before (As Found) or after (As Left) adjustment.'
    )
    instrument_reading = models.DecimalField(max_digits=12, decimal_places=4)
    uut_reading = models.DecimalField(max_digits=12, decimal_places=4)
    unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, null=True, blank=True)
    error = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True, help_text='Error (Instrument reading minus UUT reading)')
    maximum_permissible_error = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True,
        help_text='Maximum Permissible Error (± value) for this reading. Only meaningful on As-Left rows; the remark compares |error| against it.'
    )
    remark = models.CharField(
        max_length=10, blank=True, default='', choices=[('Accepted', 'Accepted'), ('Rejected', 'Rejected')],
        help_text='Accepted / Rejected for this As-Left reading when an MPE is set (|error| ≤ MPE → Accepted).'
    )

    def save(self, *args, **kwargs):
        if self.reading_type == 'as_left' and self.error is not None and self.maximum_permissible_error is not None:
            self.remark = 'Accepted' if abs(self.error) <= self.maximum_permissible_error else 'Rejected'
        else:
            self.remark = ''
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and 'remark' not in update_fields:
            kwargs['update_fields'] = list(update_fields) + ['remark']
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['id']


class CompanyAddress(models.Model):
    company_profile = models.ForeignKey(CompanyProfile, on_delete=models.CASCADE, related_name='addresses')
    label = models.CharField(max_length=200, help_text='e.g. Main Lab, Abuja Office')
    address = models.TextField(blank=True, default='')

    class Meta:
        verbose_name_plural = 'Company Addresses'
        ordering = ['label']

    def __str__(self):
        return self.label


class CalibrationProcedure(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending_approval', 'Pending Approval'),
        ('active', 'Active'),
        ('rejected', 'Rejected'),
    ]

    scope = models.ForeignKey(CalibrationType, on_delete=models.CASCADE, related_name='procedures')
    title = models.CharField(max_length=200)
    manual_reference = models.CharField(
        max_length=200, blank=True, default='',
        help_text="Equipment-manual / document reference this procedure complies with (e.g. 'Manual §7.2, Fluke 754')."
    )
    instructions = models.TextField(
        help_text='Step-by-step calibration instructions, one step per line.'
    )
    test_points_percent = models.JSONField(
        default=list, blank=True,
        help_text='Dynamic test points as % of the equipment range, e.g. [0, 25, 50, 75, 100].'
    )
    tolerance_pct = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True, help_text='Acceptance tolerance in % of range/value.')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    assigned_to = models.ForeignKey(Personnel, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_procedures')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_procedures')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_procedures')
    review_notes = models.TextField(blank=True, default='')
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    doc_no = models.CharField(
        max_length=50, blank=True, default='',
        help_text='Lab accreditation document number (PROC-{scope_abbr}-{year}-{seq:04d}).'
    )
    doc_seq = models.PositiveIntegerField(null=True, blank=True, help_text='Sequence within the per-year procedure register independent of scope.')

    def build_doc_no(self):
        year = self.created_at.year if self.created_at else date.today().year
        scope_abbr = abbreviation_for(self.scope.abbreviation, self.scope.name) if self.scope_id else '-'
        return f'PROC-{scope_abbr}-{year}-{(self.doc_seq if self.doc_seq is not None else (self.pk or 0)):04d}'

    def assign_doc_no(self):
        if self.doc_no:
            return False
        with transaction.atomic():
            locked = type(self).objects.select_for_update().filter(
                created_at__year=self.created_at.year if self.created_at else date.today().year,
                doc_no__gt='', doc_seq__isnull=False,
            ).aggregate(m=Max('doc_seq'))['m'] or 0
            self.doc_seq = locked + 1
            self.doc_no = self.build_doc_no()
            self.save(update_fields=['doc_no', 'doc_seq'])
        return True

    class Meta:
        ordering = ['scope__name', 'title']

    def __str__(self):
        return f'{self.title} ({self.scope.name}) v{self.version}'


class CalibrationLogSpec(models.Model):
    """Instrument-type-specific spec block printed on the certificate ('comments' key-value pairs)."""
    log = models.ForeignKey(CalibrationLog, on_delete=models.CASCADE, related_name='specs')
    spec_name = models.CharField(max_length=100)
    spec_value = models.CharField(max_length=100)

    class Meta:
        ordering = ['id']


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('personnel_review', 'Personnel Record Review'),
        ('repair_approved', 'Repair Approved'),
        ('repair_complete', 'Repair Completed'),
        ('dispatch_approved', 'Dispatch Approved'),
        ('new_client_pending', 'New Client Pending Info'),
        ('new_job_created', 'New Job Created'),
        ('job_updated', 'Job Updated'),
        ('job_overdue', 'Job Overdue'),
        ('primary_due_reminder', 'Primary Due Recalibration'),
        ('pending_review', 'Calibration Log Pending Review'),
        ('pending_approval', 'Calibration Log Pending Approval'),
        ('pending_qhse', 'Calibration Log Pending QHSE Approval'),
        ('log_approved', 'Calibration Log Approved'),
        ('log_rejected', 'Calibration Log Rejected'),
        ('environment_reminder', 'Environment Recording Reminder'),
        ('environment_recorded', 'Environment Recorded'),
        ('procedure_assigned', 'Calibration Procedure Assigned'),
        ('procedure_submitted', 'Calibration Procedure Submitted'),
        ('procedure_approved', 'Calibration Procedure Approved'),
        ('procedure_rejected', 'Calibration Procedure Rejected'),
    ]

    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    link = models.CharField(max_length=255, blank=True, default='')
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES, default='repair_complete')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{'Read' if self.is_read else 'Unread'}] {self.message[:60]}"


class UncertaintyBudget(models.Model):
    """An EATL uncertainty-budget workbook (xlsx) attached to a calibration scope.

    The workbook defines the GUM Type-B budget for an instrument family (e.g.
    pressure gauges). A scope can keep several revisions; exactly one may be
    'active' and drives CalibrationLog.compute_uncertainty() and the
    certificate's Uncertainty Budget annex.
    """
    scope = models.ForeignKey(
        CalibrationType, on_delete=models.CASCADE, related_name='uncertainty_budgets'
    )
    title = models.CharField(max_length=200, blank=True, default='')
    doc_ref = models.CharField(max_length=60, blank=True, default='',
                               help_text='Document reference found in the workbook (e.g. EATL/LAB/UNC/01).')
    revision = models.CharField(max_length=20, blank=True, default='',
                                help_text='Revision string from the workbook (e.g. Rev 02).')
    revised_on = models.DateField(null=True, blank=True, help_text='Revision date from the workbook.')
    file = models.FileField(
        upload_to='uncertainty_budgets/', help_text='Source workbook (.xlsx) in the EATL uncertainty-budget format.'
    )
    active = models.BooleanField(
        default=False,
        help_text='Active budget for the scope — used by calibration logs and certificates.'
    )
    expanded_k = models.DecimalField(
        max_digits=5, decimal_places=2, default=2.00,
        help_text='Coverage factor k found in the workbook (default 2 for 95% confidence).'
    )
    component_count = models.PositiveIntegerField(default=0)
    parse_status = models.CharField(
        max_length=30, default='pending',
        choices=[('pending', 'Pending'), ('ok', 'Parsed'), ('error', 'Parse error')],
    )
    parse_error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.doc_ref or self.title or 'Budget'}{' (Rev ' + self.revision + ')' if self.revision else ''} for {self.scope.name}"

    def combined_std_uncertainty(self):
        """u_comb = sqrt(Σ u_i²) over the stored static components; None when unparseable."""
        total = 0.0
        found = False
        for c in self.components_ordered.all():
            if c.std_uncertainty is not None:
                total += float(c.std_uncertainty) ** 2
                found = True
        return round(total ** 0.5, 6) if found else None

    def expanded_uncertainty(self):
        """U = k × u_comb from the static components (before the log's measured term)."""
        u = self.combined_std_uncertainty()
        if u is None:
            return None
        return round(u * float(self.expanded_k or 2.00), 6)


class UncertaintyBudgetComponent(models.Model):
    """One row of the workbook's Type-B uncertainty table (Symbol / Source / Value /
    Distribution / Divisor / Std uncertainty / Method)."""
    budget = models.ForeignKey(
        UncertaintyBudget, on_delete=models.CASCADE, related_name='components_ordered'
    )
    position = models.PositiveIntegerField(default=0)
    symbol = models.CharField(max_length=40, blank=True, default='')
    source = models.CharField(max_length=200, blank=True, default='')
    method = models.CharField(max_length=200, blank=True, default='',
                              help_text='How the component is determined (from the workbook).')
    value = models.CharField(max_length=60, blank=True, default='',
                             help_text='Raw value from the workbook (may be text like "0.02% of Full Scale").')
    distribution = models.CharField(max_length=30, blank=True, default='')
    divisor = models.DecimalField(max_digits=8, decimal_places=6, null=True, blank=True)
    std_uncertainty = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)

    class Meta:
        ordering = ['position']

    def __str__(self):
        return f"{self.symbol or self.source or 'component'} ({self.budget.doc_ref})"


# Sync Location entries from CompanyAddress
from django.db.models.signals import post_save, post_delete, pre_delete


def track_address_label(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._old_label = CompanyAddress.objects.get(pk=instance.pk).label
        except CompanyAddress.DoesNotExist:
            instance._old_label = None
    else:
        instance._old_label = None


def sync_location_from_address(sender, instance, created, **kwargs):
    if created:
        Location.objects.get_or_create(
            name=instance.label,
            defaults={'address': instance.address}
        )
    else:
        old_label = getattr(instance, '_old_label', None)
        if old_label and old_label != instance.label:
            Location.objects.filter(name=old_label).delete()
        Location.objects.update_or_create(
            name=instance.label,
            defaults={'address': instance.address}
        )


def remove_location_from_address(sender, instance, **kwargs):
    old_label = getattr(instance, '_old_label', None)
    if old_label:
        Location.objects.filter(name=old_label).delete()
    Location.objects.filter(name=instance.label).delete()


pre_delete.connect(track_address_label, sender=CompanyAddress)
post_save.connect(sync_location_from_address, sender=CompanyAddress)
post_delete.connect(remove_location_from_address, sender=CompanyAddress)

# Register additive, versioned E&I workflow records with Django's model registry.
from .workflow_models import (CalibrationLogTemplate, JobUUT, JobSubmission, JobReview, JobDecision,
    JobScheduleRevision, JobDocument, TechnicalRecord, TechnicalRecordRevision,
    PersonnelEvidence, PersonnelCompetency, PersonnelAuthorization,
    PersonnelProfileRevision, PersonnelCorrectionRequest, PersonnelReviewReminder, CAPARecord, CAPADocument, EquipmentRecord, WorkflowAudit, AdminAccountLink, AdministrativeArchive)
