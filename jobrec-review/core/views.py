import base64
import io
import json
import logging
import os
import re

import qrcode
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)

from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.core.signing import TimestampSigner, SignatureExpired, BadSignature
from django.db.models import Q, Prefetch, Count
from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, UpdateView
)
from django.forms import modelform_factory, Textarea as FormTextarea

from .auth_utils import has_perm, get_users_with_perm, get_user_signature_url, lab_authority
from .notifications import calibration_log_recipients, notify_users, personnel_users, send_overdue_job_reminders
from .unit_catalog import units_for_scope
from .forms import (
    CalibrationLogForm, CalibrationTypeForm, ClientForm,
    CompanyProfileForm, EnvironmentRecordForm, IncomingWaybillForm,
    IncomingWaybillWithAutoNumberForm, JobForm, PersonnelForm,
    PreCalibrationForm, PreCalReviewForm, PrimaryForm, ProcedureAssignForm,
    ProfileForm, RoleForm, OutgoingWaybillForm,
)
from .models import (
    CalibrationLog, CalibrationLogReading, CalibrationLogSpec,
    CalibrationProcedure, CalibrationType, Client,
    CompanyAddress, CompanyProfile, EnvironmentRecord, EnvironmentReminder,
    Job, Location, Notification, Permission, Personnel, PreCalibrationLog,
    Primary, Role, Unit, UncertaintyBudget, UncertaintyBudgetComponent,
    Waybill, WaybillItem, abbreviation_for
)


@login_required
def dashboard(request):
    from .dashboard_attention import dashboard_data
    return render(request,'core/dashboard.html',dashboard_data(request.user))


# ─── Clients ──────────────────────────────────────────────────────────────────


class ClientListView(LoginRequiredMixin, ListView):
    model = Client
    template_name = 'core/clients/list.html'
    context_object_name = 'clients'
    paginate_by = 20

    def get_queryset(self):
        qs = Client.objects.all()
        search = self.request.GET.get('search', '')
        status = self.request.GET.get('status', '')
        if search:
            qs = qs.filter(name__icontains=search)
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filters'] = {
            'search': self.request.GET.get('search', ''),
            'status': self.request.GET.get('status', ''),
        }
        return context
    paginate_by = 20


class ClientCreateView(LoginRequiredMixin, CreateView):
    model = Client
    form_class = ClientForm
    template_name = 'core/clients/create.html'
    success_url = reverse_lazy('client_list')

    def dispatch(self, request, *args, **kwargs):
        if not has_perm(request.user, 'create_clients'):
            messages.error(request, 'Only administrators can create clients.')
            return redirect('client_list')
        return super().dispatch(request, *args, **kwargs)


class ClientDetailView(LoginRequiredMixin, DetailView):
    model = Client
    template_name = 'core/clients/detail.html'
    context_object_name = 'client'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['jobs'] = self.object.jobs.select_related('incoming_waybill').prefetch_related('waybills').all()
        return context


class ClientUpdateView(LoginRequiredMixin, UpdateView):
    model = Client
    form_class = ClientForm
    template_name = 'core/clients/edit.html'
    success_url = reverse_lazy('client_list')

    def dispatch(self, request, *args, **kwargs):
        if not has_perm(request.user, 'create_clients'):
            messages.error(request, 'Only administrators can edit clients.')
            return redirect('client_list')
        return super().dispatch(request, *args, **kwargs)


class ClientDeleteView(LoginRequiredMixin, DeleteView):
    model = Client
    template_name = 'core/clients/confirm_delete.html'
    success_url = reverse_lazy('client_list')

    def dispatch(self, request, *args, **kwargs):
        if not has_perm(request.user, 'create_clients'):
            messages.error(request, 'Only administrators can delete clients.')
            return redirect('client_list')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['jobs_count'] = self.object.jobs.count()
        return context


# ─── Jobs ─────────────────────────────────────────────────────────────────────


class JobListView(LoginRequiredMixin, ListView):
    model = Job
    template_name = 'core/jobs/list.html'
    context_object_name = 'jobs'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if not has_perm(request.user, 'view_jobs'):
                raise PermissionDenied('E&I job access is required.')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        from .ei_workflow import visible_jobs
        qs = visible_jobs(self.request.user).select_related('client', 'incoming_waybill').prefetch_related('uuts')
        search = self.request.GET.get('search', '')
        status = self.request.GET.get('status', '')
        record_status = self.request.GET.get('record_status', '')
        client_id = self.request.GET.get('client', '')
        if search:
            query = (
                Q(purchase_order_number__icontains=search) |
                Q(serial_no__icontains=search) |
                Q(client__name__icontains=search)
            )
            number = re.sub(r'^EI-JOB-', '', search, flags=re.I)
            if number.isdigit():
                query |= Q(pk=int(number))
            qs = qs.filter(query)
        if status:
            qs = qs.filter(job_status=status)
        legacy_filters = {'scheduled': Q(job_status='not_received', incoming_waybill__isnull=True),
            'pending': Q(job_status='pre_calibration_pending') | Q(job_status='not_received', incoming_waybill__isnull=False),
            'ongoing': ~Q(job_status__in=['not_received', 'pre_calibration_pending', 'completed', 'dispatched']),
            'completed': Q(job_status__in=['completed', 'dispatched'])}
        if record_status in legacy_filters:
            qs = qs.filter(Q(workflow_managed=True, progress_status=record_status) | (Q(workflow_managed=False) & legacy_filters[record_status]))
        if self.request.GET.get('job_type') in ('lab', 'field'):
            qs = qs.filter(job_type=self.request.GET['job_type'])
        request_type = self.request.GET.get('request_type')
        if request_type == 'mixed':
            qs = qs.annotate(request_count=Count('uuts__request_type', distinct=True, filter=Q(uuts__archived=False))).filter(request_count__gt=1)
        elif request_type in dict(Job.REQUEST_TYPE_CHOICES):
            qs = qs.filter(Q(workflow_managed=True, uuts__request_type=request_type, uuts__archived=False) | Q(workflow_managed=False, request_type=request_type))
        if self.request.GET.get('overdue') == '1':
            qs = qs.filter(scheduled_end_date__lt=timezone.localdate()).exclude(Q(workflow_managed=True, progress_status='completed') | Q(workflow_managed=False, job_status__in=['completed', 'dispatched']))
        approval=self.request.GET.get('approval')
        if approval in ('draft','awaiting','approved','reverted'):
            qs=qs.filter(workflow_managed=True,approval_state=approval)
        if self.request.GET.get('assigned', '').isdigit():
            qs = qs.filter(assigned_to=self.request.GET['assigned'])
        if client_id:
            qs = qs.filter(client_id=client_id)
        return qs.order_by('created_at' if self.request.GET.get('sort') == 'oldest' else '-created_at').distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filters'] = {
            'search': self.request.GET.get('search', ''),
            'status': self.request.GET.get('status', ''),
            'record_status': self.request.GET.get('record_status', ''),
            'client': self.request.GET.get('client', ''),
        }
        context['clients'] = Client.objects.all()
        context['status_choices'] = Job.JOB_STATUS_CHOICES
        initial = {key: self.request.GET[key] for key in ('purchase_order_number', 'client', 'job_description', 'incoming_waybill') if key in self.request.GET}
        if 'incoming' in self.request.GET:
            initial['incoming_waybill'] = self.request.GET['incoming']
        context['new_job_form'] = JobForm(initial=initial)
        context['client_names'] = Client.objects.values_list('name', flat=True)
        from .ei_views import bootstrap
        context['job_bootstrap'] = bootstrap(self.request.user)
        return context


class JobCreateView(LoginRequiredMixin, CreateView):
    model = Job
    form_class = JobForm
    template_name = 'core/jobs/create.html'
    success_url = reverse_lazy('job_list')

    def get(self, request, *args, **kwargs):
        params = request.GET.copy()
        params['add'] = '1'
        return redirect(f'{reverse("job_list")}?{params.urlencode()}')

    def post(self, request, *args, **kwargs):
        messages.error(request, 'Use the Job Records wizard to save or submit a new E&I job.')
        return redirect(f'{reverse("job_list")}?add=1')

    def dispatch(self, request, *args, **kwargs):
        if not has_perm(request.user, 'create_jobs'):
            messages.error(request, 'You do not have permission to create jobs.')
            return redirect('job_list')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['clients'] = Client.objects.all()
        context['client_names'] = [c.name for c in Client.objects.all()]
        context['calibration_types'] = CalibrationType.objects.all()
        return context

    def get_initial(self):
        initial = super().get_initial()
        for field in ('purchase_order_number', 'client', 'job_description'):
            value = self.request.GET.get(field)
            if value:
                initial[field] = value
        incoming = self.request.GET.get('incoming')
        if incoming:
            try:
                initial['incoming_waybill'] = Waybill.objects.get(
                    pk=incoming, waybill_type='incoming'
                )
            except Waybill.DoesNotExist:
                pass
        return initial

    def _notify_job_created(self, form):
        for mgr in get_users_with_perm('approve_calibration'):
            Notification.objects.create(
                recipient=mgr,
                message=f'New job created — PO: {form.instance.purchase_order_number or "N/A"}, Client: {form.instance.client.name}',
                link=reverse('job_detail', args=[form.instance.pk]),
                notification_type='new_job_created',
            )
        for person in form.instance.assigned_to.all():
            Notification.objects.create(
                recipient=person.user,
                message=f'A new job has been assigned to you — PO: {form.instance.purchase_order_number or "N/A"}, Client: {form.instance.client.name}',
                link=reverse('job_detail', args=[form.instance.pk]),
                notification_type='new_job_created',
            )

    def form_valid(self, form):
        response = super().form_valid(form)
        # When a waybill is captured onto a job, shift status to pre-cal pending
        # (unless the user explicitly chose a later status).
        if self.object.incoming_waybill_id and self.object.job_status == 'not_received':
            self.object.job_status = 'pre_calibration_pending'
            self.object.save(update_fields=['job_status'])
        self._notify_job_created(form)
        client = getattr(form, '_new_pending_client', None)
        if client:
            for user in User.objects.filter(is_superuser=True):
                Notification.objects.create(
                    recipient=user,
                    message=f'New client "{client.name}" was auto-created and needs more information.',
                    link=reverse('client_detail', args=[client.pk]),
                    notification_type='new_client_pending',
                )
        return response


class JobDetailView(LoginRequiredMixin, DetailView):
    model = Job
    template_name = 'core/jobs/detail.html'
    context_object_name = 'job'

    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        return ['core/jobs/managed_detail.html'] if self.object.workflow_managed else [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from . import ei_workflow as service
        from .ei_views import bootstrap
        service.require_job_read(self.request.user, self.object)
        if self.object.workflow_managed:
            context['is_supervisor'] = service.supervisor(self.request.user)
            submitted=self.object.submissions.first()
            review=getattr(submitted,'review',None) if submitted else None
            context['job_review']=review
            context['can_decide_job']=service.supervisor(self.request.user) and self.object.creator_id!=self.request.user.pk and (
                not review or service.lab_authority(self.request.user) and review.created_by_id!=self.request.user.pk)
            context['eligible_personnel'] = [p for p in service.active_personnel() if service.eligible(p, self.object)]
            context['can_commence'] = self.object.approval_state == 'approved' and self.object.assigned_to.filter(user=self.request.user).exists()
            context['may_edit'] = (self.object.creator_id == self.request.user.pk or service.lab_authority(self.request.user)) and self.object.approval_state in ('draft', 'reverted')
            context['job_bootstrap'] = bootstrap(self.request.user, self.object) if context['may_edit'] else None
            return context
        items = []
        if self.object.incoming_waybill:
            for item in self.object.incoming_waybill.items.all():
                logs = item.calibration_logs.all()
                latest_pre = item.pre_calibration_logs.first()
                items.append({
                    'item': item,
                    'logs': logs,
                    'has_logs': logs.exists(),
                    'latest_log': logs.first(),
                    'latest_pre': latest_pre,
                    'needs_review': latest_pre and not latest_pre.ready_for_calibration and not latest_pre.review_decision,
                })
        context['equipment_items'] = items
        context['outgoing_waybills'] = self.object.waybills.filter(waybill_type='outgoing')
        context['assignable_personnel'] = Personnel.objects.select_related('role').filter(user__is_active=True,employment_status='active').order_by('name')
        return context


class JobUpdateView(LoginRequiredMixin, UpdateView):
    model = Job
    form_class = JobForm
    template_name = 'core/jobs/create.html'
    success_url = reverse_lazy('job_list')

    def dispatch(self, request, *args, **kwargs):
        job = get_object_or_404(Job, pk=kwargs.get('pk'))
        if job.workflow_managed:
            return redirect(reverse('job_detail', args=[job.pk]) + '?edit=1')
        if not has_perm(request.user, 'edit_jobs'):
            messages.error(request, 'You do not have permission to edit jobs.')
            return redirect('job_list')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['calibration_types'] = CalibrationType.objects.all()
        return context

    def get_initial(self):
        initial = super().get_initial()
        for field in ('purchase_order_number', 'client', 'job_description'):
            value = self.request.GET.get(field)
            if value:
                initial[field] = value
        incoming = self.request.GET.get('incoming')
        if incoming:
            try:
                initial['incoming_waybill'] = Waybill.objects.get(
                    pk=incoming, waybill_type='incoming'
                )
            except Waybill.DoesNotExist:
                pass
        return initial

    def form_valid(self, form):
        response = super().form_valid(form)
        for mgr in get_users_with_perm('approve_calibration'):
            Notification.objects.create(
                recipient=mgr,
                message=f'Job updated — PO: {form.instance.purchase_order_number or "N/A"}, Client: {form.instance.client.name}',
                link=reverse('job_detail', args=[form.instance.pk]),
                notification_type='job_updated',
            )
        for person in form.instance.assigned_to.all():
            Notification.objects.create(
                recipient=person.user,
                message=f'Job #{form.instance.pk} assigned to you has been updated — PO: {form.instance.purchase_order_number or "N/A"}',
                link=reverse('job_detail', args=[form.instance.pk]),
                notification_type='job_updated',
            )
        client = getattr(form, '_new_pending_client', None)
        if client:
            for user in User.objects.filter(is_superuser=True):
                Notification.objects.create(
                    recipient=user,
                    message=f'New client "{client.name}" was auto-created and needs more information.',
                    link=reverse('client_detail', args=[client.pk]),
                    notification_type='new_client_pending',
                )
        return response


class JobDeleteView(LoginRequiredMixin, DeleteView):
    model = Job
    template_name = 'core/jobs/confirm_delete.html'
    success_url = reverse_lazy('job_list')

    def dispatch(self, request, *args, **kwargs):
        job = get_object_or_404(Job, pk=kwargs.get('pk'))
        if job.workflow_managed:
            messages.error(request, 'Controlled job records are retained for audit and cannot be hard-deleted.')
            return redirect('job_detail', pk=job.pk)
        if not has_perm(request.user, 'edit_jobs'):
            messages.error(request, 'You do not have permission to delete jobs.')
            return redirect('job_list')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['related_count'] = self.object.assigned_to.count()
        return context


class JobStatusListView(JobListView):
    model = Job
    template_name = 'core/jobs/list.html'
    context_object_name = 'jobs'
    paginate_by = 20

    def get_queryset(self):
        status = self.kwargs['status']
        status_map = {
            'open': 'not_received',
            'pre-calibration': 'pre_calibration_pending',
            'calibration': 'calibration_pending',
            'review': 'review_pending',
            'approval-pending': 'approval_pending',
            'repair-due': 'repair_due',
            'completed': 'completed',
            'dispatched': 'dispatched',
        }
        if status == 'ongoing':
            qs = super().get_queryset().filter(Q(workflow_managed=True, progress_status='ongoing') | (Q(workflow_managed=False) & ~Q(job_status__in=['not_received', 'completed', 'dispatched'])))
        else:
            db_status = status_map.get(status, status)
            mapped = {'open':'scheduled', 'pre-calibration':'pending', 'completed':'completed'}.get(status)
            query = Q(workflow_managed=False, job_status=db_status)
            if mapped:
                query |= Q(workflow_managed=True, progress_status=mapped)
            qs = super().get_queryset().filter(query)

        search = self.request.GET.get('search', '')
        if search:
            qs = qs.filter(
                Q(purchase_order_number__icontains=search) |
                Q(serial_no__icontains=search) |
                Q(client__name__icontains=search)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_filter'] = self.kwargs['status'].replace('-', ' ').title()
        context['filters'] = {
            'search': self.request.GET.get('search', ''),
        }
        context['clients'] = Client.objects.all()
        context['status_choices'] = Job.JOB_STATUS_CHOICES
        context['new_job_form'] = JobForm()
        context['client_names'] = Client.objects.values_list('name', flat=True)
        return context


# ─── Job assignment ──────────────────────────────────────────────────────────


@login_required
def job_assign(request, pk):
    job = get_object_or_404(Job, pk=pk)
    if job.workflow_managed:
        raise PermissionDenied('Use the logged supervisor assignment workflow.')
    if not has_perm(request.user, 'edit_jobs'):
        messages.error(request, 'You do not have permission to assign personnel to jobs.')
        return redirect('job_detail', pk=pk)
    if request.method != 'POST':
        return redirect('job_detail', pk=pk)
    personnel_id = request.POST.get('personnel')
    if personnel_id:
        try:
            person = Personnel.objects.get(pk=personnel_id)
            from .personnel_records import validate_analyst
            scopes=list(CalibrationType.objects.filter(waybill_items__waybill=job.incoming_waybill).distinct()) if job.incoming_waybill_id else []
            validate_analyst(person,scopes)
            job.assigned_to.add(person)
            if person.user:
                Notification.objects.create(
                    recipient=person.user,
                    message=f'You have been assigned to job — PO: {job.purchase_order_number or "N/A"}, Client: {job.client.name}',
                    link=reverse('job_detail', args=[pk]),
                    notification_type='new_job_created',
                )
            messages.success(request, f'{person.name} assigned to the job.')
        except Personnel.DoesNotExist:
            messages.error(request, 'Personnel not found.')
    else:
        messages.error(request, 'Please select personnel to assign.')
    return redirect('job_detail', pk=pk)


@login_required
def job_unassign(request, pk, personnel_id):
    job = get_object_or_404(Job, pk=pk)
    if job.workflow_managed:
        raise PermissionDenied('Use the logged supervisor assignment workflow.')
    if not has_perm(request.user, 'edit_jobs'):
        messages.error(request, 'You do not have permission to unassign personnel from jobs.')
        return redirect('job_detail', pk=pk)
    if request.method == 'POST':
        person = get_object_or_404(Personnel, pk=personnel_id)
        job.assigned_to.remove(person)
        messages.success(request, f'{person.name} removed from the job.')
    return redirect('job_detail', pk=pk)


# ─── Waybills ─────────────────────────────────────────────────────────────────


class WaybillListView(LoginRequiredMixin, ListView):
    model = Waybill
    template_name = 'core/waybills/list.html'
    context_object_name = 'waybills'
    paginate_by = 20

    def get_queryset(self):
        # Base queryset - we don't actually use this for the lists
        return Waybill.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        search = self.request.GET.get('q', '')
        base_qs = Waybill.objects.prefetch_related('items').order_by('-created_at')
        if search:
            base_qs = base_qs.filter(waybill_no__icontains=search)

        # Paginate incoming waybills
        incoming_qs = base_qs.filter(waybill_type='incoming').prefetch_related(
            Prefetch(
                'incoming_jobs',
                queryset=Job.objects.select_related('client'),
                to_attr='linked_jobs',
            )
        )
        incoming_paginator = Paginator(incoming_qs, 20)
        incoming_page = self.request.GET.get('incoming_page')
        context['incoming_waybills'] = incoming_paginator.get_page(incoming_page)

        # Paginate outgoing waybills (client via the linked incoming waybill's job)
        outgoing_qs = base_qs.filter(waybill_type='outgoing').select_related(
            'linked_incoming_waybill'
        ).prefetch_related(
            Prefetch(
                'linked_incoming_waybill__incoming_jobs',
                queryset=Job.objects.select_related('client'),
                to_attr='linked_jobs',
            )
        )
        outgoing_paginator = Paginator(outgoing_qs, 20)
        outgoing_page = self.request.GET.get('outgoing_page')
        context['outgoing_waybills'] = outgoing_paginator.get_page(outgoing_page)

        return context


class IncomingWaybillCreateView(LoginRequiredMixin, CreateView):
    model = Waybill
    form_class = IncomingWaybillWithAutoNumberForm
    template_name = 'core/waybills/incoming/create.html'
    success_url = reverse_lazy('waybill_list')

    def dispatch(self, request, *args, **kwargs):
        if not has_perm(request.user, 'create_waybills'):
            messages.error(request, 'You do not have permission to create waybills.')
            return redirect('waybill_list')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        numbers = []
        for wbn in Waybill.objects.values_list('waybill_no', flat=True):
            try:
                numbers.append(int(wbn))
            except (ValueError, TypeError):
                pass
        next_num = max(numbers) + 1 if numbers else 1
        kwargs['auto_number'] = str(next_num)
        return kwargs

    def get_context_data(self, **kwargs):
        from . import ocr_engine
        ctx = super().get_context_data(**kwargs)
        ctx['ocr_available'] = ocr_engine.is_available()
        ctx['can_scan'] = has_perm(self.request.user, 'create_waybills')
        return ctx

    def form_valid(self, form):
        form.instance.waybill_type = 'incoming'
        response = super().form_valid(form)

        sub_equipment_descriptions = self.request.POST.getlist('sub_equipment_description[]')
        sub_serial_nos = self.request.POST.getlist('sub_serial_no[]')
        sub_model_nos = self.request.POST.getlist('sub_model_no[]')
        sub_manufacturers = self.request.POST.getlist('sub_manufacturer[]')
        sub_ranges = self.request.POST.getlist('sub_range[]')

        for i in range(len(sub_serial_nos)):
            if sub_serial_nos[i]:
                WaybillItem.objects.create(
                    waybill=self.object,
                    equipment_description=sub_equipment_descriptions[i] if i < len(sub_equipment_descriptions) else '',
                    quantity=1,
                    serial_no=sub_serial_nos[i],
                    model_no=sub_model_nos[i] if i < len(sub_model_nos) else '',
                    manufacturer=sub_manufacturers[i] if i < len(sub_manufacturers) else '',
                    range_field=sub_ranges[i] if i < len(sub_ranges) else '',
                )

        return response

    def get_success_url(self):
        next_url = self.request.GET.get('next', '')
        if next_url:
            # request.GET has already decoded the browser's encodeURIComponent
            # layer once, so next_url holds a single-encoded query string.
            # Parse it properly instead of unquote()/quote() round-trips, which
            # corrupted spaces into '+' and left raw '&'/'=' inside values.
            base, _, query = next_url.partition('?')
            if url_has_allowed_host_and_scheme(base, allowed_hosts={None}):
                params = QueryDict(query, mutable=True) if query else QueryDict('', mutable=True)
                params['incoming'] = self.object.pk
                return f'{base}?{params.urlencode()}'
        return reverse('waybill_detail', kwargs={'pk': self.object.pk})


class WaybillDetailView(LoginRequiredMixin, DetailView):
    model = Waybill
    template_name = 'core/waybills/incoming/detail.html'
    context_object_name = 'waybill'

    def get_context_data(self, **kwargs):
        from . import ocr_engine
        context = super().get_context_data(**kwargs)
        items = []
        for item in self.object.items.all():
            logs = item.calibration_logs.all()
            latest_pre = item.pre_calibration_logs.first()
            items.append({
                'item': item,
                'logs': logs,
                'has_logs': logs.exists(),
                'latest_log': logs.first(),
                'latest_pre': latest_pre,
                'needs_review': latest_pre and not latest_pre.ready_for_calibration and not latest_pre.review_decision,
            })
        context['equipment_items'] = items
        context['ocr_available'] = ocr_engine.is_available() and bool(self.object.file_upload)
        context['can_rescan'] = has_perm(self.request.user, 'create_waybills')
        context['job'] = self.object.incoming_jobs.select_related('client').first()
        return context


class OutgoingWaybillCreateView(LoginRequiredMixin, CreateView):
    model = Waybill
    form_class = OutgoingWaybillForm
    template_name = 'core/waybills/outgoing/create.html'
    success_url = reverse_lazy('waybill_list')

    def dispatch(self, request, *args, **kwargs):
        if not has_perm(request.user, 'create_waybills'):
            messages.error(request, 'You do not have permission to create waybills.')
            return redirect('waybill_list')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        initial_incoming_no = ''
        job_id = self.request.GET.get('job')
        if job_id:
            job = Job.objects.filter(pk=job_id).first()
            if job and job.incoming_waybill_id:
                initial_incoming_no = job.incoming_waybill.waybill_no
        context['initial_incoming_no'] = initial_incoming_no
        incoming_no = self.request.GET.get('incoming')
        if incoming_no:
            try:
                incoming_wb = Waybill.objects.get(
                    waybill_no=incoming_no, waybill_type='incoming'
                )
                context['incoming_waybill'] = incoming_wb
                context['items'] = incoming_wb.items.all()
            except Waybill.DoesNotExist:
                pass
        jobs = Job.objects.select_related('client', 'incoming_waybill').order_by('-created_at')
        context['jobs'] = jobs
        # id -> {incoming_no, po} map for the client-side auto-fill / PO guard
        context['jobs_data'] = json.dumps({
            str(j.pk): {
                'incoming_no': j.incoming_waybill.waybill_no if j.incoming_waybill_id else '',
                'po': j.purchase_order_number or '',
                'client': j.client.name if j.client_id else '',
            } for j in jobs
        })
        return context

    def get_initial(self):
        initial = super().get_initial()
        job_id = self.request.GET.get('job')
        if job_id:
            try:
                job = Job.objects.get(pk=job_id)
                initial['job'] = job
            except Job.DoesNotExist:
                pass
        return initial

    def form_valid(self, form):
        form.instance.waybill_type = 'outgoing'
        response = super().form_valid(form)

        incoming_no = self.request.POST.get('incoming_waybill_no')
        selected_items = self.request.POST.getlist('selected_items')

        # Auto-pick: if no incoming waybill was typed but the job has one, link it.
        if not incoming_no and self.object.job_id and self.object.job.incoming_waybill_id:
            incoming_no = self.object.job.incoming_waybill.waybill_no

        if incoming_no:
            try:
                incoming_wb = Waybill.objects.get(
                    waybill_no=incoming_no, waybill_type='incoming'
                )
                self.object.linked_incoming_waybill = incoming_wb
                self.object.save()

                if selected_items:
                    for item_id in selected_items:
                        try:
                            original_item = WaybillItem.objects.get(
                                id=item_id, waybill=incoming_wb
                            )
                            WaybillItem.objects.create(
                                waybill=self.object,
                                equipment_description=original_item.equipment_description,
                                quantity=original_item.quantity,
                                serial_no=original_item.serial_no,
                                model_no=original_item.model_no,
                                manufacturer=original_item.manufacturer,
                                range_field=original_item.range_field,
                            )
                        except WaybillItem.DoesNotExist:
                            pass
            except Waybill.DoesNotExist:
                pass

        return response


class OutgoingWaybillDetailView(LoginRequiredMixin, DetailView):
    model = Waybill
    template_name = 'core/waybills/outgoing/detail.html'
    context_object_name = 'waybill'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        items = []
        for item in self.object.items.all():
            logs = item.calibration_logs.all()
            items.append({
                'item': item,
                'logs': logs,
                'has_logs': logs.exists(),
                'latest_log': logs.first(),
            })
        context['equipment_items'] = items
        linked = self.object.linked_incoming_waybill
        if linked:
            job = linked.incoming_jobs.select_related('client').first()
            context['client_name'] = job.client.name if job and job.client else None
        else:
            context['client_name'] = None
        return context


@login_required
def fetch_incoming_waybill(request):
    waybill_no = request.GET.get('waybill_no')
    try:
        waybill = Waybill.objects.get(waybill_no=waybill_no, waybill_type='incoming')
        items = waybill.items.all().values(
            'id', 'equipment_description', 'quantity', 'serial_no',
            'model_no', 'manufacturer', 'range_field'
        )
        return JsonResponse({
            'found': True,
            'waybill_id': waybill.id,
            'items': list(items),
        })
    except Waybill.DoesNotExist:
        return JsonResponse({'found': False})


# ─── Profile (Self-Service) ─────────────────────────────────────────────────


@login_required
def profile(request):
    person = None
    try:
        person = request.user.personnel_profile
    except Personnel.DoesNotExist:
        pass
    return render(request, 'core/profile/profile.html', {'person': person})


@login_required
def profile_edit(request):
    try:
        person = request.user.personnel_profile
    except Personnel.DoesNotExist:
        messages.error(request, 'No personnel profile found.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=person)
        email = request.POST.get('email', '').strip()
        if form.is_valid():
            form.save()
            if email:
                request.user.email = email
            request.user.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('profile')
    else:
        form = ProfileForm(instance=person)

    return render(request, 'core/profile/edit.html', {
        'form': form,
        'person': person,
    })


# ─── Personnel ────────────────────────────────────────────────────────────────


class PersonnelListView(LoginRequiredMixin, ListView):
    model = Personnel
    template_name = 'core/personnel/list.html'
    context_object_name = 'personnel'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_active:
            messages.error(request, 'You do not have permission to view personnel.')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        from .personnel_records import compliance
        qs = Personnel.objects.select_related('role', 'user').prefetch_related('evidence','authorizations','competencies','scope_of_expertise')
        search = self.request.GET.get('search', '')
        role_id = self.request.GET.get('role', '')
        if search:
            from django.db.models import Q
            query=Q(name__icontains=search)|Q(position__icontains=search)|Q(scope_of_expertise__name__icontains=search)
            if search.isdigit(): query |= Q(pk=int(search))
            qs = qs.filter(query).distinct()
        if role_id:
            qs = qs.filter(role_id=role_id)
        people=list(qs)
        for person in people:
            person.compliance=compliance(person)
        status=self.request.GET.get('status','')
        category=self.request.GET.get('category','authorization')
        if status in ('active','missing','expired','pending') and category in ('qualification','competency','authorization','training'):
            people=[p for p in people if p.compliance[category]['code']==status]
        return people

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filters'] = {
            'search': self.request.GET.get('search', ''),
            'role': self.request.GET.get('role', ''),
        }
        context['roles'] = Role.objects.all()
        from .personnel_records import flags
        context.update(flags(self.request.user))
        context['category']=self.request.GET.get('category','authorization')
        context['status']=self.request.GET.get('status','')
        return context


class PersonnelCreateView(LoginRequiredMixin, CreateView):
    model = Personnel
    form_class = PersonnelForm
    template_name = 'core/personnel/create.html'
    success_url = reverse_lazy('personnel_list')

    def get_form(self, form_class=None):
        from .personnel_records import assignable_roles
        form=super().get_form(form_class)
        form.fields['role'].queryset=assignable_roles(self.request.user)
        return form

    def dispatch(self, request, *args, **kwargs):
        if not has_perm(request.user, 'manage_personnel'):
            messages.error(request, 'Only administrators can create personnel.')
            return redirect('personnel_list')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['roles'] = context['form'].fields['role'].queryset
        context['calibration_types'] = CalibrationType.objects.all()
        return context

    @transaction.atomic
    def form_valid(self, form):
        person = form.save(commit=False)
        from .models import PersonnelProfileRevision
        from .ei_workflow import actor_fields
        before = {}
        username = form.cleaned_data['login_username']
        user = User.objects.create_user(username=username, password=form.cleaned_data['temporary_password'])
        person.user = user
        person.experience_as_of = person.experience_as_of or timezone.localdate()
        person.save()
        form.save_m2m()
        PersonnelProfileRevision.objects.create(personnel=person, snapshot={'before':before, 'after':{name:str(getattr(person,name)) for name in ('name', 'role_id', 'qualifications', 'years_of_experience')}}, **actor_fields(self.request.user))
        return super().form_valid(form)


class PersonnelDetailView(LoginRequiredMixin, DetailView):
    def get(self, request, *args, **kwargs):
        from .ei_views import personnel_workspace
        return personnel_workspace(request, pk=kwargs['pk'])
    model = Personnel
    template_name = 'core/personnel/detail.html'
    context_object_name = 'personnel'


class PersonnelUpdateView(LoginRequiredMixin, UpdateView):
    model = Personnel
    form_class = PersonnelForm
    template_name = 'core/personnel/create.html'
    success_url = reverse_lazy('personnel_list')

    def get_form(self, form_class=None):
        from .personnel_records import assignable_roles
        from django.core.exceptions import PermissionDenied
        form=super().get_form(form_class)
        allowed=assignable_roles(self.request.user)
        if self.object.role_id and not allowed.filter(pk=self.object.role_id).exists():
            raise PermissionDenied('Only an administrator may maintain personnel with privileged roles.')
        form.fields['role'].queryset=allowed
        return form

    def dispatch(self, request, *args, **kwargs):
        if not has_perm(request.user, 'manage_personnel'):
            messages.error(request, 'Only administrators can edit personnel.')
            return redirect('personnel_list')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_edit'] = True
        context['roles'] = context['form'].fields['role'].queryset
        context['calibration_types'] = CalibrationType.objects.all()
        return context

    def form_valid(self, form):
        person = form.save(commit=False)
        from .models import PersonnelProfileRevision
        from .ei_workflow import actor_fields
        prior = Personnel.objects.get(pk=person.pk)
        before = {name:str(getattr(prior,name)) for name in ('name', 'role_id', 'qualifications', 'years_of_experience')}
        person.save()
        form.save_m2m()
        PersonnelProfileRevision.objects.create(personnel=person, snapshot={'before':before, 'after':{name:str(getattr(person,name)) for name in before}}, **actor_fields(self.request.user))
        return super().form_valid(form)


class PersonnelDeleteView(LoginRequiredMixin, DeleteView):
    model = Personnel
    template_name = 'core/personnel/confirm_delete.html'
    success_url = reverse_lazy('personnel_list')

    def dispatch(self, request, *args, **kwargs):
        if not has_perm(request.user, 'manage_personnel'):
            messages.error(request, 'Only administrators can delete personnel.')
            return redirect('personnel_list')
        person = get_object_or_404(Personnel, pk=kwargs.get('pk'))
        if person.evidence.exists() or person.authorizations.exists() or person.competencies.exists() or person.assigned_jobs.filter(workflow_managed=True).exists():
            messages.error(request, 'Personnel with controlled history must be deactivated rather than deleted.')
            return redirect('ei_personnel_workspace', pk=person.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['calibration_logs_count'] = CalibrationLog.objects.filter(calibrated_by=self.object).count()
        context['assigned_jobs_count'] = Job.objects.filter(assigned_to=self.object).count()
        return context


@login_required
def personnel_qr_card(request, pk):
    person = get_object_or_404(Personnel, pk=pk)
    from .ei_views import require_personnel
    require_personnel(request.user, person)
    url = request.build_absolute_uri(reverse('ei_personnel_verify', kwargs={'token': person.verification_token}))
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

    if request.GET.get('format') == 'card':
        return render(request, 'core/personnel/qr_card.html', {
            'person': person,
            'qr_data': qr_b64,
        })

    return render(request, 'core/personnel/detail.html', {
        'personnel': person,
        'qr_data': qr_b64,
    })


@login_required
def qr_login(request, token):
    signer = TimestampSigner()
    try:
        user_id = signer.unsign(token, max_age=365 * 86400)
    except (SignatureExpired, BadSignature):
        return render(request, 'core/auth/login.html', {
            'error': 'Invalid or expired QR code. Please contact your administrator.',
        })

    user = get_object_or_404(User, pk=user_id)
    try:
        person = Personnel.objects.get(user=user)
        from .ei_views import personnel_workspace
        return personnel_workspace(request, pk=person.pk)
    except Personnel.DoesNotExist:
        return redirect('dashboard')


@login_required
def personnel_by_scope(request):
    from .ei_workflow import active_personnel
    scope_id = request.GET.get('scope')
    if scope_id:
        personnel = active_personnel().filter(scope_of_expertise__id=scope_id).distinct()
    else:
        personnel = active_personnel()
    data = [{'id': p.id, 'name': p.name, 'role_name': p.role.name if p.role else ''} for p in personnel]
    return JsonResponse(data, safe=False)


@login_required
def units_by_scope(request, scope_id):
    """Units available for a scope (path arg) — or a comma-separated list of
    scopes via ?scopes=1,2,3.

    ?primary_only=1  → limit to units that have an active reference standard.
    ?range=0-10 bar  → also require at least one standard whose range fully
                       contains the equipment range.
    Each unit carries `available` (active standard exists) and `range_ok`
    (range containment satisfied). Used by the pre-cal and cal-log pages.
    """
    from .matching import available_unit_ids
    from .models import Unit

    scope_ids = []
    if request.GET.get('scopes'):
        scope_ids = [int(s) for s in request.GET.get('scopes').split(',') if s.strip().isdigit()]
    if scope_id and str(scope_id) != '0':
        scope_ids.insert(0, int(scope_id))
    scope_ids = list(dict.fromkeys(scope_ids))
    refresh = request.GET.get('refresh') == '1'
    range_str = request.GET.get('range')
    primary_only = request.GET.get('primary_only') == '1'

    if scope_ids:
        for sid in scope_ids:
            sc = CalibrationType.objects.filter(pk=sid).first()
            if sc:
                units_for_scope(sc, refresh=refresh)
        base = Unit.objects.filter(scope_id__in=scope_ids)
    else:
        base = Unit.objects.all()

    with_standard = set(available_unit_ids(scope_ids, None, require_containment=False))
    covers = set(available_unit_ids(scope_ids, range_str, require_containment=True))

    if primary_only:
        usable = covers if range_str else with_standard
        base = base.filter(id__in=usable) if usable else base.none()

    data = [{
        'id': u.id, 'name': u.name, 'symbol': u.symbol, 'scope_id': u.scope_id,
        'available': u.id in with_standard, 'range_ok': u.id in covers,
    } for u in base.order_by('name')]
    return JsonResponse(data, safe=False)


@login_required
def procedure_for_scope(request, scope_id):
    """Active calibration procedure for a scope (used by the cal-log create page)."""
    proc = CalibrationProcedure.objects.filter(
        scope_id=scope_id, status='active').first()
    if not proc:
        return JsonResponse({})
    return JsonResponse({
        'id': proc.pk,
        'title': proc.title,
        'manual_reference': proc.manual_reference,
        'instructions': proc.instructions,
        'test_points_percent': proc.test_points_percent or [],
        'tolerance_pct': float(proc.tolerance_pct) if proc.tolerance_pct is not None else None,
    })


# ─── Calibration Procedures ──────────────────────────────────────────────────


def _can_approve_procedure(user):
    return user.is_superuser or has_perm(user, 'approve_calibration')


@login_required
def procedure_list(request):
    procedures = CalibrationProcedure.objects.select_related(
        'scope', 'assigned_to', 'created_by').all()
    scopes = CalibrationType.objects.all()
    scope_id = request.GET.get('scope')
    status = request.GET.get('status')
    if scope_id:
        procedures = procedures.filter(scope_id=scope_id)
    if status:
        procedures = procedures.filter(status=status)
    paginator = Paginator(procedures, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'core/procedures/list.html', {
        'page_obj': page_obj,
        'scopes': scopes,
        'status_choices': CalibrationProcedure.STATUS_CHOICES,
        'result_count': paginator.count,
    })


@login_required
def procedure_detail(request, pk):
    proc = get_object_or_404(
        CalibrationProcedure.objects.select_related('scope', 'assigned_to', 'created_by', 'approved_by'),
        pk=pk)
    can_edit = (
        proc.status == 'draft' and proc.assigned_to and
        getattr(proc.assigned_to, 'user', None) == request.user
    )
    context = {
        'procedure': proc,
        'steps': [s for s in proc.instructions.splitlines() if s.strip()],
        'test_points': proc.test_points_percent or [],
        'can_edit': can_edit,
        'can_assign': _can_approve_procedure(request.user),
        'can_review': _can_approve_procedure(request.user) and proc.status == 'pending_approval',
    }
    if request.method == 'POST':
        # Approve / reject from the detail page
        if not context['can_review']:
            messages.error(request, 'Only supervisors/managers can approve procedures, and only while pending approval.')
            return redirect('procedure_detail', pk=pk)
        action = request.POST.get('action')
        if action == 'approve':
            proc.status = 'active'
            proc.approved_by = request.user
            proc.save()
            notify_users(
                ([proc.assigned_to.user] if proc.assigned_to and proc.assigned_to.user else []) +
                ([proc.created_by] if proc.created_by else []),
                f'Calibration procedure approved — {proc.title} ({proc.scope.name})',
                reverse('procedure_detail', args=[pk]),
                'procedure_approved',
            )
            messages.success(request, 'Procedure approved and set active.')
        elif action == 'reject':
            reason = request.POST.get('notes', '').strip()
            proc.status = 'rejected'
            proc.review_notes = reason
            proc.save()
            notify_users(
                ([proc.assigned_to.user] if proc.assigned_to and proc.assigned_to.user else []) +
                ([proc.created_by] if proc.created_by else []),
                f'Calibration procedure rejected — {proc.title}: {reason}',
                reverse('procedure_detail', args=[pk]),
                'procedure_rejected',
            )
            messages.success(request, 'Procedure rejected and returned as draft-ready feedback.')
        return redirect('procedure_detail', pk=pk)
    return render(request, 'core/procedures/detail.html', context)


@login_required
def procedure_assign(request):
    """Supervisor assigns a scope + technician; creates a draft procedure."""
    if not _can_approve_procedure(request.user):
        messages.error(request, 'Only supervisors/managers can assign calibration procedures.')
        return redirect('procedure_list')
    personnel_qs = Personnel.objects.select_related('user').filter(user__isnull=False).order_by('name')
    initial_scope = request.GET.get('scope')
    if request.method == 'POST':
        form = ProcedureAssignForm(request.POST)
        if form.is_valid():
            proc = form.save(commit=False)
            proc.status = 'draft'
            proc.created_by = request.user
            proc.version = 1
            proc.save()
            proc.assign_doc_no()
            if proc.assigned_to and proc.assigned_to.user:
                notify_users(
                    [proc.assigned_to.user],
                    f'A calibration procedure was assigned to you — {proc.title} ({proc.scope.name})',
                    reverse('procedure_edit', args=[proc.pk]),
                    'procedure_assigned',
                )
            messages.success(request, 'Procedure assigned.')
            return redirect('procedure_detail', pk=proc.pk)
    else:
        form = ProcedureAssignForm(initial={'scope': initial_scope} if initial_scope else None)
    return render(request, 'core/procedures/assign.html', {
        'form': form,
        'personnel': personnel_qs,
    })


@login_required
def procedure_edit(request, pk):
    proc = get_object_or_404(CalibrationProcedure, pk=pk)
    is_assignee = proc.assigned_to and getattr(proc.assigned_to, 'user', None) == request.user
    if not (is_assignee or _can_approve_procedure(request.user)):
        messages.error(request, 'Only the assigned technician can edit this procedure.')
        return redirect('procedure_detail', pk=pk)
    if proc.status not in ('draft', 'rejected'):
        messages.error(request, 'Only draft/rejected procedures can be edited.')
        return redirect('procedure_detail', pk=pk)

    ProcedureFormMod = modelform_factory(
        CalibrationProcedure,
        fields=['title', 'manual_reference', 'instructions', 'test_points_percent', 'tolerance_pct'],
        widgets={
            'instructions': FormTextarea(attrs={'rows': 10, 'class': 'font-mono text-sm'}),
        },
    )
    if request.method == 'POST':
        form = ProcedureFormMod(request.POST, instance=proc)
        if form.is_valid():
            saved = form.save()
            saved.status = 'draft'
            saved.review_notes = ''
            saved.save()
            if request.POST.get('submit') == 'submit':
                saved.status = 'pending_approval'
                saved.save(update_fields=['status'])
                notify_users(
                    get_users_with_perm('approve_calibration'),
                    f'Calibration procedure submitted for approval — {saved.title} ({saved.scope.name})',
                    reverse('procedure_detail', args=[saved.pk]),
                    'procedure_submitted',
                )
                messages.success(request, 'Procedure submitted for approval.')
            else:
                messages.success(request, 'Draft saved.')
            return redirect('procedure_detail', pk=saved.pk)
    else:
        form = ProcedureFormMod(instance=proc)
    return render(request, 'core/procedures/edit.html', {
        'form': form,
        'procedure': proc,
        'test_points_json': json.dumps(proc.test_points_percent or []),
    })


@login_required
@require_POST
def procedure_submit(request, pk):
    proc = get_object_or_404(CalibrationProcedure, pk=pk)
    is_assignee = proc.assigned_to and getattr(proc.assigned_to, 'user', None) == request.user
    if not (is_assignee or _can_approve_procedure(request.user)):
        messages.error(request, 'Only the assigned technician can submit this procedure.')
        return redirect('procedure_detail', pk=pk)
    if proc.status != 'draft':
        messages.warning(request, 'Only draft procedures can be submitted.')
        return redirect('procedure_detail', pk=pk)
    proc.status = 'pending_approval'
    proc.save(update_fields=['status'])
    notify_users(
        get_users_with_perm('approve_calibration'),
        f'Calibration procedure submitted for approval — {proc.title} ({proc.scope.name})',
        reverse('procedure_detail', args=[pk]),
        'procedure_submitted',
    )
    messages.success(request, 'Procedure submitted for approval.')
    return redirect('procedure_detail', pk=pk)


@login_required
def client_lookup(request):
    name = request.GET.get('name', '').strip()
    if name:
        client = Client.objects.filter(name__iexact=name).first()
        if client:
            return JsonResponse({
                'found': True,
                'name': client.name,
                'email': client.email or '',
                'phone': client.phone or '',
                'address': client.address or '',
            })
    return JsonResponse({'found': False})


# ─── Entry & Dispatch Log ─────────────────────────────────────────────────────


def _initials(name):
    if not name:
        return '-'
    letters = [part[0].upper() for part in name.split() if part]
    return ''.join(letters[:3]) or '-'


@login_required
def entry_dispatch_log(request):
    """One row per incoming-waybill equipment item, aggregating the lifecycle
    data from jobs, pre-calibration, calibration logs, and outgoing waybills."""
    items = WaybillItem.objects.filter(
        waybill__waybill_type='incoming'
    ).select_related('waybill', 'scope').order_by('-waybill__created_at')

    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    if q:
        items = items.filter(
            Q(equipment_description__icontains=q) |
            Q(serial_no__icontains=q) |
            Q(model_no__icontains=q) |
            Q(waybill__waybill_no__icontains=q)
        )
    if status:
        items = items.filter(status=status)

    item_ids = [it.pk for it in items]
    wb_ids = {it.waybill_id for it in items}

    jobs_by_wb = {
        j.incoming_waybill_id: j
        for j in Job.objects.filter(incoming_waybill_id__in=wb_ids).select_related('client')
    }

    cal_logs = {}
    for cl in (CalibrationLog.objects
               .filter(waybill_item_id__in=item_ids)
               .select_related('calibrated_by', 'scope')
               .order_by('waybill_item_id', '-created_at')):
        cal_logs.setdefault(cl.waybill_item_id, cl)

    pre_cal_latest = {}
    repair_items = set()
    for pc in (PreCalibrationLog.objects
               .filter(waybill_item_id__in=item_ids)
               .order_by('waybill_item_id', '-created_at')):
        pre_cal_latest.setdefault(pc.waybill_item_id, pc)
        if pc.review_decision == 'repair':
            repair_items.add(pc.waybill_item_id)

    outgoing_by_key = {}
    for wb in (Waybill.objects
               .filter(waybill_type='outgoing', linked_incoming_waybill_id__in=wb_ids)
               .prefetch_related('items')):
        for it in wb.items.all():
            outgoing_by_key.setdefault((wb.linked_incoming_waybill_id, it.serial_no), wb)

    rows = []
    for item in items:
        job = jobs_by_wb.get(item.waybill_id)
        cal_log = cal_logs.get(item.pk)
        pre_cal = pre_cal_latest.get(item.pk)
        outgoing = outgoing_by_key.get((item.waybill_id, item.serial_no))
        is_repair = item.pk in repair_items

        remarks_parts = []
        if pre_cal and pre_cal.remarks:
            remarks_parts.append(pre_cal.remarks)
        if cal_log and cal_log.notes:
            remarks_parts.append(cal_log.notes)

        scope_name = item.scope.name if item.scope_id else (cal_log.scope.name if cal_log and cal_log.scope_id else '-')

        rows.append({
            'item': item,
            'job': job,
            'cal_log': cal_log,
            'outgoing': outgoing,
            'client_name': job.client.name if job and job.client_id else '-',
            'date_received': item.waybill.created_at.date(),
            'date_calibrated': cal_log.calibrated_at_date if cal_log else None,
            'date_returned': outgoing.created_at.date() if outgoing else None,
            'certificate_no': (cal_log.certificate_no if cal_log and cal_log.certificate_no else None),
            'service_full': 'Calibration + Repair' if is_repair else 'Calibration',
            'service_short': 'Cal + Repair' if is_repair else 'Cal',
            'remarks': ' | '.join(remarks_parts),
            'initials': _initials(cal_log.calibrated_by.name) if cal_log and cal_log.calibrated_by else '-',
            'scope_name': scope_name,
        })

    paginator = Paginator(rows, 25)
    page = paginator.get_page(request.GET.get('page'))
    start_index = paginator.per_page * (page.number - 1) + 1 if rows else 0
    end_index = start_index + len(page.object_list) - 1 if rows else 0

    status_choices = WaybillItem.WAYBILL_ITEM_STATUS_CHOICES
    return render(request, 'core/waybills/entry_dispatch.html', {
        'rows': page,
        'page_obj': page,
        'start_index': start_index,
        'end_index': end_index,
        'total_count': paginator.count,
        'status_choices': status_choices,
        'filters': {'q': q, 'status': status},
    })


# ─── Environment ──────────────────────────────────────────────────────────────


class EnvironmentListView(LoginRequiredMixin, ListView):
    model = EnvironmentRecord
    template_name = 'core/environment/list.html'
    context_object_name = 'records'
    paginate_by = 20

    def get_queryset(self):
        qs = EnvironmentRecord.objects.select_related('recorded_by', 'location')
        from_date = self.request.GET.get('from_date', '')
        to_date = self.request.GET.get('to_date', '')
        location = self.request.GET.get('location', '')
        if from_date:
            qs = qs.filter(date__gte=from_date)
        if to_date:
            qs = qs.filter(date__lte=to_date)
        if location:
            qs = qs.filter(location_id=location)
        return qs.order_by('-date', '-time')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = date.today()
        location = self.request.GET.get('location', '')
        reminders = EnvironmentReminder.objects.filter(date=today)
        if location:
            reminders = reminders.filter(location_id=location)
        context['reminders'] = reminders
        context['locations'] = Location.objects.all()
        context['filters'] = {
            'from_date': self.request.GET.get('from_date', ''),
            'to_date': self.request.GET.get('to_date', ''),
            'location': location,
        }
        return context


class EnvironmentCreateView(LoginRequiredMixin, CreateView):
    model = EnvironmentRecord
    form_class = EnvironmentRecordForm
    template_name = 'core/environment/create.html'
    success_url = reverse_lazy('environment_list')

    def dispatch(self, request, *args, **kwargs):
        if not has_perm(request.user, 'record_environment'):
            messages.error(request, 'You do not have permission to record environment conditions.')
            return redirect('environment_list')
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial['date'] = date.today()
        req_location = self.request.GET.get('location', '')
        if req_location:
            initial['location'] = req_location
        else:
            latest = EnvironmentRecord.objects.order_by('-date', '-time').first()
            if latest:
                initial['location'] = latest.location_id
                initial['time'] = latest.time
            else:
                first_location = Location.objects.first()
                if first_location:
                    initial['location'] = first_location.pk
                hour = timezone.localtime().hour
                if hour < 10:
                    initial['time'] = '08'
                elif hour < 15:
                    initial['time'] = '12'
                else:
                    initial['time'] = '17'
        return initial

    def form_valid(self, form):
        form.instance.recorded_by = self.request.user
        response = super().form_valid(form)
        self.object.assign_doc_no()

        EnvironmentReminder.objects.update_or_create(
            date=self.object.date,
            time=self.object.time,
            location_id=self.object.location_id,
            defaults={
                'is_recorded': True,
                'recorded_at': timezone.now(),
            }
        )

        lab = f" for {self.object.location.name}" if self.object.location_id else ""
        notify_users(
            personnel_users(exclude_user=self.request.user),
            (
                f'Environment recorded{lab} — {self.object.date} {self.object.get_time_display()} '
                f'({self.object.temperature}\u00b0C, {self.object.relative_humidity}% RH) '
                f'by {self.request.user.get_full_name() or self.request.user.username}.'
            ),
            reverse('environment_list') + (f'?location={self.object.location_id}' if self.object.location_id else ''),
            'environment_recorded',
        )

        return response


@login_required
def environment_data(request):
    days = int(request.GET.get('days', 30))
    start_date = date.today() - timedelta(days=days)
    location = request.GET.get('location', '')

    records = EnvironmentRecord.objects.filter(
        date__gte=start_date
    )
    if location:
        records = records.filter(location_id=location)
    records = records.order_by('date', 'time')

    date_labels = []
    temp_08, temp_12, temp_17 = [], [], []
    hum_08, hum_12, hum_17 = [], [], []

    grouped = {}
    for r in records:
        key = r.date.isoformat()
        if key not in grouped:
            grouped[key] = {}
        grouped[key][r.time] = r

    for date_str in sorted(grouped.keys()):
        date_labels.append(date_str)
        day = grouped[date_str]
        t08 = day.get('08')
        t12 = day.get('12')
        t17 = day.get('17')
        temp_08.append(float(t08.temperature) if t08 else None)
        temp_12.append(float(t12.temperature) if t12 else None)
        temp_17.append(float(t17.temperature) if t17 else None)
        hum_08.append(float(t08.relative_humidity) if t08 else None)
        hum_12.append(float(t12.relative_humidity) if t12 else None)
        hum_17.append(float(t17.relative_humidity) if t17 else None)

    return JsonResponse({
        'labels': date_labels,
        'temp_08': temp_08, 'temp_12': temp_12, 'temp_17': temp_17,
        'hum_08': hum_08, 'hum_12': hum_12, 'hum_17': hum_17,
    })


@login_required
def environment_export(request):
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

    from_date = request.GET.get('from_date', '')
    to_date = request.GET.get('to_date', '')
    location = request.GET.get('location', '')

    records = EnvironmentRecord.objects.select_related('recorded_by', 'location').all()
    if from_date:
        records = records.filter(date__gte=from_date)
    if to_date:
        records = records.filter(date__lte=to_date)
    if location:
        records = records.filter(location_id=location)
    records = records.order_by('date', 'time')

    wb = Workbook()
    ws = wb.active
    ws.title = 'Environment Records'

    header_font = Font(bold=True, color='FFFFFF', size=11)
    header_fill = PatternFill(start_color='2563EB', end_color='2563EB', fill_type='solid')
    header_align = Alignment(horizontal='center', vertical='center')
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    headers = ['Date', 'Time', 'Lab / Location', 'Temperature (°C)', 'Humidity (%)', 'Recorded By']
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border

    time_labels = {'08': '08:00 Hrs', '12': '12:00 Hrs', '17': '17:00 Hrs'}
    for i, r in enumerate(records, 2):
        ws.cell(row=i, column=1, value=r.date.isoformat()).border = thin_border
        ws.cell(row=i, column=2, value=time_labels.get(r.time, r.time)).border = thin_border
        ws.cell(row=i, column=3, value=r.location.name if r.location_id else '').border = thin_border
        ws.cell(row=i, column=4, value=float(r.temperature)).border = thin_border
        ws.cell(row=i, column=5, value=float(r.relative_humidity)).border = thin_border
        ws.cell(row=i, column=6, value=r.recorded_by.username if r.recorded_by else '').border = thin_border

    ws.column_dimensions['A'].width = 14
    ws.column_dimensions['B'].width = 14
    ws.column_dimensions['C'].width = 18
    ws.column_dimensions['D'].width = 18
    ws.column_dimensions['E'].width = 16
    ws.column_dimensions['F'].width = 18

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    custom_name = request.GET.get('filename', '').strip()
    safe_name = re.sub(r'[^A-Za-z0-9._-]', '_', custom_name) if custom_name else ''
    if safe_name and not safe_name.lower().endswith('.xlsx'):
        safe_name += '.xlsx'
    if not safe_name:
        safe_name = 'environment_records'
        if from_date or to_date:
            parts = []
            if from_date:
                parts.append(from_date)
            if to_date:
                parts.append(to_date)
            safe_name += f'_{"_".join(parts)}'
        safe_name += '.xlsx'
    response['Content-Disposition'] = f'attachment; filename="{safe_name}"'
    wb.save(response)
    return response


# ─── Documents export (ISO 17025 yearly archive) ──────────────────────────────


def _sanitize_fs_part(value):
    """Filesystem-safe folder/file name: strip separators + windows-invalid chars."""
    return re.sub(r'[/\\:*?"<>|]', '_', (value or '').strip() or 'unnamed')


def _waybill_client(waybill):
    """Resolve the owning client for any waybill (incoming via Job.incoming_waybill,
    outgoing via Waybill.job then linked incoming), matching the list/detail views."""
    job = None
    if waybill.waybill_type == 'incoming':
        job = Job.objects.filter(incoming_waybill=waybill).select_related('client').first()
    elif waybill.job_id:
        job = Job.objects.select_related('client').filter(pk=waybill.job_id).first()
    elif waybill.linked_incoming_waybill_id:
        job = Job.objects.filter(incoming_waybill=waybill.linked_incoming_waybill).select_related('client').first()
    return job.client if job else None


def _render_certificate_html(log, context, request):
    """Render the effective certificate layout (per-scope custom or default) to an HTML string."""
    from django.template import engines
    scope_tpl = log.scope.certificate_template if log.scope_id else ''
    if scope_tpl and scope_tpl.strip():
        tpl = engines['django'].from_string(scope_tpl)
        return tpl.render(context, request)
    return engines['django'].get_template('core/calibration_logs/certificate.html').render(context, request)


def _document_years():
    """Sorted list of years that contain exportable documents (newest first)."""
    years = set()
    for q in (
        CalibrationLog.objects.exclude(calibrated_at_date__isnull=True).values_list('calibrated_at_date', flat=True),
        Waybill.objects.values_list('created_at', flat=True),
        EnvironmentRecord.objects.values_list('date', flat=True),
        CalibrationProcedure.objects.values_list('created_at', flat=True),
    ):
        for dt in q.iterator():
            years.add(dt.year)
            if len(years) > 40:
                break
    return sorted(years, reverse=True)


@login_required
def documents_list(request):
    if not (has_perm(request.user, 'view_waybills') or has_perm(request.user, 'approve_calibration')):
        messages.error(request, 'You do not have permission to view archived documents.')
        return redirect('dashboard')
    rows = []
    for year in _document_years():
        rows.append({
            'year': year,
            'certificates': CalibrationLog.objects.filter(calibrated_at_date__year=year).count(),
            'waybills': Waybill.objects.filter(created_at__year=year).count(),
            'env_records': EnvironmentRecord.objects.filter(date__year=year).count(),
            'procedures': CalibrationProcedure.objects.filter(created_at__year=year).count(),
        })
    return render(request, 'core/documents/year_list.html', {'rows': rows})


@login_required
def documents_export_year(request, year):
    """Produce the yearly ISO 17025 batch archive as one ZIP + registers.xlsx.

    Layout: Year/{ClientAbbr}/{ScopeAbbr}/{equipment}_{serial}/certificates/...,
    Year/waybills/{ClientAbbr}/{waybill_no}/uploaded_waybills/...,
    Year/env/{Location.name}/{08|12|17}/, Year/procedures/{ScopeAbbr}/{doc_no}/.
    """
    from zipfile import ZipFile, ZIP_DEFLATED
    from io import BytesIO
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

    try:
        year = int(year)
    except (TypeError, ValueError):
        messages.error(request, 'Invalid year.')
        return redirect('documents_list')
    if not (has_perm(request.user, 'view_waybills') or has_perm(request.user, 'approve_calibration')):
        messages.error(request, 'You do not have permission to export documents.')
        return redirect('dashboard')

    buf = BytesIO()
    with ZipFile(buf, 'w', ZIP_DEFLATED) as zf:
        cert_rows, wb_rows, env_rows, proc_rows = [], [], [], []

        tests = CalibrationLog.objects.filter(
            calibrated_at_date__year=year
        ).select_related(
            'waybill_item', 'scope', 'equipment_owner', 'calibrated_by'
        ).prefetch_related('scopes', 'standards', 'specs')
        for log in tests:
            client = log.equipment_owner
            client_abbr = abbreviation_for(client.abbreviation, client.name) if client else '-'
            scope_abbr = abbreviation_for(log.scope.abbreviation, log.scope.name) if log.scope_id else '-'
            folder = _sanitize_fs_part(log.equipment_desc or 'equipment')
            if log.serial_no:
                folder += f'_{_sanitize_fs_part(log.serial_no)}'
            base = f'{year}/{client_abbr}/{scope_abbr}/{folder}'
            context = _certificate_context(log)
            html = _render_certificate_html(log, context, request)
            stem = _sanitize_fs_part(log.certificate_no or f'{log.calibrated_at_date:%Y%m%d}-{log.pk}')
            zf.writestr(f'{base}/certificates/{stem}.html', html)
            if log.certificate and log.certificate.name:
                try:
                    with log.certificate.open('rb') as f:
                        ofile = os.path.basename(log.certificate.name)
                        if not ofile:
                            ofile = f'{stem}.file'
                        zf.writestr(f'{base}/certificates/{ofile}', f.read())
                except (FileNotFoundError, ValueError, OSError):
                    pass
            cert_rows.append([
                log.certificate_no, log.calibrated_at_date, log.equipment_desc,
                log.serial_no, client.name if client else '-',
                ', '.join(s.name for s in log.scopes.all()) or (log.scope.name if log.scope_id else '-'),
                log.get_status_display(), log.get_pass_fail_display(),
                float(log.expanded_uncertainty) if log.expanded_uncertainty is not None else '',
            ])

        waybills = Waybill.objects.filter(created_at__year=year).select_related('job__client', 'linked_incoming_waybill')
        for wb in waybills.iterator():
            client = _waybill_client(wb)
            client_abbr = abbreviation_for(client.abbreviation, client.name) if client else 'waybills'
            folder = _sanitize_fs_part(wb.waybill_no)
            if wb.file_upload and wb.file_upload.name:
                try:
                    with wb.file_upload.open('rb') as f:
                        zf.writestr(
                            f'{year}/waybills/{client_abbr}/{folder}/uploaded_waybills/{os.path.basename(wb.file_upload.name)}',
                            f.read(),
                        )
                except (FileNotFoundError, ValueError, OSError):
                    pass
            wb_rows.append([
                wb.waybill_no, wb.get_waybill_type_display(),
                client.name if client else '-', wb.created_at.date(),
                os.path.basename(wb.file_upload.name) if wb.file_upload and wb.file_upload.name else '',
            ])

        env_records = EnvironmentRecord.objects.filter(date__year=year).select_related('location', 'recorded_by')
        for rec in env_records.iterator():
            abbr = abbreviation_for(None, rec.location.name) if rec.location_id else '-'
            lab = _sanitize_fs_part(rec.location.name) if rec.location_id else '_unassigned'
            from django.template import engines
            tpl = engines['django'].get_template('core/documents/env_record.html').render({'rec': rec, 'seq_abbr': abbr}, request)
            zf.writestr(f'{year}/env/{lab}/{rec.time}/{_sanitize_fs_part(rec.doc_no)}.html', tpl)
            env_rows.append([
                rec.doc_no, rec.date, rec.get_time_display(),
                rec.location.name if rec.location_id else '-',
                float(rec.temperature), float(rec.relative_humidity),
                rec.recorded_by.get_full_name() if rec.recorded_by else '',
            ])

        procs = CalibrationProcedure.objects.filter(created_at__year=year).select_related('scope', 'assigned_to')
        for proc in procs.iterator():
            scope_abbr = abbreviation_for(proc.scope.abbreviation, proc.scope.name) if proc.scope_id else '-'
            folder = _sanitize_fs_part(proc.doc_no or f'PROC-{proc.pk}')
            from django.template import engines
            tpl = engines['django'].get_template('core/documents/procedure_record.html').render({'proc': proc, 'scope_abbr': scope_abbr}, request)
            zf.writestr(f'{year}/procedures/{scope_abbr}/{folder}/{folder}.html', tpl)
            proc_rows.append([
                proc.doc_no, proc.title, proc.scope.name if proc.scope_id else '-',
                proc.version, proc.get_status_display(),
                proc.assigned_to.name if proc.assigned_to_id else '',
            ])

        primaries = Primary.objects.select_related('scope', 'unit')
        primary_rows = [[
            p.name, p.serial_no, p.scope.name if p.scope_id else '-',
            p.unit.symbol if p.unit_id else '', p.model_no, p.manufacturer,
            (p.range_min or '') + ('–' + p.range_max if p.range_max else '') if (p.range_min or p.range_max) else '',
            p.last_calibrated, p.calibration_due_date, p.certificate_no, p.get_status_display(),
        ] for p in primaries.iterator()]

        wb = Workbook()
        header_font = Font(bold=True, color='FFFFFF', size=11)
        header_fill = PatternFill(start_color='2563EB', end_color='2563EB', fill_type='solid')
        thin_border = Border(left=Side('thin'), right=Side('thin'), top=Side('thin'), bottom=Side('thin'))
        header_align = Alignment(horizontal='center', vertical='center')

        def write_sheet(sheet, headers, rows, widths):
            ws = wb.active if sheet == wb.active.title else wb.create_sheet(title=sheet)
            ws.title = sheet
            for col, h in enumerate(headers, 1):
                c = ws.cell(row=1, column=col, value=h)
                c.font, c.fill, c.alignment, c.border = header_font, header_fill, header_align, thin_border
            for i, row in enumerate(rows, 2):
                for j, val in enumerate(row, 1):
                    ws.cell(row=i, column=j, value=val).border = thin_border
            for col, w in enumerate(widths, 1):
                ws.column_dimensions[chr(64 + col)].width = w

        write_sheet('Certificates',
                    ['Certificate No', 'Calibrated At', 'Equipment', 'Serial', 'Client', 'Scope(s)', 'Status', 'Result', 'U%'],
                    cert_rows, [22, 14, 28, 16, 24, 24, 16, 12, 10])
        write_sheet('Waybills',
                    ['Waybill No', 'Type', 'Client', 'Date', 'Uploaded File'],
                    wb_rows, [20, 12, 24, 14, 30])
        write_sheet('Env',
                    ['Doc No', 'Date', 'Time', 'Lab / Location', 'Temperature (°C)', 'Humidity (%)', 'Recorded By'],
                    env_rows, [22, 14, 12, 18, 18, 15, 22])
        write_sheet('Procedures',
                    ['Doc No', 'Title', 'Scope', 'Version', 'Status', 'Assigned To'],
                    proc_rows, [24, 42, 20, 10, 16, 20])
        write_sheet('Primaries',
                    ['Name', 'Serial No', 'Scope', 'Unit', 'Model', 'Manufacturer', 'Range', 'Last Cal', 'Cal Due', 'Cert No', 'Status'],
                    primary_rows, [28, 16, 20, 10, 14, 18, 16, 12, 12, 18, 18])

        rx = BytesIO()
        wb.save(rx)
        zf.writestr(f'{year}/registers.xlsx', rx.getvalue())

    response = HttpResponse(buf.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="EATL-Documents-{year}.zip"'
    return response


# ─── Calibration Logs ─────────────────────────────────────────────────────────


def _standards_context(scope_ids, unit_ids, range_str):
    """JSON feed of active reference standards + suggested presets for the
    cal-log create/edit page (used by JS chips, filtering and selection)."""
    from .matching import suggested_primaries
    from .models import Primary

    suggested = suggested_primaries(scope_ids, unit_ids, range_str, each=3)
    data = []
    for p in Primary.objects.filter(status='active',is_reference=True).select_related('unit', 'scope'):
        data.append({
            'id': p.pk, 'name': p.name, 'serial_no': p.serial_no or '',
            'certificate_no': p.certificate_no or '', 'scope_id': p.scope_id,
            'unit_id': p.unit_id, 'unit_symbol': p.unit.symbol if p.unit_id else '',
            'range_min': p.range_min or '', 'range_max': p.range_max or '',
        })
    return {
        'standards_json': json.dumps(data),
        'suggested_standard_ids': [str(s) for s in suggested],
        'suggested_standard_ids_json': json.dumps([str(s) for s in suggested]),
    }


def _pre_cal_scope_unit_ids(pre_cal):
    """(scope_ids, unit_ids, range_str) derived from a pre-cal log."""
    scopes = list(pre_cal.scopes.values_list('id', flat=True)) if pre_cal else []
    units = list(pre_cal.units.values_list('id', flat=True)) if pre_cal else []
    if pre_cal and not scopes and pre_cal.scope_id:
        scopes = [pre_cal.scope_id]
    if pre_cal and not units and pre_cal.unit_id:
        units = [pre_cal.unit_id]
    range_str = pre_cal.range_value if (pre_cal and pre_cal.range_value) else None
    return scopes, units, range_str


class CalibrationLogListView(LoginRequiredMixin, ListView):
    model = CalibrationLog
    template_name = 'core/calibration_logs/list.html'
    context_object_name = 'logs'
    paginate_by = 20

    def get_queryset(self):
        qs = CalibrationLog.objects.select_related(
            'waybill_item', 'scope', 'calibrated_by', 'reviewed_by', 'approved_by'
        ).prefetch_related('scopes')
        search = self.request.GET.get('search', '')
        status = self.request.GET.get('status', '')
        if search:
            qs = qs.filter(
                Q(equipment_desc__icontains=search) |
                Q(serial_no__icontains=search)
            )
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filters'] = {
            'search': self.request.GET.get('search', ''),
            'status': self.request.GET.get('status', ''),
        }
        context['status_choices'] = CalibrationLog.CALIBRATION_LOG_STATUS_CHOICES
        return context


def _parse_readings_payload(post):
    """Return (found_rows, left_rows) from the two hidden JSON fields.

    Falls back to the legacy single 'readings_json' field (treated as the
    As-Found set) for API/older clients that only send one payload.
    """
    found_raw = post.get('readings_found_json')
    left_raw = post.get('readings_left_json')
    if found_raw is None and left_raw is None:
        found_raw = post.get('readings_json', '[]')

    def _loads(raw):
        try:
            data = json.loads(raw or '[]')
        except (json.JSONDecodeError, TypeError):
            return []
        return data if isinstance(data, list) else []

    return _loads(found_raw), _loads(left_raw)


def _save_log_readings(log, post):
    """Create CalibrationLogReading rows from the as-found / as-left payloads.

    * As-Left rows inherit the log's default MPE when the row leaves it blank.
    * The per-row remark (Accepted / Rejected) is computed by the model save.
    * Afterwards the uncertainty budget and the majority-rule Pass/Fail are
      refreshed and persisted (mirrors what the web+API create/update paths do).
    """
    found_rows, left_rows = _parse_readings_payload(post)

    def _decimal(value):
        if value in (None, ''):
            return None
        try:
            return Decimal(value)
        except (TypeError, ValueError, InvalidOperation):
            return None

    def _error_of(row, inst, uut):
        err = _decimal(row.get('error'))
        if err is None and inst is not None and uut is not None:
            try:
                err = Decimal(inst) - Decimal(uut)
            except (TypeError, ValueError, InvalidOperation):
                err = None
        return err

    for row in found_rows:
        inst = row.get('instrument_reading')
        uut = row.get('uut_reading')
        if inst is None or uut is None:
            continue
        CalibrationLogReading.objects.create(
            calibration_log=log,
            reading_type='as_found',
            instrument_reading=inst,
            uut_reading=uut,
            unit_id=row.get('unit_id') or None,
            error=_error_of(row, inst, uut),
        )

    for row in left_rows:
        inst = row.get('instrument_reading')
        uut = row.get('uut_reading')
        if inst is None or uut is None:
            continue
        CalibrationLogReading.objects.create(
            calibration_log=log,
            reading_type='as_left',
            instrument_reading=inst,
            uut_reading=uut,
            unit_id=row.get('unit_id') or None,
            error=_error_of(row, inst, uut),
            maximum_permissible_error=_decimal(row.get('maximum_permissible_error')),
        )

    log.compute_uncertainty()
    log.derive_pass_fail_from_remarks()
    CalibrationLog.objects.filter(pk=log.pk).update(
        expanded_uncertainty=log.expanded_uncertainty,
        uncertainty_in_tolerance=log.uncertainty_in_tolerance,
        pass_fail=log.pass_fail,
    )


class CalibrationLogCreateView(LoginRequiredMixin, CreateView):
    model = CalibrationLog
    form_class = CalibrationLogForm
    template_name = 'core/calibration_logs/create.html'
    success_url = reverse_lazy('calibration_log_list')

    def get(self, request, *args, **kwargs):
        waybill_item_id = self.kwargs.get('waybill_item_id')
        item = get_object_or_404(WaybillItem, pk=waybill_item_id)
        if not item.pre_calibration_logs.exists():
            messages.warning(request, 'Pre-calibration must be completed before creating a calibration log.')
            return redirect('pre_calibration_create', waybill_item_id=waybill_item_id)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['calibration_types'] = CalibrationType.objects.all()
        context['readings_found_json'] = '[]'
        context['readings_left_json'] = '[]'
        pre_cal = None
        waybill_item_id = self.kwargs.get('waybill_item_id')
        if waybill_item_id:
            item = get_object_or_404(WaybillItem, pk=waybill_item_id)
            pre_cal = item.pre_calibration_logs.first()
        if pre_cal and pre_cal.units.exists():
            context['initial_unit_id'] = pre_cal.units.first().pk
        else:
            context['initial_unit_id'] = pre_cal.unit_id if (pre_cal and pre_cal.unit_id) else ''
        # Selected scopes (checkbox state) + reference-standard feed/suggestions
        form_ctx = self.get_form()
        scope_ids = list(pre_cal.scopes.values_list('id', flat=True)) if pre_cal else []
        if pre_cal and not scope_ids and pre_cal.scope_id:
            scope_ids = [pre_cal.scope_id]
        context['selected_scopes'] = {str(pk) for pk in scope_ids}
        context['initial_scope_ids'] = {str(pk) for pk in scope_ids}
        sc_ids, unit_ids, range_str = _pre_cal_scope_unit_ids(pre_cal)
        if not sc_ids and item and item.scope_id:
            sc_ids = [item.scope_id]
        context.update(_standards_context(sc_ids, unit_ids, range_str))
        return context

    def get_initial(self):
        initial = super().get_initial()
        initial['calibrated_at_date'] = date.today()
        # Auto-set calibrated_by from logged-in user
        try:
            person = self.request.user.personnel_profile
            initial['calibrated_by'] = person
        except (Personnel.DoesNotExist, AttributeError):
            pass
        waybill_item_id = self.kwargs.get('waybill_item_id')
        if waybill_item_id:
            item = get_object_or_404(WaybillItem, pk=waybill_item_id)
            pre_cal = item.pre_calibration_logs.first()
            if pre_cal:
                initial['physical_condition'] = pre_cal.get_physical_condition_display()
                initial['environmental_condition'] = pre_cal.environmental_condition
                initial['calibrated_at_location'] = pre_cal.location
                sc_ids, unit_ids, range_str = _pre_cal_scope_unit_ids(pre_cal)
                initial['scopes'] = sc_ids or ([pre_cal.scope_id] if pre_cal.scope_id else [])
                if sc_ids:
                    from .matching import suggested_primaries
                    initial['standards'] = [
                        p.pk for p in suggested_primaries(sc_ids, unit_ids, range_str, each=3)
                    ]
            elif item.scope_id:
                initial['scopes'] = [item.scope_id]
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        waybill_item_id = self.kwargs.get('waybill_item_id')
        if waybill_item_id:
            item = get_object_or_404(WaybillItem, pk=waybill_item_id)
            kwargs['waybill_item'] = item
            job = Job.objects.filter(incoming_waybill=item.waybill).first()
            if job:
                kwargs['job'] = job
        return kwargs

    def form_valid(self, form):
        waybill_item = get_object_or_404(WaybillItem, pk=self.kwargs['waybill_item_id'])
        form.instance.waybill_item = waybill_item
        from .personnel_records import validate_analyst
        analyst=form.cleaned_data.get('calibrated_by') or Personnel.objects.filter(user=self.request.user).first()
        scopes=list(form.cleaned_data.get('scopes') or [])
        if not scopes and form.instance.scope_id: scopes=[form.instance.scope]
        validate_analyst(analyst,scopes)
        form.instance.calibrated_by=analyst
        form.instance.recorded_by = self.request.user
        form.instance.status = 'pending_review'
        # Mirror the first selected scope onto the legacy single FK
        if not form.instance.scope_id and self.request.POST.getlist('scopes'):
            first_scope = CalibrationType.objects.filter(
                pk__in=[v for v in self.request.POST.getlist('scopes') if v.isdigit()]
            ).order_by('pk').first()
            form.instance.scope = first_scope
        # Snapshot the scope's active procedure (if any) at creation time
        if not form.instance.procedure_id and form.instance.scope_id:
            form.instance.procedure = CalibrationProcedure.objects.filter(
                scope_id=form.instance.scope_id, status='active'
            ).first()

        # Update WaybillItem status
        waybill_item.status = 'result_pending'
        waybill_item.save()

        # Update Job status to track equipment progression
        job = Job.objects.filter(incoming_waybill=waybill_item.waybill).first()
        if job:
            job.reconcile_status()

        response = super().form_valid(form)
        # Sync the M2M selection onto the legacy single FK
        if not form.instance.scope_id and form.instance.scopes.first():
            form.instance.scope = form.instance.scopes.first()
            form.instance.save(update_fields=['scope'])
        self._save_readings()
        self._save_specs()

        reviewer = form.cleaned_data.get('reviewer')
        if reviewer:
            notify_users(
                [reviewer],
                f'New calibration log assigned for your review — {waybill_item.equipment_description} (SN: {waybill_item.serial_no})',
                reverse('calibration_log_detail', args=[self.object.pk]),
                'pending_review',
            )
        else:
            notify_users(
                get_users_with_perm('review_calibration'),
                f'New calibration log pending review — {waybill_item.equipment_description} (SN: {waybill_item.serial_no})',
                reverse('calibration_log_detail', args=[self.object.pk]),
                'pending_review',
            )
        messages.success(self.request, 'Calibration log created successfully.')
        return response

    def _save_readings(self):
        _save_log_readings(self.object, self.request.POST)

    def _save_specs(self):
        try:
            data = json.loads(self.request.POST.get('specs_json', '[]'))
        except (json.JSONDecodeError, TypeError):
            return
        if not isinstance(data, list):
            return
        for row in data:
            name = (row.get('spec_name') or '').strip()
            value = (row.get('spec_value') or '').strip()
            if name:
                CalibrationLogSpec.objects.create(
                    log=self.object, spec_name=name[:100], spec_value=value[:100])


class CalibrationLogDetailView(LoginRequiredMixin, DetailView):
    model = CalibrationLog
    template_name = 'core/calibration_logs/detail.html'
    context_object_name = 'log'

    def get_queryset(self):
        return CalibrationLog.objects.prefetch_related(
            'readings__unit', 'scope', 'standards'
        ).select_related(
            'calibrated_by', 'calibrated_at_location', 'environmental_condition',
            'equipment_owner', 'reviewer', 'recorded_by'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        log = self.object
        temp = None
        humidity = None
        if log.use_manual_env:
            temp = log.manual_temperature
            humidity = log.manual_humidity
        elif log.environmental_condition:
            temp = log.environmental_condition.temperature
            humidity = log.environmental_condition.relative_humidity
        conformity = None
        primary = log.primary
        if primary:
            conformity = primary.environment_conforms(temp, humidity)
        context['conformity'] = conformity
        context['conformity_temp'] = temp
        context['conformity_humidity'] = humidity
        context['is_assigned_reviewer'] = (
            bool(log.reviewer_id) and log.reviewer_id == self.request.user.pk
        )
        context['can_review'] = (
            has_perm(self.request.user,'review_calibration')
            and (lab_authority(self.request.user) or not log.reviewer_id or log.reviewer_id==self.request.user.pk)
            and log.recorded_by_id != self.request.user.pk
            and (not log.calibrated_by_id or log.calibrated_by.user_id != self.request.user.pk)
        )
        from .personnel_records import authorized_log
        context['can_review']=context['can_review'] and authorized_log(self.request.user,log,'review')
        context['can_approve']=lab_authority(self.request.user) and authorized_log(self.request.user,log,'approve') and log.recorded_by_id!=self.request.user.pk and (not log.calibrated_by_id or log.calibrated_by.user_id!=self.request.user.pk)
        found = log.readings.filter(reading_type='as_found').select_related('unit')
        left = log.readings.filter(reading_type='as_left').select_related('unit')
        judged = left.exclude(maximum_permissible_error__isnull=True)
        context['readings_found'] = found
        context['readings_left'] = left
        context['remarks_accepted'] = judged.filter(remark='Accepted').count()
        context['remarks_total'] = judged.count()
        context['remarks_majority_pass'] = context['remarks_accepted'] * 2 > context['remarks_total']
        return context


class CalibrationLogUpdateView(LoginRequiredMixin, UpdateView):
    model = CalibrationLog
    form_class = CalibrationLogForm
    template_name = 'core/calibration_logs/create.html'
    success_url = reverse_lazy('calibration_log_list')

    def dispatch(self, request, *args, **kwargs):
        log = get_object_or_404(CalibrationLog, pk=kwargs.get('pk'))
        if log.status not in ('pending_review','rejected'):
            messages.error(request, 'Reviewed or approved calibration logs are locked. Return for rework or use a controlled revision.')
            return redirect('calibration_log_detail', pk=log.pk)
        if not has_perm(request.user, 'edit_calibration'):
            messages.error(request, 'You do not have permission to edit calibration logs.')
            return redirect('calibration_log_list')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['calibration_types'] = CalibrationType.objects.all()
        found_list, left_list = [], []
        readings = self.object.readings.all().values(
            'reading_type', 'instrument_reading', 'uut_reading', 'unit_id', 'error', 'maximum_permissible_error'
        )
        for r in readings:
            item = {
                'instrument_reading': float(r['instrument_reading']) if r['instrument_reading'] is not None else None,
                'uut_reading': float(r['uut_reading']) if r['uut_reading'] is not None else None,
                'unit_id': r['unit_id'],
                'error': float(r['error']) if r['error'] is not None else None,
            }
            if r['reading_type'] == 'as_left':
                item['maximum_permissible_error'] = (
                    float(r['maximum_permissible_error']) if r['maximum_permissible_error'] is not None else None
                )
                left_list.append(item)
            else:
                found_list.append(item)
        context['readings_found_json'] = json.dumps(found_list)
        context['readings_left_json'] = json.dumps(left_list)
        scope_ids = list(self.object.scopes.values_list('id', flat=True)) or (
            [self.object.scope_id] if self.object.scope_id else [])
        context['selected_scopes'] = {str(pk) for pk in scope_ids}
        context['initial_scope_ids'] = {str(pk) for pk in scope_ids}
        unit_ids = [r['unit_id'] for r in found_list + left_list if r['unit_id']]
        context.update(_standards_context(scope_ids, unit_ids, self.object.range_value))
        first_unit = next((r['unit_id'] for r in found_list + left_list if r['unit_id']), None)
        context['initial_unit_id'] = first_unit or ''
        return context

    def form_valid(self, form):
        from .personnel_records import validate_analyst
        scopes=list(form.cleaned_data.get('scopes') or [])
        if not scopes and form.instance.scope_id: scopes=[form.instance.scope]
        validate_analyst(form.cleaned_data.get('calibrated_by') or form.instance.calibrated_by,scopes)
        response = super().form_valid(form)
        self.object.readings.all().delete()
        self._save_readings()
        self.object.specs.all().delete()
        self._save_specs()
        # Sync the M2M selection onto the legacy single FK
        if self.object.scopes.first():
            self.object.scope = self.object.scopes.first()
        # Snapshot the active procedure for the chosen scope (if not already set)
        if not self.object.procedure_id and self.object.scope_id:
            proc = CalibrationProcedure.objects.filter(
                scope_id=self.object.scope_id, status='active').first()
            if proc:
                self.object.procedure = proc
        reviewer = form.cleaned_data.get('reviewer')
        if reviewer is not None or 'reviewer' in form.fields:
            self.object.reviewer = reviewer or None
        was_rejected=self.object.status=='rejected'
        if was_rejected:
            self.object.status='pending_review'; self.object.reviewed_by=None;self.object.reviewed_at=None
            self.object.reviewer_signature='';self.object.approved_by=None;self.object.approved_at=None
            self.object.rejection_reason=''
        self.object.save(update_fields=['procedure','reviewer','scope','status','reviewed_by','reviewed_at','reviewer_signature','approved_by','approved_at','rejection_reason'])
        if was_rejected:
            notify_users([self.object.reviewer] if self.object.reviewer_id else get_users_with_perm('review_calibration'),
                f'Reworked calibration log {self.object.pk} requires Supervisor review.',reverse('calibration_log_detail',args=[self.object.pk]),'pending_review')
        return response

    def _save_specs(self):
        try:
            data = json.loads(self.request.POST.get('specs_json', '[]'))
        except (json.JSONDecodeError, TypeError):
            return
        if not isinstance(data, list):
            return
        for row in data:
            name = (row.get('spec_name') or '').strip()
            value = (row.get('spec_value') or '').strip()
            if name:
                CalibrationLogSpec.objects.create(
                    log=self.object, spec_name=name[:100], spec_value=value[:100])

    def _save_readings(self):
        _save_log_readings(self.object, self.request.POST)


# ─── Calibration Log Review/Approve/Reject ──────────────────────────────────


@login_required
def calibration_log_review(request, pk):
    log = get_object_or_404(CalibrationLog, pk=pk)
    from .personnel_records import authorized_log
    if not authorized_log(request.user,log,'review') or log.recorded_by_id == request.user.pk or (log.calibrated_by_id and log.calibrated_by.user_id == request.user.pk):
        raise PermissionDenied('Current scope-specific review authorization and an independent reviewer are required.')
    if not has_perm(request.user, 'review_calibration'):
        messages.error(request, 'Only Lab Leads and Managers can review calibration logs.')
        return redirect('calibration_log_detail', pk=pk)

    # The technician selects the reviewer; honour that selection.
    if log.reviewer_id and log.reviewer_id != request.user.pk and not lab_authority(request.user):
        messages.error(request, f'This log was assigned to {log.reviewer.get_full_name() or log.reviewer.username} for review.')
        return redirect('calibration_log_detail', pk=pk)

    if log.status != 'pending_review':
        messages.warning(request, 'This log is not pending review.')
        return redirect('calibration_log_detail', pk=pk)

    if request.method == 'POST':
        # Review is the signing moment: stamp the reviewer's profile signature
        signature = get_user_signature_url(request.user)
        if not signature:
            messages.error(request, 'No signature on your profile. Upload one via Profile → Edit before reviewing.')
            return redirect('profile_edit')

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
        messages.success(request, 'Calibration log reviewed. Upload the signed result to send it for QHSE approval.')
        return redirect('calibration_log_detail', pk=pk)

    return render(request, 'core/calibration_logs/review_confirm.html', {
        'log': log,
        'my_signature': get_user_signature_url(request.user),
        'readings_found': log.readings.filter(reading_type='as_found').select_related('unit'),
        'readings_left': log.readings.filter(reading_type='as_left').select_related('unit'),
    })


@login_required
def calibration_log_approve(request, pk):
    log = get_object_or_404(CalibrationLog, pk=pk)
    from .personnel_records import authorized_log
    if not authorized_log(request.user,log,'approve') or log.recorded_by_id == request.user.pk or (log.calibrated_by_id and log.calibrated_by.user_id == request.user.pk):
        raise PermissionDenied('Current scope-specific approval authorization and an independent approver are required.')
    if not has_perm(request.user, 'approve_calibration'):
        messages.error(request, 'Only Managers can approve calibration logs.')
        return redirect('calibration_log_detail', pk=pk)

    if log.status not in ('pending_qhse', 'pending_approval'):
        messages.warning(request, 'This log is not pending QHSE approval.')
        return redirect('calibration_log_detail', pk=pk)

    if request.method == 'POST':
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

        waybill_item = log.waybill_item

        # Only advance to completed if certificate already uploaded
        if log.certificate:
            waybill_item.status = 'completed'
            waybill_item.save()
            messages.success(request, 'Calibration log approved. Equipment marked as completed.')
        else:
            messages.success(request, 'Calibration log approved. Personnel must upload the signed result before equipment can be completed.')

        job = Job.objects.filter(incoming_waybill=waybill_item.waybill).first()
        if job:
            job.reconcile_status()

        return redirect('calibration_log_detail', pk=pk)

    return render(request, 'core/calibration_logs/approve_confirm.html', {
        'log': log,
        'readings_found': log.readings.filter(reading_type='as_found').select_related('unit'),
        'readings_left': log.readings.filter(reading_type='as_left').select_related('unit'),
    })


def _certificate_context(log):
    """Shared context for the certificate pages + the yearly documents export.

    Builds the exact context contract both the default certificate.html and the
    per-scope custom certificate templates consume (see calibration_certificate).
    Assigns the certificate number if this is the first view/export of the log.
    """
    if not log.certificate_no:
        log.assign_certificate_no()

    company = CompanyProfile.objects.first()
    temp = None
    humidity = None
    if log.use_manual_env:
        temp = log.manual_temperature
        humidity = log.manual_humidity
    elif log.environmental_condition:
        temp = log.environmental_condition.temperature
        humidity = log.environmental_condition.relative_humidity
    conformity = None
    primary = log.primary
    if primary:
        conformity = primary.environment_conforms(temp, humidity)

    # Narrative paragraph resolved from Settings placeholders (never free text on the log)
    standards = list(log.standards.all())
    first_standard = standards[0] if standards else None
    default_narrative = (
        'The calibration of {uuc_description} was carried out in accordance with '
        '{procedure_manual} using the reference standard {standard_used} (certificate no. '
        '{standard_cert_no}), traceable to {traceability_body}. The calibration complies with '
        '{compliance_standard}. Results were processed with {software}.'
    )
    template = (company.narrative_template if company and company.narrative_template
                else default_narrative)
    narrative_ctx = {
        'uuc_description': log.equipment_desc or '-',
        'standard_used': first_standard.name if first_standard else '-',
        'standard_cert_no': first_standard.certificate_no if first_standard else '-',
        'traceability_body': getattr(company, 'traceability_body', '') or '-',
        'compliance_standard': getattr(company, 'compliance_standard', '') or '-',
        'software': getattr(company, 'software', '') or '-',
        'procedure_manual': log.procedure.manual_reference if log.procedure_id else '-',
    }
    narrative = template
    for key, val in narrative_ctx.items():
        narrative = narrative.replace('{' + key + '}', str(val))

    date_received = None
    wb_item = log.waybill_item
    if wb_item is not None:
        date_received = wb_item.waybill.created_at.date() if wb_item.waybill else None

    # Reporting unit: determined during pre-calibration (falls back to the first
    # reading's unit, then any scope unit). Never hardcoded per certificate type.
    reporting_unit = ''
    readings_qs = log.readings.select_related('unit')
    first_reading = readings_qs.first()
    if first_reading and first_reading.unit_id:
        reporting_unit = first_reading.unit.symbol
    if not reporting_unit and wb_item is not None:
        pre_cal = wb_item.pre_calibration_logs.select_related('unit').first()
        if pre_cal and pre_cal.unit_id:
            reporting_unit = pre_cal.unit.symbol
    if not reporting_unit and log.scope_id:
        scope_unit = log.scope.units.first()
        if scope_unit:
            reporting_unit = scope_unit.symbol

    readings_qs = log.readings.select_related('unit')
    readings_found = readings_qs.filter(reading_type='as_found')
    readings_left = readings_qs.filter(reading_type='as_left')
    left_judged = readings_left.exclude(maximum_permissible_error__isnull=True)
    remarks_accepted = left_judged.filter(remark='Accepted').count()
    remarks_total = left_judged.count()

    return {
        'log': log,
        'company': company,
        'addresses': company.addresses.all() if company else [],
        'readings': readings_qs,
        'readings_found': readings_found,
        'readings_left': readings_left,
        'remarks_accepted': remarks_accepted,
        'remarks_total': remarks_total,
        'remarks_majority_pass': remarks_accepted * 2 > remarks_total,
        'conformity': conformity,
        'standards': standards,
        'specs': log.specs.all(),
        'narrative': narrative,
        'date_received': date_received,
        'previous_log': log.previous_certificate_log,
        'total_pages': 2,
        'reporting_unit': reporting_unit,
        'budget': log.scope.uncertainty_budgets.filter(active=True).first() if log.scope_id else None,
    }


def calibration_certificate(request, pk):
    log = get_object_or_404(
        CalibrationLog.objects.select_related(
            'waybill_item', 'scope', 'equipment_owner',
            'environmental_condition', 'calibrated_by', 'reviewed_by', 'approved_by'
        ).prefetch_related('standards', 'specs'),
        pk=pk,
    )
    if log.status not in ('pending_approval', 'pending_qhse', 'approved'):
        messages.warning(request, 'Certificate is available once the calibration log has passed review.')
        return redirect('calibration_log_detail', pk=pk)

    context = _certificate_context(log)

    # Per-scope custom certificate layout (Settings → Scopes). The template is
    # admin-authored and compiled with the project engine, so it receives the
    # exact same context as the default certificate.html.
    scope_tpl = log.scope.certificate_template if log.scope_id else ''
    if scope_tpl and scope_tpl.strip():
        from django.template import engines
        tpl = engines['django'].from_string(scope_tpl)
        return HttpResponse(tpl.render(context, request))

    return render(request, 'core/calibration_logs/certificate.html', context)


@login_required
def calibration_log_reject(request, pk):
    log = get_object_or_404(CalibrationLog, pk=pk)
    if not has_perm(request.user, 'reject_calibration'):
        messages.error(request, 'Only Lab Leads and Managers can reject calibration logs.')
        return redirect('calibration_log_detail', pk=pk)

    if log.status not in ['pending_review', 'pending_approval', 'pending_qhse']:
        messages.warning(request, 'This log cannot be rejected at its current status.')
        return redirect('calibration_log_detail', pk=pk)

    if request.method == 'POST':
        reason = request.POST.get('rejection_reason', '').strip()
        if not reason:
            messages.error(request, 'Please provide a reason for rejection.')
            return redirect('calibration_log_detail', pk=pk)

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
        messages.success(request, 'Calibration log rejected.')
        return redirect('calibration_log_detail', pk=pk)

    return render(request, 'core/calibration_logs/reject.html', {'log': log})


@login_required
def calibration_log_reissue_cert(request, pk):
    """Re-generate this log's certificate number from the CURRENT numbering
    settings (Settings → Scopes / Company), keeping its sequence slot."""
    if request.method != 'POST':
        messages.error(request, 'Invalid request.')
        return redirect('calibration_log_detail', pk=pk)

    log = get_object_or_404(CalibrationLog.objects.select_related('scope', 'equipment_owner'), pk=pk)
    if not has_perm(request.user, 'approve_calibration'):
        messages.error(request, 'Only Lab Leads and Managers can re-issue certificate numbers.')
        return redirect('calibration_log_detail', pk=pk)

    if log.status not in ('pending_approval', 'pending_qhse', 'approved'):
        messages.warning(request, 'Certificate number can be issued once the log has passed review.')
        return redirect('calibration_log_detail', pk=pk)

    old_no = log.certificate_no or '(not issued)'
    changed = log.reissue_certificate_no()
    new_no = log.certificate_no
    if changed:
        messages.success(request, f'Certificate number updated: {old_no} → {new_no}')
    else:
        messages.info(request, f'Certificate number is already up to date ({new_no}).')
    return redirect('calibration_log_detail', pk=pk)


@login_required
def calibration_log_upload_certificate(request, pk):
    """Upload/replace the signed calibration result directly from the log's
    detail page (no full-form edit needed)."""
    if request.method != 'POST':
        messages.error(request, 'Invalid request.')
        return redirect('calibration_log_detail', pk=pk)

    log = get_object_or_404(CalibrationLog, pk=pk)
    if log.status=='approved' and log.certificate:
        messages.error(request,'An approved signed result is locked. Issue a controlled amendment instead of replacing it.')
        return redirect('calibration_log_detail',pk=pk)
    if not has_perm(request.user, 'edit_calibration'):
        messages.error(request, 'You do not have permission to upload calibration results.')
        return redirect('calibration_log_detail', pk=pk)

    upload = request.FILES.get('certificate')
    if not upload:
        messages.error(request, 'Please choose a file to upload.')
        return redirect('calibration_log_detail', pk=pk)

    log.certificate = upload
    log.save(update_fields=['certificate'])

    # After review, uploading the signed result pushes the log to QHSE approval.
    if log.status == 'pending_approval':
        log.status = 'pending_qhse'
        log.save(update_fields=['status'])
        notify_users(
            get_users_with_perm('approve_calibration'),
            f'Signed result uploaded — calibration log pending QHSE approval: {log.equipment_desc} (SN: {log.serial_no})',
            reverse('calibration_log_detail', args=[pk]),
            'pending_qhse',
        )
        messages.success(request, 'Signed calibration result uploaded. The log is now pending QHSE approval.')
        return redirect('calibration_log_detail', pk=pk)

    # Approved logs: uploading the signed result completes the equipment item
    # and advances the job (mirrors the old CalibrationLogUpdateView behavior).
    if log.status == 'approved' and log.waybill_item:
        waybill_item = log.waybill_item
        if waybill_item.status != 'completed':
            waybill_item.status = 'completed'
            waybill_item.save()

            job = Job.objects.filter(incoming_waybill=waybill_item.waybill).first()
            if job:
                job.reconcile_status()

    messages.success(request, 'Signed calibration result uploaded successfully.')
    return redirect('calibration_log_detail', pk=pk)


# ─── Pre-Calibration Logs ────────────────────────────────────────────────────


class PreCalibrationLogListView(LoginRequiredMixin, ListView):
    model = PreCalibrationLog
    template_name = 'core/pre_calibration/list.html'
    context_object_name = 'pre_logs'
    paginate_by = 20

    def get_queryset(self):
        qs = PreCalibrationLog.objects.select_related(
            'waybill_item', 'inspected_by', 'unit', 'scope'
        ).prefetch_related('scopes', 'units')
        search = self.request.GET.get('search', '')
        if search:
            qs = qs.filter(
                Q(waybill_item__equipment_description__icontains=search) |
                Q(waybill_item__serial_no__icontains=search) |
                Q(inspected_by__username__icontains=search)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filters'] = {
            'search': self.request.GET.get('search', ''),
        }
        # Items awaiting a pre-calibration action (status pre_cal_pending):
        # either never had a pre-cal log, or have one marked not-ready awaiting review.
        pending_qs = WaybillItem.objects.filter(status='pre_cal_pending')
        pending = []
        for item in pending_qs.select_related('waybill'):
            pre_log = item.pre_calibration_logs.first()
            pending.append({
                'item': item,
                'has_log': pre_log is not None,
                'awaiting_review': bool(pre_log and not pre_log.ready_for_calibration and not pre_log.review_decision),
            })
        context['pending_items'] = pending
        context['can_perform_pre_cal'] = has_perm(self.request.user, 'perform_pre_calibration')
        context['can_review_pre_cal'] = has_perm(self.request.user, 'review_pre_calibration')
        return context


class PreCalibrationLogCreateView(LoginRequiredMixin, CreateView):
    model = PreCalibrationLog
    form_class = PreCalibrationForm
    template_name = 'core/pre_calibration/create.html'
    success_url = reverse_lazy('pre_calibration_list')

    def dispatch(self, request, *args, **kwargs):
        if not has_perm(request.user, 'perform_pre_calibration'):
            messages.error(request, 'You do not have permission to perform pre-calibration.')
            return redirect('pre_calibration_list')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        waybill_item_id = self.kwargs.get('waybill_item_id')
        context['waybill_item'] = get_object_or_404(WaybillItem, pk=waybill_item_id)

        # Currently selected scope/unit pks (strings, for template checked-state).
        # Unit availability/range info is fetched client-side from units_by_scope,
        # which lazy-seeds the Unit catalog and computes `available`/`range_ok`.
        form = self.get_form()
        context['selected_scopes'] = {str(pk) for pk in (form['scopes'].value() or [])}
        context['selected_units'] = {str(pk) for pk in (form['units'].value() or [])}
        context['selected_units_json'] = json.dumps(
            [str(pk) for pk in (form['units'].value() or [])])
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        waybill_item_id = self.kwargs.get('waybill_item_id')
        if waybill_item_id:
            kwargs['waybill_item'] = get_object_or_404(WaybillItem, pk=waybill_item_id)
        return kwargs

    def form_valid(self, form):
        waybill_item = get_object_or_404(WaybillItem, pk=self.kwargs['waybill_item_id'])
        form.instance.waybill_item = waybill_item
        form.instance.inspected_by = self.request.user
        response = super().form_valid(form)

        # Mirror the first of the selected scopes/units onto the legacy single FKs,
        # then assign the accreditation document number (PRE-{year}-{seq:04d}).
        form.instance.scope = form.instance.scopes.first()
        form.instance.unit = form.instance.units.first()
        form.instance.save(update_fields=['scope', 'unit'])
        form.instance.assign_doc_no()

        # Mirror the primary scope decided during inspection onto the equipment item
        if form.instance.scope_id:
            waybill_item.scope = form.instance.scope
            waybill_item.save(update_fields=['scope'])

        ready = form.instance.ready_for_calibration

        if ready:
            waybill_item.status = 'cal_pending'
        else:
            waybill_item.status = 'pre_cal_pending'
        waybill_item.save()

        # Append remarks to Job and advance job status with equipment progression
        job = Job.objects.filter(incoming_waybill=waybill_item.waybill).first()
        if job:
            remarks = form.instance.remarks.strip()
            if remarks:
                entry = f"\n[{waybill_item.serial_no}] {remarks}"
                existing = job.remarks or ''
                job.remarks = (existing + entry).strip() if existing else entry.strip()
                job.save(update_fields=['remarks'])
            job.reconcile_status()

        if ready:
            messages.success(self.request, 'Pre-calibration completed successfully.')
        else:
            messages.warning(self.request, 'Equipment marked as not ready. A Lab Lead or Manager must review.')
        return response


class PreCalibrationLogDetailView(LoginRequiredMixin, DetailView):
    model = PreCalibrationLog
    template_name = 'core/pre_calibration/detail.html'
    context_object_name = 'pre_log'

    def get_queryset(self):
        return PreCalibrationLog.objects.select_related(
            'waybill_item', 'unit', 'location', 'inspected_by', 'reviewed_by'
        ).prefetch_related('scopes', 'units')


# ─── Pre-Cal Review (Lab Lead / Manager) ────────────────────────────────────


@login_required
def pre_cal_review(request, pk):
    pre_log = get_object_or_404(PreCalibrationLog, pk=pk)

    if not has_perm(request.user, 'review_pre_calibration'):
        messages.error(request, 'Only Lab Leads and Managers can review pre-calibration logs.')
        return redirect('pre_calibration_detail', pk=pk)

    if pre_log.ready_for_calibration:
        messages.info(request, 'This equipment is already marked as ready for calibration.')
        return redirect('pre_calibration_detail', pk=pk)

    if pre_log.review_decision:
        messages.info(request, 'This pre-calibration log has already been reviewed.')
        return redirect('pre_calibration_detail', pk=pk)

    if request.method == 'POST':
        form = PreCalReviewForm(request.POST, request.FILES)
        if form.is_valid():
            decision = form.cleaned_data['decision']
            review_notes = form.cleaned_data['review_notes']
            waybill_no = form.cleaned_data.get('waybill_no', '')

            pre_log.review_decision = decision
            pre_log.reviewed_by = request.user
            pre_log.reviewed_at = timezone.now()
            pre_log.repair_notes = review_notes

            waybill_item = pre_log.waybill_item

            if decision == 'dispatch':
                # No outgoing waybill may be created without an established PO for the job
                dispatch_job = Job.objects.filter(incoming_waybill=waybill_item.waybill).first()
                if not dispatch_job or not (dispatch_job.purchase_order_number or '').strip():
                    messages.error(
                        request,
                        'Cannot dispatch: no Purchase Order is established for this job. '
                        'Add a PO number to the job first, then review again.'
                    )
                    return redirect('pre_calibration_detail', pk=pk)

            if decision == 'repair':
                waybill_item.status = 'repair_due'
                waybill_item.save()

                job = Job.objects.filter(incoming_waybill=waybill_item.waybill).first()
                if job:
                    job.reconcile_status()

                # Notify managers
                managers = get_users_with_perm('approve_calibration')
                for mgr in managers:
                    Notification.objects.create(
                        message=f'Equipment "{waybill_item.equipment_description}" ({waybill_item.serial_no}) on Job #{job.pk if job else "?"} has been approved for repair.',
                        recipient=mgr,
                        link=reverse('pre_calibration_detail', kwargs={'pk': pk}),
                        notification_type='repair_approved',
                    )

                messages.success(request, 'Repair approved. Equipment status set to Repair Due.')

            elif decision == 'dispatch':
                waybill_no = form.cleaned_data['waybill_no']
                waybill_file = request.FILES.get('waybill_file')

                job = Job.objects.filter(incoming_waybill=waybill_item.waybill).first()

                # Create outgoing waybill
                outgoing = Waybill.objects.create(
                    waybill_no=waybill_no,
                    waybill_type='outgoing',
                    file_upload=waybill_file,
                    linked_incoming_waybill=waybill_item.waybill,
                    job=job,
                )
                # Link the outgoing waybill to the pre-cal log
                pre_log.outgoing_waybill = outgoing

                # Create a copy of the waybill item in the outgoing waybill
                WaybillItem.objects.create(
                    waybill=outgoing,
                    equipment_description=waybill_item.equipment_description,
                    quantity=waybill_item.quantity,
                    serial_no=waybill_item.serial_no,
                    model_no=waybill_item.model_no or '',
                    manufacturer=waybill_item.manufacturer or '',
                    range_field=waybill_item.range_field or '',
                    scope=waybill_item.scope,
                    status='dispatched',
                )

                waybill_item.status = 'dispatched'
                waybill_item.save()

                # Update job status to track equipment progression
                job = Job.objects.filter(incoming_waybill=waybill_item.waybill).first()
                if job:
                    job.reconcile_status()

                # Notify managers
                managers = get_users_with_perm('approve_calibration')
                for mgr in managers:
                    Notification.objects.create(
                        message=f'Equipment "{waybill_item.equipment_description}" ({waybill_item.serial_no}) on Job #{job.pk if job else "?"} has been approved for dispatch (cannot be repaired in-house).',
                        recipient=mgr,
                        link=reverse('pre_calibration_detail', kwargs={'pk': pk}),
                        notification_type='dispatch_approved',
                    )

                messages.success(request, 'Dispatch approved. Outgoing waybill created and equipment dispatched.')

            pre_log.save()
            return redirect('pre_calibration_detail', pk=pk)
    else:
        form = PreCalReviewForm()

    return render(request, 'core/pre_calibration/review.html', {
        'form': form,
        'pre_log': pre_log,
    })


# ─── Repair Complete ─────────────────────────────────────────────────────────


@login_required
def repair_complete(request, pk):
    waybill_item = get_object_or_404(WaybillItem, pk=pk)

    if not has_perm(request.user, 'repair_equipment'):
        messages.error(request, 'Only Lab Leads and Managers can mark equipment as repaired.')
        return redirect('job_list')

    if waybill_item.status != 'repair_due':
        messages.warning(request, 'This equipment is not in Repair Due status.')
        return redirect('job_list')

    if request.method == 'POST':
        waybill_item.status = 'cal_pending'
        waybill_item.save()

        # Update job status to track equipment progression
        job = Job.objects.filter(incoming_waybill=waybill_item.waybill).first()
        if job:
            job.reconcile_status()

        # Notify managers
        managers = get_users_with_perm('approve_calibration')
        for mgr in managers:
            Notification.objects.create(
                message=f'Equipment "{waybill_item.equipment_description}" ({waybill_item.serial_no}) has been repaired by {request.user.get_full_name() or request.user.username}. Ready for calibration.',
                recipient=mgr,
                link=reverse('job_detail', kwargs={'pk': job.pk}) if job else '',
                notification_type='repair_complete',
            )

        messages.success(request, f'Equipment "{waybill_item.equipment_description}" marked as repaired and ready for calibration.')
        return redirect('job_detail', pk=job.pk) if job else redirect('job_list')

    return render(request, 'core/pre_calibration/repair_complete.html', {
        'item': waybill_item,
    })


# ─── Notifications ────────────────────────────────────────────────────────────


@login_required
def notification_list(request):
    notifications = Notification.objects.filter(recipient=request.user)
    search = request.GET.get('search', '')
    if search:
        notifications = notifications.filter(message__icontains=search)
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'core/notifications/list.html', {
        'notifications': page_obj,
        'filters': {'search': search},
    })


@login_required
def notification_mark_all_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    messages.success(request, 'All notifications marked as read.')
    return redirect('notification_list')


@login_required
def notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.is_read = True
    notification.save()
    if notification.link:
        return redirect(notification.link)
    return redirect('notification_list')


@login_required
def notification_popups(request):
    """Polled by base.html to surface "environment recorded" notifications as
    in-app pop-up toasts. Returns only unread notifications with id > ?after=,
    so the client can track what it has already shown via localStorage."""
    after = 0
    try:
        after = int(request.GET.get('after', 0))
    except (TypeError, ValueError):
        after = 0
    qs = Notification.objects.filter(
        recipient=request.user,
        notification_type='environment_recorded',
        is_read=False,
        pk__gt=after,
    ).order_by('-pk')[:5]
    items = [
        {'id': n.pk, 'message': n.message, 'link': n.link}
        for n in qs
    ]
    max_id = max((n['id'] for n in items), default=after)
    return JsonResponse({'items': items, 'max_id': max_id})


# ─── Settings (Tabbed) ─────────────────────────────────────────────────────

ALL_SETTINGS_TABS = [
    {'key': 'company', 'label': 'Company Profile', 'icon': 'fa-building'},
    {'key': 'scopes', 'label': 'Scopes', 'icon': 'fa-flask'},
    {'key': 'roles', 'label': 'Roles', 'icon': 'fa-user-tag'},
    {'key': 'permissions', 'label': 'Permissions', 'icon': 'fa-shield-alt'},
]


def _get_settings_tabs(active):
    tabs = []
    for t in ALL_SETTINGS_TABS:
        t = dict(t)
        t['active'] = t['key'] == active
        tabs.append(t)
    return tabs


@login_required
@login_required
def scope_certificate_template(request, pk):
    """Edit the per-scope custom certificate Django template
    (Settings → Scopes → Cert Layout)."""
    if not has_perm(request.user, 'approve_calibration'):
        messages.error(request, 'Only Lab Leads and Managers can edit certificate templates.')
        return redirect('dashboard')

    scope = get_object_or_404(CalibrationType, pk=pk)
    error = None
    if request.method == 'POST':
        action = request.POST.get('action', 'save')
        if action == 'clear':
            if scope.certificate_template:
                scope.certificate_template = ''
                scope.save(update_fields=['certificate_template'])
                messages.success(request, f'Custom certificate template cleared for "{scope.name}" — the default layout will be used.')
            else:
                messages.info(request, f'"{scope.name}" already uses the default certificate layout.')
            return redirect('scope_cert_template', pk=scope.pk)
        src = request.POST.get('certificate_template', '')
        from django.template import engines, TemplateSyntaxError
        try:
            engines['django'].from_string(src or '')
            scope.certificate_template = src
            scope.save(update_fields=['certificate_template'])
            messages.success(request, f'Custom certificate template saved for "{scope.name}".')
            return redirect('scope_cert_template', pk=scope.pk)
        except TemplateSyntaxError as exc:
            error = str(exc)

    sample_log = CalibrationLog.objects.filter(scope=scope).order_by('-pk').first()
    preview_log = None
    if sample_log and sample_log.status in ('pending_approval', 'pending_qhse', 'approved'):
        preview_log = sample_log

    return render(request, 'core/settings/scope_cert_template.html', {
        'scope': scope,
        'error': error,
        'preview_log': preview_log,
    })


@login_required
def scope_uncertainty_budget(request, pk):
    """Manage the scope's uncertainty budgets (Settings → Scopes → Unc. Budget).

    Uploads an EATL-format workbook (.xlsx), parses its Type-B component table
    into `UncertaintyBudgetComponent` rows, and activates it — the active budget
    then drives CalibrationLog.compute_uncertainty() and the certificate annex.
    """
    if not has_perm(request.user, 'approve_calibration'):
        messages.error(request, 'Only Lab Leads and Managers can manage uncertainty budgets.')
        return redirect('dashboard')

    scope = get_object_or_404(CalibrationType, pk=pk)

    if request.method == 'POST':
        action = request.POST.get('action', 'upload')
        if action in ('activate', 'delete'):
            budget = get_object_or_404(UncertaintyBudget, pk=request.POST.get('budget_id'), scope=scope)
            if action == 'activate':
                scope.uncertainty_budgets.update(active=False)
                budget.active = True
                budget.save(update_fields=['active'])
                messages.success(request, f'"{budget}" is now the active uncertainty budget for {scope.name}.')
            else:
                label = str(budget)
                budget.delete()
                messages.success(request, f'Deleted uncertainty budget "{label}".')
            return redirect('scope_uncertainty_budget', pk=scope.pk)

        # action == upload
        f = request.FILES.get('budget_file')
        if not f:
            messages.error(request, 'Choose a workbook (.xlsx) to upload.')
        elif not f.name.lower().endswith('.xlsx'):
            messages.error(request, 'Only .xlsx workbooks are supported.')
        else:
            from .uncertainty_budget import parse_budget_file
            budget = UncertaintyBudget.objects.create(
                scope=scope,
                title=request.POST.get('title', '').strip(),
                file=f,
                active=False,
            )
            try:
                parsed = parse_budget_file(budget.file.path)
            except Exception as exc:
                budget.parse_status = 'error'
                budget.parse_error = f'{type(exc).__name__}: {exc}'
                budget.save(update_fields=['parse_status', 'parse_error'])
                messages.error(request, f'Could not read the workbook: {exc}')
                return redirect('scope_uncertainty_budget', pk=scope.pk)

            header = parsed['header']
            comps = parsed['components']
            if not comps:
                budget.parse_status = 'error'
                budget.parse_error = 'No Type-B uncertainty table found in the workbook.'
                budget.save(update_fields=['parse_status', 'parse_error'])
                messages.error(
                    request,
                    'No uncertainty-components table found — the file may not be an EATL uncertainty budget.',
                )
                return redirect('scope_uncertainty_budget', pk=scope.pk)

            UncertaintyBudgetComponent.objects.bulk_create([
                UncertaintyBudgetComponent(budget=budget, **c)
                for c in comps
            ])
            budget.doc_ref = header['doc_ref']
            budget.revision = header['revision']
            budget.revised_on = header['revised_on']
            if not budget.title:
                budget.title = header['title'][:200]
            budget.component_count = len(comps)
            budget.parse_status = 'ok'
            budget.parse_error = '\n'.join(parsed['warnings'])
            budget.save(update_fields=[
                'doc_ref', 'revision', 'revised_on', 'title',
                'component_count', 'parse_status', 'parse_error',
            ])
            scope.uncertainty_budgets.exclude(pk=budget.pk).update(active=False)
            budget.active = True
            budget.save(update_fields=['active'])
            details = f'{len(comps)} components'
            if parsed['points']:
                details += f', {len(parsed["points"])} measurement points'
            messages.success(request, f'Budget imported from "{f.name}" ({details}). It is now the active budget for {scope.name}.')

        return redirect('scope_uncertainty_budget', pk=scope.pk)

    active_budget = scope.uncertainty_budgets.filter(active=True).first()
    return render(request, 'core/settings/scope_uncertainty_budget.html', {
        'scope': scope,
        'budgets': scope.uncertainty_budgets.all(),
        'active_budget': active_budget,
    })


def settings_view(request, tab='company'):
    if not has_perm(request.user, 'view_settings'):
        messages.error(request, 'Only administrators can access settings.')
        return redirect('dashboard')

    profile, _ = CompanyProfile.objects.get_or_create(
        pk=1, defaults={'company_name': 'My Company'}
    )
    tabs = _get_settings_tabs(tab)

    if tab == 'company':
        if request.method == 'POST':
            form = CompanyProfileForm(request.POST, request.FILES, instance=profile)
            address_ids = request.POST.getlist('address_id')
            address_labels = request.POST.getlist('address_label')
            address_texts = request.POST.getlist('address_text')
            if form.is_valid():
                form.save()
                kept_ids = [int(aid) for aid in address_ids if aid and aid != 'new']
                CompanyAddress.objects.filter(company_profile=profile).exclude(pk__in=kept_ids).delete()
                for i, label in enumerate(address_labels):
                    if label.strip():
                        addr_text = address_texts[i] if i < len(address_texts) else ''
                        if address_ids[i] and address_ids[i] != 'new':
                            addr = CompanyAddress.objects.get(pk=int(address_ids[i]), company_profile=profile)
                            addr.label = label.strip()
                            addr.address = addr_text
                            addr.save()
                        else:
                            CompanyAddress.objects.create(company_profile=profile, label=label.strip(), address=addr_text)
                messages.success(request, 'Company profile updated.')
                return redirect('settings_tab', tab='company')
        else:
            form = CompanyProfileForm(instance=profile)
        addresses = CompanyAddress.objects.filter(company_profile=profile)
        return render(request, 'core/settings/settings.html', {
            'tabs': tabs, 'active_tab': tab,
            'profile': profile, 'addresses': addresses, 'form': form,
        })

    elif tab == 'scopes':
        scopes = CalibrationType.objects.all()
        from .workflow_models import WorkflowAudit
        from django.forms.models import model_to_dict
        scope_form = CalibrationTypeForm()
        def record_scope(scope, action, before):
            WorkflowAudit.objects.create(created_by=request.user, actor_name=request.user.get_full_name() or request.user.username,
                event=action, before=before, after={'scope_id': scope.pk, **model_to_dict(scope)})
        if request.method == 'POST':
            edit_id = request.POST.get('edit_scope')
            if edit_id:
                scope = get_object_or_404(CalibrationType, pk=edit_id)
                before = model_to_dict(scope)
                values = request.POST.copy()
                for field in CalibrationTypeForm.Meta.fields:
                    if field not in values:
                        values[field] = getattr(scope, field) or ''
                form = CalibrationTypeForm(values, instance=scope)
                if form.is_valid():
                    form.save()
                    record_scope(scope, 'scope_updated', before)
                    messages.success(request, f'Scope "{scope.name}" updated.')
                else:
                    messages.error(request, 'Could not update scope. Check the form fields.')
                return redirect('settings_tab', tab='scopes')
            delete_id = request.POST.get('delete_scope') or request.POST.get('restore_scope')
            if delete_id:
                scope = get_object_or_404(CalibrationType, pk=delete_id)
                before = model_to_dict(scope)
                scope.active = bool(request.POST.get('restore_scope'))
                scope.save(update_fields=['active'])
                record_scope(scope, 'scope_restored' if scope.active else 'scope_archived', before)
                messages.success(request, 'Scope restored.' if scope.active else 'Scope archived. Existing records are retained.')
                return redirect('settings_tab', tab='scopes')
            values = request.POST.copy()
            defaults = CalibrationType()
            for field in CalibrationTypeForm.Meta.fields:
                if field not in values:
                    values[field] = getattr(defaults, field) or ''
            scope_form = CalibrationTypeForm(values)
            if scope_form.is_valid():
                scope = scope_form.save()
                record_scope(scope, 'scope_created', {})
                messages.success(request, 'Scope added.')
                return redirect('settings_tab', tab='scopes')
        return render(request, 'core/settings/settings.html', {
            'tabs': tabs, 'active_tab': tab,
            'scopes': scopes, 'scope_form': scope_form,
        })

    elif tab == 'roles':
        roles = Role.objects.all()
        if request.method == 'POST':
            delete_id = request.POST.get('delete_role')
            if delete_id:
                role = get_object_or_404(Role, pk=delete_id)
                if Personnel.objects.filter(role=role).exists():
                    messages.error(request, f'Cannot delete "{role.name}" — personnel are assigned to it.')
                else:
                    if Role.objects.count() <= 1:
                        messages.error(request, 'Cannot delete the last role.')
                    else:
                        role.delete()
                        messages.success(request, f'Role "{role.name}" deleted.')
                return redirect('settings_tab', tab='roles')
        return render(request, 'core/settings/settings.html', {
            'tabs': tabs, 'active_tab': tab,
            'roles': roles,
        })

    elif tab == 'permissions':
        all_permissions = Permission.objects.all()
        roles = Role.objects.all()
        if request.method == 'POST':
            for role in roles:
                perm_keys = [k for k in request.POST.keys() if k.startswith(f'perms_{role.id}_')]
                selected = [k.split('_', 2)[2] for k in perm_keys]
                role.permissions.set(Permission.objects.filter(codename__in=selected))
            messages.success(request, 'Permissions updated.')
            return redirect('settings_tab', tab='permissions')
        return render(request, 'core/settings/settings.html', {
            'tabs': tabs, 'active_tab': tab,
            'all_permissions': all_permissions, 'roles': roles,
        })

    return redirect('settings_tab', tab='company')


# ─── Role CRUD (Create/Edit within settings) ──────────────────────────────


@login_required
def role_create(request):
    if not has_perm(request.user, 'manage_roles'):
        messages.error(request, 'You do not have permission to manage roles.')
        return redirect('settings_tab', tab='roles')
    if request.method == 'POST':
        form = RoleForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Role created.')
            return redirect('settings_tab', tab='roles')
    else:
        form = RoleForm()
    return render(request, 'core/settings/role_form.html', {'form': form, 'title': 'Create Role'})


@login_required
def role_edit(request, pk):
    if not has_perm(request.user, 'manage_roles'):
        messages.error(request, 'You do not have permission to manage roles.')
        return redirect('settings_tab', tab='roles')
    role = get_object_or_404(Role, pk=pk)
    if request.method == 'POST':
        form = RoleForm(request.POST, instance=role)
        if form.is_valid():
            form.save()
            messages.success(request, 'Role updated.')
            return redirect('settings_tab', tab='roles')
    else:
        form = RoleForm(instance=role)
    return render(request, 'core/settings/role_form.html', {'form': form, 'title': 'Edit Role'})


# ─── Equipment List ────────────────────────────────────────────────────────


@login_required
def equipment_list(request):
    if not has_perm(request.user, 'view_equipment'):
        messages.error(request, 'You do not have permission to view equipment.')
        return redirect('dashboard')

    items = WaybillItem.objects.select_related('waybill').filter(
        waybill__waybill_type='incoming'
    ).order_by('-waybill__created_at')

    # Filters
    status = request.GET.get('status', '')
    client_id = request.GET.get('client', '')
    po_search = request.GET.get('po', '')
    search = request.GET.get('search', '')

    if status:
        items = items.filter(status=status)
    if client_id:
        items = items.filter(waybill__incoming_jobs__client_id=client_id)
    if po_search:
        items = items.filter(waybill__incoming_jobs__purchase_order_number__icontains=po_search)
    if search:
        items = items.filter(
            Q(equipment_description__icontains=search) |
            Q(serial_no__icontains=search)
        )

    # Attach client/PO info from linked job
    equipped = []
    for item in items:
        job = Job.objects.filter(incoming_waybill=item.waybill).first()
        equipped.append({
            'item': item,
            'client': job.client if job else None,
            'po': job.purchase_order_number if job else '',
            'latest_log': item.calibration_logs.first(),
        })

    # Pagination
    paginator = Paginator(equipped, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    clients = Client.objects.all()
    return render(request, 'core/equipment/list.html', {
        'equipment': page_obj,
        'clients': clients,
        'filters': {
            'status': status,
            'client': client_id,
            'po': po_search,
            'search': search,
        },
        'status_choices': WaybillItem.WAYBILL_ITEM_STATUS_CHOICES,
    })


# ─── OCR Integration ────────────────────────────────────────────────────────


@login_required
def ocr_health(request):
    from . import ocr_engine
    h = ocr_engine.health()
    return JsonResponse({
        'ocr_available': h['ocr_available'],
        'provider': h['provider'],
    })


@login_required
def ocr_parse_text(request):
    """Parse already-OCRed input (from a browser-side tesseract.js run, e.g. on
    PythonAnywhere free tier where no server-side engine runs) into waybill items.

    Accepts either:
      * JSON ``"text"`` — plain OCR text (parsed with best-effort heuristics), or
      * JSON ``"lines"`` — a list of ``{text, bbox, confidence}`` from tesseract.js
        word/line boxes, enabling the same accurate column-table parse used by the
        server-side engines.

    Pure parsing: no OCR, no model download — tiny footprint.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    from .ocr_parser import parse_waybill_text, parse_waybill_items

    payload = None
    if request.content_type == 'application/json':
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            payload = {}
    if payload is None:
        payload = request.POST.dict()

    lines = payload.get('lines')
    text = payload.get('text', '')
    raw_text = ''
    try:
        if lines:
            items = parse_waybill_items({'lines': lines})
            raw_text = '\n'.join(l.get('text', '') for l in lines)
        elif text:
            items = parse_waybill_text(text)
            raw_text = text
        else:
            return JsonResponse({'error': 'No text or lines provided'}, status=400)
    except Exception as exc:
        logger.exception('waybill text parsing failed')
        return JsonResponse({'items': [], 'raw_text': raw_text, 'error': str(exc)}, status=500)

    return JsonResponse({
        'items': items,
        'raw_text': raw_text,
        'provider': 'text',
        'mock': False,
        'error': None,
    })


@login_required
def ocr_scan_certificate(request, pk):
    log = get_object_or_404(CalibrationLog, pk=pk)
    if not log.certificate:
        return JsonResponse({'error': 'No certificate uploaded'}, status=400)

    from . import ocr_engine
    from .ocr_parser import parse_waybill_items
    result = ocr_engine.extract(log.certificate.path)
    result['items'] = parse_waybill_items(result)
    return JsonResponse(result)


@login_required
def ocr_scan_upload(request):
    """Scan an arbitrary uploaded file. Returns raw OCR + parsed waybill items."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file provided'}, status=400)

    from . import ocr_engine
    from .ocr_parser import parse_waybill_items
    result = ocr_engine.extract_upload(request.FILES['file'])
    result['items'] = parse_waybill_items(result)
    return JsonResponse(result)


@login_required
def waybill_ocr_extract(request, pk):
    """Scan a saved waybill's document and return parsed equipment items.

    Read-only: does NOT create ``WaybillItem`` rows — used by the incoming
    waybill create form to auto-fill item blocks before saving.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    waybill = get_object_or_404(Waybill, pk=pk)
    if not waybill.file_upload:
        return JsonResponse({'error': 'No file attached to this waybill'}, status=400)

    from . import ocr_engine
    from .ocr_parser import parse_waybill_items
    result = ocr_engine.extract(waybill.file_upload.path)
    result['items'] = parse_waybill_items(result)
    return JsonResponse(result)


@login_required
def waybill_ocr_rescan_create_items(request, pk):
    """Scan a saved waybill's document and create missing WaybillItem rows.

    Existing items (matched by serial_no) are left untouched. Any serial
    not already on the waybill is created. Redirect back to the waybill.
    """
    if not has_perm(request.user, 'create_waybills'):
        messages.error(request, 'You do not have permission to edit waybills.')
        return redirect('waybill_detail', pk=pk)
    waybill = get_object_or_404(Waybill, pk=pk)
    if not waybill.file_upload:
        messages.warning(request, 'This waybill has no file attached.')
        return redirect('waybill_detail', pk=pk)

    from . import ocr_engine
    from .ocr_parser import parse_waybill_items
    result = ocr_engine.extract(waybill.file_upload.path)
    items = parse_waybill_items(result)

    existing_serials = set(
        waybill.items.values_list('serial_no', flat=True)
    )
    created = 0
    for it in items:
        serial = (it.get('serial_no') or '').strip()
        if not serial or serial in existing_serials:
            continue
        WaybillItem.objects.create(
            waybill=waybill,
            equipment_description=it.get('equipment_description', '') or '',
            quantity=it.get('quantity') or 1,
            serial_no=serial,
            model_no=it.get('model_no', '') or None,
            manufacturer=it.get('manufacturer', '') or None,
            range_field=it.get('range_field', '') or None,
        )
        existing_serials.add(serial)
        created += 1

    if result.get('mock'):
        messages.warning(
            request,
            'OCR service was unavailable — items could not be scanned. '
            'You can add equipment manually.',
        )
    elif not items:
        messages.info(request, 'No equipment items were found in the document.')
    else:
        messages.success(request, f'{created} equipment item(s) added from the scanned document.')

    return redirect('waybill_detail', pk=pk)


# ─── Primaries (company reference / calibration standards) ─────────────────────

class PrimaryListView(LoginRequiredMixin, ListView):
    model = Primary
    template_name = 'core/primaries/list.html'
    context_object_name = 'primaries'
    paginate_by = 20

    def get_queryset(self):
        qs = Primary.objects.select_related('scope', 'unit').prefetch_related('units').order_by('name')
        search = self.request.GET.get('search', '')
        status = self.request.GET.get('status', '')
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(serial_no__icontains=search) |
                Q(manufacturer__icontains=search)
            )
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filters'] = {
            'search': self.request.GET.get('search', ''),
            'status': self.request.GET.get('status', ''),
        }
        context['status_choices'] = Primary.STATUS_CHOICES
        return context


class PrimaryDetailView(LoginRequiredMixin, DetailView):
    model = Primary
    template_name = 'core/primaries/detail.html'
    context_object_name = 'primary'

    def get_queryset(self):
        return super().get_queryset().select_related('scope', 'unit').prefetch_related('units')


class PrimaryCreateView(LoginRequiredMixin, CreateView):
    model = Primary
    form_class = PrimaryForm
    template_name = 'core/primaries/create.html'
    success_url = reverse_lazy('equipment_list')

    def dispatch(self, request, *args, **kwargs):
        if not (has_perm(request.user, 'approve_calibration') or has_perm(request.user,'manage_ei_jobs')):
            messages.error(request, 'Only managers can add primaries.')
            return redirect('primary_list')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context.get('form') or self.get_form()
        try:
            selected = [u.pk for u in (form['units'].value() or [])]
        except Exception:
            selected = []
        context['selected_units_json'] = json.dumps(selected)
        return context

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.save()
        self.object=instance
        form.save_m2m()
        if not instance.unit_id:
            first = instance.units.first()
            if first:
                instance.unit = first
                instance.save(update_fields=['unit'])
        from .ei_workflow import audit
        audit(self.request.user,None,'equipment_registered',after={'equipment':instance.pk,'asset_number':instance.asset_number,'name':instance.name,'last_calibrated':str(instance.last_calibrated),'due_date':str(instance.calibration_due_date)})
        return redirect(self.get_success_url())


class PrimaryUpdateView(LoginRequiredMixin, UpdateView):
    model = Primary
    form_class = PrimaryForm
    template_name = 'core/primaries/create.html'
    success_url = reverse_lazy('equipment_list')

    def dispatch(self, request, *args, **kwargs):
        if not (has_perm(request.user, 'approve_calibration') or has_perm(request.user,'manage_ei_jobs')):
            messages.error(request, 'Only managers can edit primaries.')
            return redirect('primary_list')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context.get('form') or self.get_form()
        try:
            selected = [u.pk for u in (form['units'].value() or [])]
        except Exception:
            selected = []
        context['selected_units_json'] = json.dumps(selected)
        return context

    def form_valid(self, form):
        # Keep status in sync with the due date
        original=Primary.objects.get(pk=self.object.pk)
        before={name:str(getattr(original,name)) for name in ('name','asset_number','certificate_no','last_calibrated','calibration_due_date','calibration_frequency','include_programme','is_reference','status')}
        instance = form.save(commit=False)
        if instance.calibration_due_date and instance.calibration_due_date <= date.today() and instance.status == 'active':
            instance.status = 'pending_maintenance'
        instance.save()
        form.save_m2m()
        # `unit` FK mirrors the first M2M entry
        first = instance.units.first()
        if first and instance.unit_id != first.pk:
            instance.unit = first
            instance.save(update_fields=['unit'])
        from .ei_workflow import audit
        audit(self.request.user,None,'equipment_profile_updated',before=before,after={'equipment':instance.pk,**{name:str(getattr(instance,name)) for name in before}})
        return redirect(self.get_success_url())


class PrimaryDeleteView(LoginRequiredMixin, DeleteView):
    model = Primary
    template_name = 'core/primaries/confirm_delete.html'
    success_url = reverse_lazy('primary_list')

    def dispatch(self, request, *args, **kwargs):
        if not has_perm(request.user, 'approve_calibration'):
            messages.error(request, 'Only managers can delete primaries.')
            return redirect('primary_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        from .ei_workflow import audit
        before={'status':self.object.status,'equipment':self.object.pk}
        self.object.status='inactive';self.object.save(update_fields=['status'])
        audit(self.request.user,None,'equipment_deactivated',before=before,after={'equipment':self.object.pk,'status':'inactive'})
        messages.success(self.request,'Equipment deactivated. All calibration records and history are retained.')
        return redirect('equipment_list')
