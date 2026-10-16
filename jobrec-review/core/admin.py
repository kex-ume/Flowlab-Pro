from django.contrib import admin
from .models import (
    CalibrationLog, CalibrationLogReading, CalibrationLogSpec,
    CalibrationProcedure, CalibrationType, Client,
    CompanyAddress, CompanyProfile, EnvironmentRecord, EnvironmentReminder,
    Job, Location, Notification, Permission, Personnel, PreCalibrationLog,
    Primary, Role, Unit, UncertaintyBudget, UncertaintyBudgetComponent,
    Waybill, WaybillItem
)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'phone', 'status']
    list_filter = ['status']
    search_fields = ['name', 'email']


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = [
        'purchase_order_number', 'client', 'job_status',
        'invoice_status', 'created_at'
    ]
    list_filter = ['job_status', 'invoice_status']
    search_fields = ['purchase_order_number', 'serial_no']

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.workflow_managed:
            return [field.name for field in self.model._meta.fields] + ['assigned_to']
        return super().get_readonly_fields(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False if obj and obj.workflow_managed else super().has_delete_permission(request, obj)


@admin.register(Primary)
class PrimaryAdmin(admin.ModelAdmin):
    def get_readonly_fields(self,request,obj=None):
        if obj and obj.retained_records.filter(kind='calibration',status='approved').exists():
            return ['last_calibrated','calibration_due_date','calibration_frequency','certificate_no']
        return []

    def has_delete_permission(self,request,obj=None):
        return False

    list_display = ['name', 'serial_no', 'scope', 'unit', 'range_min', 'range_max', 'calibration_due_date', 'standard_uncertainty', 'status']
    list_filter = ['status', 'scope', 'unit']
    search_fields = ['name', 'serial_no']
    filter_horizontal = ['units']


@admin.register(CalibrationProcedure)
class CalibrationProcedureAdmin(admin.ModelAdmin):
    list_display = ['title', 'scope', 'doc_no', 'status', 'assigned_to', 'version', 'updated_at']
    list_filter = ['status', 'scope']
    search_fields = ['title', 'manual_reference', 'doc_no']
    readonly_fields = ['created_at', 'updated_at', 'doc_no']


class WaybillItemInline(admin.TabularInline):
    model = WaybillItem
    extra = 1


@admin.register(Waybill)
class WaybillAdmin(admin.ModelAdmin):
    list_display = ['waybill_no', 'waybill_type', 'created_at']
    list_filter = ['waybill_type']
    search_fields = ['waybill_no']
    inlines = [WaybillItemInline]


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'address']
    search_fields = ['name']


@admin.register(CalibrationType)
class CalibrationTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'instrument_column_label', 'uut_column_label', 'error_column_label']


@admin.register(Personnel)
class PersonnelAdmin(admin.ModelAdmin):
    list_display = ['name', 'role', 'location_text', 'years_of_experience']
    list_filter = ['role']
    filter_horizontal = ['scope_of_expertise']

    def save_model(self, request, obj, form, change):
        from .models import PersonnelProfileRevision
        names=('name','position','department','qualifications','years_of_experience','employment_status')
        previous=Personnel.objects.get(pk=obj.pk) if change else None
        before={name:str(getattr(previous,name)) for name in names} if previous else {}
        super().save_model(request,obj,form,change)
        PersonnelProfileRevision.objects.create(personnel=obj,created_by=request.user,
            actor_name=request.user.get_full_name() or request.user.username,
            snapshot={'before':before,'after':{name:str(getattr(obj,name)) for name in names},'source':'Django administrator'})

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'permission_count']
    filter_horizontal = ['permissions']

    def permission_count(self, obj):
        return obj.permissions.count()
    permission_count.short_description = 'Permissions'


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ['codename', 'name']
    search_fields = ['codename', 'name']


@admin.register(PreCalibrationLog)
class PreCalibrationLogAdmin(admin.ModelAdmin):
    list_display = ['waybill_item', 'doc_no', 'ready_for_calibration', 'inspected_by', 'created_at']
    list_filter = ['physical_condition', 'ready_for_calibration', 'scope']
    filter_horizontal = ['scopes', 'units']
    readonly_fields = ['doc_no']


@admin.register(EnvironmentRecord)
class EnvironmentRecordAdmin(admin.ModelAdmin):
    list_display = ['date', 'time', 'doc_no', 'location', 'temperature', 'relative_humidity', 'recorded_by']
    list_filter = ['date', 'time', 'location']
    readonly_fields = ['doc_no']


@admin.register(EnvironmentReminder)
class EnvironmentReminderAdmin(admin.ModelAdmin):
    list_display = ['date', 'time', 'is_recorded']
    list_filter = ['is_recorded']


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ['symbol', 'name', 'scope']
    list_filter = ['scope']
    search_fields = ['name', 'symbol']


class CalibrationLogReadingInline(admin.TabularInline):
    model = CalibrationLogReading
    extra = 1


class CalibrationLogSpecInline(admin.TabularInline):
    model = CalibrationLogSpec
    extra = 1


class CompanyAddressInline(admin.TabularInline):
    model = CompanyAddress
    extra = 1


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'phone', 'email']
    inlines = [CompanyAddressInline]


@admin.register(CompanyAddress)
class CompanyAddressAdmin(admin.ModelAdmin):
    list_display = ['label', 'company_profile']
    list_filter = ['company_profile']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['message', 'recipient', 'is_read', 'notification_type', 'created_at']
    list_filter = ['is_read', 'notification_type']


@admin.register(CalibrationLog)
class CalibrationLogAdmin(admin.ModelAdmin):
    list_display = ['equipment_desc', 'serial_no', 'primary', 'status', 'pass_fail', 'expanded_uncertainty', 'calibrated_at_date', 'calibrated_by']
    list_filter = ['status', 'pass_fail', 'scope', 'scopes']
    search_fields = ['serial_no', 'equipment_desc', 'certificate_no']
    inlines = [CalibrationLogReadingInline, CalibrationLogSpecInline]
    autocomplete_fields = ['standards']
    filter_horizontal = ['scopes']
    readonly_fields = ['reviewer_signature']


class UncertaintyBudgetComponentInline(admin.TabularInline):
    model = UncertaintyBudgetComponent
    extra = 0
    fields = ['position', 'symbol', 'source', 'method', 'value', 'distribution', 'divisor', 'std_uncertainty']


@admin.register(UncertaintyBudget)
class UncertaintyBudgetAdmin(admin.ModelAdmin):
    list_display = ['scope', 'doc_ref', 'revision', 'revised_on', 'active', 'component_count', 'expanded_k', 'parse_status', 'created_at']
    list_filter = ['scope', 'active', 'parse_status']
    search_fields = ['doc_ref', 'title']
    inlines = [UncertaintyBudgetComponentInline]
    readonly_fields = ['doc_ref', 'revision', 'revised_on', 'component_count', 'parse_status', 'parse_error', 'created_at']


class ControlledRecordAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


from .workflow_models import (CalibrationLogTemplate, JobUUT, JobSubmission, JobDecision,
    JobScheduleRevision, JobDocument, TechnicalRecord, TechnicalRecordRevision,
    PersonnelEvidence, PersonnelCompetency, PersonnelAuthorization,
    PersonnelProfileRevision, PersonnelCorrectionRequest, PersonnelReviewReminder, CAPARecord, CAPADocument, EquipmentRecord, WorkflowAudit)

for record_model in (CalibrationLogTemplate, JobUUT, JobSubmission, JobDecision,
    JobScheduleRevision, JobDocument, TechnicalRecord, TechnicalRecordRevision,
    PersonnelEvidence, PersonnelCompetency, PersonnelAuthorization,
    PersonnelProfileRevision, PersonnelCorrectionRequest, PersonnelReviewReminder, CAPARecord, CAPADocument, EquipmentRecord, WorkflowAudit):
    admin.site.register(record_model, ControlledRecordAdmin)
