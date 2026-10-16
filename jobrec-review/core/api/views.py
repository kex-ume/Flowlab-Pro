from django.urls import reverse
from django.utils import timezone
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from core.api.serializers import (
    CalibrationLogSerializer, CalibrationLogWriteSerializer,
    CalibrationTypeSerializer, ClientSerializer,
    EnvironmentRecordSerializer, JobSerializer, JobWriteSerializer,
    NotificationSerializer, PersonnelSerializer,
    PreCalibrationLogSerializer, RoleSerializer,
    UnitSerializer, WaybillSerializer, WaybillWriteSerializer,
)
from core.auth_utils import get_users_with_perm, has_perm, get_user_signature_url
from core.notifications import calibration_log_recipients, notify_users, personnel_users
from core.models import (
    CalibrationLog, CalibrationType, Client, EnvironmentRecord,
    EnvironmentReminder, Job, Notification, Personnel, PreCalibrationLog, Role,
    Unit, Waybill, WaybillItem,
)


# ─── Custom DRF Permission ──────────────────────────────────────────────────

class CustomPermission(permissions.BasePermission):
    """Map custom codename permissions to DRF view permissions."""

    perms_map = {
        'GET': ['view_%(model_name)s'],
        'OPTIONS': ['view_%(model_name)s'],
        'HEAD': ['view_%(model_name)s'],
        'POST': ['create_%(model_name)s'],
        'PUT': ['edit_%(model_name)s'],
        'PATCH': ['edit_%(model_name)s'],
        'DELETE': ['delete_%(model_name)s'],
    }

    def has_permission(self, request, view):
        from core.auth_utils import lab_authority
        if not request.user.is_authenticated or not request.user.is_active: return False
        if lab_authority(request.user):
            return True
        model_name = getattr(view, 'perm_model_name', None)
        if not model_name:
            return True
        action=getattr(view,'action','')
        action_permissions={'review':'review_calibration','approve':'approve_calibration',
                            'reject':'reject_calibration','upload_certificate':'edit_calibration'}
        if action in action_permissions: return has_perm(request.user,action_permissions[action])
        read=request.method in ('GET','HEAD','OPTIONS')
        aliases={
            'calibration':('view_jobs','edit_calibration') if read else ('edit_calibration',),
            'precalibration':('view_jobs','view_equipment') if read else ('perform_pre_calibration',),
            'environment':('view_jobs','record_environment') if read else ('record_environment',),
            'personnel':('view_jobs','manage_personnel') if read else ('manage_personnel',),
            'clients':('view_jobs','create_clients') if read else ('create_clients',),
            'waybills':('view_waybills',) if read else ('create_waybills',),
        }
        if model_name in aliases:
            return any(has_perm(request.user,permission) for permission in aliases[model_name])
        perm_codenames = self.perms_map.get(request.method, [])
        return any(has_perm(request.user, c % {'model_name': model_name}) for c in perm_codenames)


# ─── Mixin ───────────────────────────────────────────────────────────────────

class ModelPermMixin:
    perm_model_name = None
    permission_classes = [permissions.IsAuthenticated,CustomPermission]

    def destroy(self, request, *args, **kwargs):
        raise ValidationError('Use the recoverable record-removal controls; direct permanent API deletion is disabled.')

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return getattr(self, 'write_serializer_class', self.serializer_class)
        return self.serializer_class


# ─── Client ──────────────────────────────────────────────────────────────────

class ClientViewSet(ModelPermMixin, viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    perm_model_name = 'clients'
    filterset_fields = ['status', 'name']
    search_fields = ['name', 'email']


# ─── Waybill ─────────────────────────────────────────────────────────────────

class WaybillViewSet(ModelPermMixin, viewsets.ModelViewSet):
    queryset = Waybill.objects.prefetch_related('items__calibration_logs')
    serializer_class = WaybillSerializer
    write_serializer_class = WaybillWriteSerializer
    perm_model_name = 'waybills'
    filterset_fields = ['waybill_type']
    search_fields = ['waybill_no']

    @action(detail=False)
    def incoming(self, request):
        qs = self.get_queryset().filter(waybill_type='incoming')
        page = self.paginate_queryset(qs)
        if page is not None:
            ser = self.get_serializer(page, many=True)
            return self.get_paginated_response(ser.data)
        ser = self.get_serializer(qs, many=True)
        return Response(ser.data)

    @action(detail=False)
    def outgoing(self, request):
        qs = self.get_queryset().filter(waybill_type='outgoing')
        page = self.paginate_queryset(qs)
        if page is not None:
            ser = self.get_serializer(page, many=True)
            return self.get_paginated_response(ser.data)
        ser = self.get_serializer(qs, many=True)
        return Response(ser.data)


# ─── CalibrationLog ──────────────────────────────────────────────────────────

class CalibrationLogViewSet(ModelPermMixin, viewsets.ModelViewSet):
    queryset = CalibrationLog.objects.prefetch_related(
        'readings__unit', 'waybill_item'
    ).select_related(
        'calibrated_by', 'reviewer', 'reviewed_by', 'approved_by', 'scope'
    )
    serializer_class = CalibrationLogSerializer
    write_serializer_class = CalibrationLogWriteSerializer
    parser_classes = [FormParser, MultiPartParser]
    perm_model_name = 'calibration'
    filterset_fields = ['status', 'pass_fail', 'scope']
    search_fields = ['waybill_item__serial_no', 'waybill_item__equipment_description']

    def perform_create(self, serializer):
        from core.personnel_records import validate_analyst
        from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
        from rest_framework.exceptions import PermissionDenied
        person=serializer.validated_data.get('calibrated_by') or Personnel.objects.filter(user=self.request.user).first()
        scopes=list(serializer.validated_data.get('scopes') or [])
        if not scopes and serializer.validated_data.get('scope'): scopes=[serializer.validated_data['scope']]
        try: validate_analyst(person,scopes)
        except DjangoPermissionDenied as error: raise PermissionDenied(str(error))
        log = serializer.save(recorded_by=self.request.user,calibrated_by=person)
        item = log.waybill_item
        if item and item.status != 'result_pending':
            item.status = 'result_pending'
            item.save()
        job = Job.objects.filter(incoming_waybill=item.waybill).first() if item else None
        if job:
            job.reconcile_status()
        if log.status == 'pending_review':
            reviewer = log.reviewer
            recipients = [reviewer] if reviewer else get_users_with_perm('review_calibration')
            notify_users(
                recipients,
                f'New calibration log pending review — {log.equipment_desc} (SN: {log.serial_no})',
                reverse('calibration_log_detail', args=[log.pk]),
                'pending_review',
            )

    def perform_update(self, serializer):
        if serializer.instance.status not in ('pending_review','rejected'):
            raise ValidationError('Reviewed or approved calibration logs are locked; return for rework or issue a controlled revision.')
        from core.personnel_records import validate_analyst
        from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
        from rest_framework.exceptions import PermissionDenied
        scopes=list(serializer.validated_data.get('scopes',serializer.instance.scopes.all()))
        if not scopes and serializer.validated_data.get('scope',serializer.instance.scope): scopes=[serializer.validated_data.get('scope',serializer.instance.scope)]
        try: validate_analyst(serializer.validated_data.get('calibrated_by',serializer.instance.calibrated_by),scopes)
        except DjangoPermissionDenied as error: raise PermissionDenied(str(error))
        log=serializer.save()
        if log.status=='rejected':
            log.status='pending_review';log.reviewed_by=None;log.reviewed_at=None;log.reviewer_signature=''
            log.approved_by=None;log.approved_at=None;log.rejection_reason=''
            log.save(update_fields=['status','reviewed_by','reviewed_at','reviewer_signature','approved_by','approved_at','rejection_reason'])
            notify_users([log.reviewer] if log.reviewer_id else get_users_with_perm('review_calibration'),
                f'Reworked calibration log {log.pk} requires Supervisor review.',reverse('calibration_log_detail',args=[log.pk]),'pending_review')

    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        log = self.get_object()
        from core.personnel_records import authorized_log
        if not authorized_log(request.user,log,'review') or request.user.pk == log.recorded_by_id or (log.calibrated_by_id and log.calibrated_by.user_id == request.user.pk):
            return Response({'error':'Current technical review authorization and independent reviewer required'},status=403)
        if not has_perm(request.user, 'review_calibration'):
            return Response({'error': 'Not authorized to review'}, status=403)
        if log.status != 'pending_review':
            return Response({'error': 'Log is not pending review'}, status=400)
        from core.auth_utils import lab_authority
        if log.reviewer_id and log.reviewer_id != request.user.pk and not lab_authority(request.user):
            return Response({'error': 'Log is assigned to a different reviewer'}, status=403)
        signature = get_user_signature_url(request.user)
        if not signature:
            return Response(
                {'error': 'No signature on your profile. Upload one via Profile → Edit before reviewing.'},
                status=400,
            )
        log.status = 'pending_approval'
        log.reviewed_by = request.user
        log.reviewed_at = timezone.now()
        log.reviewer_signature = signature
        log.save()
        job = Job.objects.filter(incoming_waybill=log.waybill_item.waybill).first()
        if job:
            job.reconcile_status()
        notify_users(
            calibration_log_recipients(log),
            f'Calibration log reviewed — upload the signed result to push it for QHSE approval: {log.equipment_desc} (SN: {log.serial_no})',
            reverse('calibration_log_detail', args=[pk]),
            'pending_approval',
        )
        return Response(CalibrationLogSerializer(log).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        log = self.get_object()
        from core.personnel_records import authorized_log
        if not authorized_log(request.user,log,'approve') or request.user.pk == log.recorded_by_id or (log.calibrated_by_id and log.calibrated_by.user_id == request.user.pk):
            return Response({'error':'Current technical approval authorization and independent approver required'},status=403)
        if not has_perm(request.user, 'approve_calibration'):
            return Response({'error': 'Not authorized to approve'}, status=403)
        if log.status not in ('pending_qhse', 'pending_approval'):
            return Response({'error': 'Log is not pending QHSE approval'}, status=400)
        log.status = 'approved'
        log.approved_by = request.user
        log.approved_at = timezone.now()
        if not log.date_of_issue:
            log.date_of_issue = log.approved_at.date()
        log.save()
        notify_users(
            calibration_log_recipients(log),
            f'Your calibration log was approved — {log.equipment_desc} (SN: {log.serial_no})',
            reverse('calibration_log_detail', args=[pk]),
            'log_approved',
        )
        if log.certificate and log.waybill_item:
            log.waybill_item.status = 'completed'
            log.waybill_item.save()
        job = Job.objects.filter(incoming_waybill=log.waybill_item.waybill).first()
        if job:
            job.reconcile_status()
        return Response(CalibrationLogSerializer(log).data)

    @action(detail=True, methods=['post'])
    def upload_certificate(self, request, pk=None):
        log = self.get_object()
        if log.status=='approved' and log.certificate:
            raise ValidationError('Approved signed results are locked; use a controlled amendment.')
        if not has_perm(request.user, 'edit_calibration'):
            return Response({'error': 'Not authorized to upload results'}, status=403)
        upload = request.FILES.get('certificate')
        if not upload:
            return Response({'error': 'No certificate file provided'}, status=400)
        log.certificate = upload
        log.save(update_fields=['certificate'])
        if log.status == 'pending_approval':
            log.status = 'pending_qhse'
            log.save(update_fields=['status'])
            notify_users(
                get_users_with_perm('approve_calibration'),
                f'Signed result uploaded — calibration log pending QHSE approval: {log.equipment_desc} (SN: {log.serial_no})',
                reverse('calibration_log_detail', args=[pk]),
                'pending_qhse',
            )
        elif log.status == 'approved' and log.waybill_item:
            if log.waybill_item.status != 'completed':
                log.waybill_item.status = 'completed'
                log.waybill_item.save()
                job = Job.objects.filter(incoming_waybill=log.waybill_item.waybill).first()
                if job:
                    job.reconcile_status()
        return Response(CalibrationLogSerializer(log).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        log = self.get_object()
        from core.personnel_records import authorized_log
        if not authorized_log(request.user,log,'review') or request.user.pk in (log.recorded_by_id,getattr(log.calibrated_by,'user_id',None)):
            return Response({'error':'An independent authorized reviewer is required'},status=403)
        if not has_perm(request.user, 'reject_calibration'):
            return Response({'error': 'Not authorized to reject'}, status=403)
        if log.status not in ('pending_review', 'pending_approval', 'pending_qhse'):
            return Response({'error': 'Log cannot be rejected at its current status'}, status=400)
        reason = request.data.get('reason', '')
        if not str(reason).strip(): raise ValidationError('A return-for-rework reason is required.')
        log.status = 'rejected'
        log.rejection_reason = reason
        log.save()
        job = Job.objects.filter(incoming_waybill=log.waybill_item.waybill).first()
        if job:
            job.reconcile_status()
        notify_users(
            calibration_log_recipients(log),
            f'Your calibration log was rejected — {log.equipment_desc} (SN: {log.serial_no}). Reason: {reason}',
            reverse('calibration_log_detail', args=[pk]),
            'log_rejected',
        )
        return Response(CalibrationLogSerializer(log).data)


# ─── Job ─────────────────────────────────────────────────────────────────────

class JobViewSet(ModelPermMixin, viewsets.ModelViewSet):
    queryset = Job.objects.select_related(
        'client', 'incoming_waybill'
    )
    serializer_class = JobSerializer
    write_serializer_class = JobWriteSerializer
    perm_model_name = 'jobs'
    filterset_fields = ['job_status', 'client']
    search_fields = ['purchase_order_number', 'client__name']

    def get_queryset(self):
        # Managed jobs have dedicated approval/ownership endpoints.
        return super().get_queryset().filter(workflow_managed=False)

    def perform_create(self, serializer):
        raise ValidationError('New E&I jobs must use the Job Records draft/submission workflow.')


# ─── PreCalibrationLog ───────────────────────────────────────────────────────

class PreCalibrationLogViewSet(ModelPermMixin, viewsets.ModelViewSet):
    queryset = PreCalibrationLog.objects.select_related(
        'waybill_item', 'inspected_by'
    ).prefetch_related('scopes', 'units')
    serializer_class = PreCalibrationLogSerializer
    perm_model_name = 'precalibration'
    filterset_fields = ['ready_for_calibration', 'review_decision']
    search_fields = ['waybill_item__serial_no', 'waybill_item__equipment_description']

    def perform_create(self, serializer):
        save_kwargs = {}
        if 'inspected_by' not in serializer.validated_data and hasattr(self.request.user, 'personnel_profile'):
            save_kwargs['inspected_by'] = self.request.user.personnel_profile
        instance = serializer.save(**save_kwargs)
        instance.assign_doc_no()
        scope_ids = list(instance.scopes.values_list('id', flat=True))
        unit_ids = list(instance.units.values_list('id', flat=True))
        if not scope_ids and instance.waybill_item and instance.waybill_item.scope_id:
            scope_ids = [instance.waybill_item.scope_id]
        if scope_ids:
            from core.models import CalibrationType
            instance.scopes.set(CalibrationType.objects.filter(id__in=scope_ids))
            instance.scope = instance.scopes.first()
        if unit_ids:
            instance.unit = instance.units.first()
        if scope_ids or unit_ids:
            instance.save(update_fields=['scope', 'unit'])


# ─── EnvironmentRecord ───────────────────────────────────────────────────────

class EnvironmentRecordViewSet(ModelPermMixin, viewsets.ModelViewSet):
    queryset = EnvironmentRecord.objects.select_related('recorded_by', 'location')
    serializer_class = EnvironmentRecordSerializer
    perm_model_name = 'environment'
    filterset_fields = ['date', 'location']
    ordering_fields = ['date', 'time']

    def perform_create(self, serializer):
        record = serializer.save(recorded_by=self.request.user)
        record.assign_doc_no()
        EnvironmentReminder.objects.update_or_create(
            date=record.date,
            time=record.time,
            location_id=record.location_id,
            defaults={
                'is_recorded': True,
                'recorded_at': timezone.now(),
            }
        )
        lab = f" for {record.location.name}" if record.location_id else ""
        notify_users(
            personnel_users(exclude_user=self.request.user),
            (
                f'Environment recorded{lab} — {record.date} {record.get_time_display()} '
                f'({record.temperature}\u00b0C, {record.relative_humidity}% RH) '
                f'by {self.request.user.get_full_name() or self.request.user.username}.'
            ),
            reverse('environment_list') + (f'?location={record.location_id}' if record.location_id else ''),
            'environment_recorded',
        )


# ─── Personnel (read-only) ───────────────────────────────────────────────────

class PersonnelViewSet(ModelPermMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Personnel.objects.select_related('role', 'user')
    serializer_class = PersonnelSerializer
    perm_model_name = 'personnel'
    search_fields = ['name', 'user__username']

    def get_queryset(self):
        rows=super().get_queryset()
        if has_perm(self.request.user,'manage_personnel'): return rows
        return rows.filter(user=self.request.user)


# ─── Reference data (unrestricted read-only) ─────────────────────────────────

class CalibrationTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CalibrationType.objects.all()
    serializer_class = CalibrationTypeSerializer
    pagination_class = None


class UnitViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Unit.objects.select_related('scope')
    serializer_class = UnitSerializer
    pagination_class = None
    filterset_fields = ['scope']


class RoleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Role.objects.prefetch_related('permissions')
    serializer_class = RoleSerializer
    pagination_class = None
    search_fields = ['name']


class NotificationViewSet(ModelPermMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    perm_model_name = 'notifications'

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response({'status': 'marked as read'})
