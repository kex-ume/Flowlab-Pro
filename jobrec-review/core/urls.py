from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import PasswordChangeView
from . import views
from . import ei_views
from . import capa_views
from . import equipment_records
from . import retained_records
from . import record_removal
from .forms import CustomPasswordChangeForm
from .integrated_auth import IntegratedPasswordChangeView

urlpatterns = [
    path('records/remove/',record_removal.remove,name='ei_record_remove'),
    path('', views.dashboard, name='dashboard'),
    path('records/retained/',retained_records.register,name='ei_retained_records'),
    path('personnel/records/<str:kind>/<int:pk>/',retained_records.personnel_snapshot,name='ei_personnel_snapshot'),
    path('capa/',capa_views.register,name='ei_capa_list'),
    path('capa/action/<str:action>/',capa_views.action,name='ei_capa_create'),
    path('capa/<int:pk>/',capa_views.detail,name='ei_capa_detail'),
    path('capa/<int:pk>/action/<str:action>/',capa_views.action,name='ei_capa_action'),
    path('capa/documents/<int:pk>/',capa_views.document,name='ei_capa_document'),

    # Authentication
    path('login/', auth_views.LoginView.as_view(
        template_name='core/auth/login.html'
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('password/change/', IntegratedPasswordChangeView.as_view(
        form_class=CustomPasswordChangeForm,
        template_name='core/auth/password_change.html',
        success_url=reverse_lazy('password_change_done'),
    ), name='password_change'),
    path('password/change/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='core/auth/password_change_done.html',
    ), name='password_change_done'),

    # Jobs
    path('jobs/workflow/save/', ei_views.job_save, name='ei_job_save'),
    path('jobs/workflow/eligible/', ei_views.eligible_lookup, name='ei_eligible_lookup'),
    path('jobs/workflow/<int:pk>/save/', ei_views.job_save, name='ei_job_edit'),
    path('jobs/workflow/<int:pk>/action/<str:action>/', ei_views.job_action, name='ei_job_action'),
    path('jobs/workflow/<int:pk>/documents/', ei_views.job_upload, name='ei_job_upload'),
    path('jobs/documents/<uuid:token>/', ei_views.document_view, name='ei_document_view'),
    path('jobs/workflow/<int:pk>/schedule/', ei_views.schedule_action, name='ei_schedule_propose'),
    path('jobs/workflow/<int:pk>/schedule/<int:revision>/', ei_views.schedule_action, name='ei_schedule_decide'),
    path('jobs/uuts/<int:pk>/', ei_views.uut_workspace, name='ei_uut_workspace'),
    path('jobs/uuts/<int:pk>/action/<str:action>/', ei_views.uut_action, name='ei_uut_action'),
    path('jobs/records/<int:pk>/', ei_views.record_view, name='ei_record_view'),
    path('jobs/records/<int:pk>/data/', ei_views.record_save, name='ei_record_save'),
    path('jobs/records/<int:pk>/report/', ei_views.record_report, name='ei_record_report'),
    path('jobs/records/<int:pk>/action/<str:action>/', ei_views.record_action, name='ei_record_action'),
    path('settings/log-templates/', ei_views.template_workspace, name='ei_log_templates'),
    path('settings/scopes/<int:scope_id>/log-templates/', ei_views.template_workspace, name='ei_scope_templates'),
    path('settings/scopes/<int:scope_id>/log-templates/<str:action>/', ei_views.template_action, name='ei_template_create'),
    path('settings/scopes/<int:scope_id>/log-templates/<int:pk>/<str:action>/', ei_views.template_action, name='ei_template_action'),
    path('personnel/<int:pk>/competency/', ei_views.personnel_workspace, name='ei_personnel_workspace'),
    path('personnel/verify/<uuid:token>/', ei_views.personnel_workspace, name='ei_personnel_verify'),
    path('personnel/<int:pk>/records/<str:action>/', ei_views.personnel_action, name='ei_personnel_action'),
    path('personnel/evidence/<int:pk>/view/', ei_views.personnel_file, name='ei_personnel_file'),
    path('jobs/', views.JobListView.as_view(), name='job_list'),
    path('jobs/new/', views.JobCreateView.as_view(), name='job_create'),
    path('jobs/<int:pk>/', views.JobDetailView.as_view(), name='job_detail'),
    path('jobs/<int:pk>/edit/', views.JobUpdateView.as_view(), name='job_update'),
    path('jobs/<int:pk>/delete/', record_removal.legacy_delete, {'kind':'ei_job'}, name='job_delete'),
    path('jobs/<int:pk>/assign/', views.job_assign, name='job_assign'),
    path('jobs/<int:pk>/unassign/<int:personnel_id>/', views.job_unassign, name='job_unassign'),
    path('jobs/status/<str:status>/', views.JobStatusListView.as_view(), name='job_by_status'),

    # Waybills
    path('waybills/', views.WaybillListView.as_view(), name='waybill_list'),
    path('waybills/fetch-incoming/', views.fetch_incoming_waybill, name='fetch_incoming_waybill'),
    path('waybills/incoming/new/', views.IncomingWaybillCreateView.as_view(), name='incoming_waybill_create'),
    path('waybills/incoming/<int:pk>/', views.WaybillDetailView.as_view(), name='waybill_detail'),
    path('waybills/outgoing/new/', views.OutgoingWaybillCreateView.as_view(), name='outgoing_waybill_create'),
    path('waybills/outgoing/<int:pk>/', views.OutgoingWaybillDetailView.as_view(), name='outgoing_waybill_detail'),
    path('waybills/entry-dispatch/', views.entry_dispatch_log, name='entry_dispatch'),

    # Personnel
    path('personnel/', views.PersonnelListView.as_view(), name='personnel_list'),
    path('personnel/new/', views.PersonnelCreateView.as_view(), name='personnel_create'),
    path('personnel/<int:pk>/', views.PersonnelDetailView.as_view(), name='personnel_detail'),
    path('personnel/<int:pk>/edit/', views.PersonnelUpdateView.as_view(), name='personnel_update'),
    path('personnel/<int:pk>/delete/', record_removal.legacy_delete, {'kind':'ei_personnel'}, name='personnel_delete'),
    path('personnel/<int:pk>/qr/', views.personnel_qr_card, name='personnel_qr'),
    path('personnel/<int:pk>/qr/card/', views.personnel_qr_card, {'format': 'card'}, name='personnel_qr_card'),
    path('qr/<path:token>/', views.qr_login, name='qr_login'),

    # Personnel AJAX
    path('api/personnel-by-scope/', views.personnel_by_scope, name='personnel_by_scope'),
    path('api/units-by-scope/<int:scope_id>/', views.units_by_scope, name='units_by_scope'),
    path('api/procedure-for-scope/<int:scope_id>/', views.procedure_for_scope, name='procedure_for_scope'),
    path('api/client-lookup/', views.client_lookup, name='client_lookup'),

    # Calibration Procedures
    path('procedures/', views.procedure_list, name='procedure_list'),
    path('procedures/assign/', views.procedure_assign, name='procedure_assign'),
    path('procedures/<int:pk>/', views.procedure_detail, name='procedure_detail'),
    path('procedures/<int:pk>/edit/', views.procedure_edit, name='procedure_edit'),
    path('procedures/<int:pk>/submit/', views.procedure_submit, name='procedure_submit'),

    # Environment
    path('environment/', views.EnvironmentListView.as_view(), name='environment_list'),
    path('environment/new/', views.EnvironmentCreateView.as_view(), name='environment_create'),
    path('environment/data/', views.environment_data, name='environment_data'),
    path('environment/export/', views.environment_export, name='environment_export'),

    # Documents archive (ISO 17025 yearly export)
    path('documents/', views.documents_list, name='documents_list'),
    path('documents/<int:year>/export/', views.documents_export_year, name='documents_export_year'),

    # Clients
    path('clients/', views.ClientListView.as_view(), name='client_list'),
    path('clients/new/', views.ClientCreateView.as_view(), name='client_create'),
    path('clients/<int:pk>/', views.ClientDetailView.as_view(), name='client_detail'),
    path('clients/<int:pk>/edit/', views.ClientUpdateView.as_view(), name='client_update'),
    path('clients/<int:pk>/delete/', record_removal.legacy_delete, {'kind':'ei_client'}, name='client_delete'),

    # Calibration Logs
    path('calibration-logs/', views.CalibrationLogListView.as_view(), name='calibration_log_list'),
    path('calibration-logs/new/<int:waybill_item_id>/', views.CalibrationLogCreateView.as_view(), name='calibration_log_create'),
    path('calibration-logs/<int:pk>/', views.CalibrationLogDetailView.as_view(), name='calibration_log_detail'),
    path('calibration-logs/<int:pk>/edit/', views.CalibrationLogUpdateView.as_view(), name='calibration_log_update'),
    path('calibration-logs/<int:pk>/review/', views.calibration_log_review, name='calibration_log_review'),
    path('calibration-logs/<int:pk>/approve/', views.calibration_log_approve, name='calibration_log_approve'),
    path('calibration-logs/<int:pk>/certificate/', views.calibration_certificate, name='calibration_certificate'),
    path('calibration-logs/<int:pk>/reject/', views.calibration_log_reject, name='calibration_log_reject'),
    path('calibration-logs/<int:pk>/upload-certificate/', views.calibration_log_upload_certificate, name='calibration_log_upload_certificate'),
    path('calibration-logs/<int:pk>/reissue-cert-no/', views.calibration_log_reissue_cert, name='calibration_log_reissue_cert'),

    # Pre-Calibration Logs
    path('pre-calibration/', views.PreCalibrationLogListView.as_view(), name='pre_calibration_list'),
    path('pre-calibration/new/<int:waybill_item_id>/', views.PreCalibrationLogCreateView.as_view(), name='pre_calibration_create'),
    path('pre-calibration/<int:pk>/', views.PreCalibrationLogDetailView.as_view(), name='pre_calibration_detail'),
    path('pre-calibration/<int:pk>/review/', views.pre_cal_review, name='pre_cal_review'),
    path('equipment/<int:pk>/repair-complete/', views.repair_complete, name='repair_complete'),

    # Notifications
    path('notifications/', views.notification_list, name='notification_list'),
    path('notifications/read-all/', views.notification_mark_all_read, name='notification_mark_all_read'),
    path('notifications/<int:pk>/read/', views.notification_read, name='notification_read'),
    path('notifications/popups/', views.notification_popups, name='notification_popups'),

    # Settings (replaces company profile)
    path('settings/', views.settings_view, name='settings'),
    path('settings/<str:tab>/', views.settings_view, name='settings_tab'),
    path('settings/roles/create/', views.role_create, name='role_create'),
    path('settings/scopes/<int:pk>/certificate-template/', views.scope_certificate_template, name='scope_cert_template'),
    path('settings/scopes/<int:pk>/uncertainty-budget/', views.scope_uncertainty_budget, name='scope_uncertainty_budget'),
    path('settings/roles/<int:pk>/edit/', views.role_edit, name='role_edit'),

    # Equipment
    path('equipment/', equipment_records.register, name='equipment_list'),
    path('equipment/received/', views.equipment_list, name='ei_received_equipment'),
    path('equipment/programme/',equipment_records.register,{'programme':True},name='ei_calibration_programme'),
    path('equipment/<int:pk>/',equipment_records.detail,name='ei_equipment_detail'),
    path('equipment/<int:pk>/records/<str:action>/',equipment_records.record_action,name='ei_equipment_record_add'),
    path('equipment/<int:pk>/records/<int:record_id>/<str:action>/',equipment_records.record_action,name='ei_equipment_record_action'),
    path('equipment/records/<int:pk>/file/',equipment_records.document,name='ei_equipment_file'),

    # Primaries (company reference standards)
    path('primaries/', views.PrimaryListView.as_view(), name='primary_list'),
    path('primaries/new/', views.PrimaryCreateView.as_view(), name='primary_create'),
    path('primaries/<int:pk>/', views.PrimaryDetailView.as_view(), name='primary_detail'),
    path('primaries/<int:pk>/edit/', views.PrimaryUpdateView.as_view(), name='primary_update'),
    path('primaries/<int:pk>/delete/', views.PrimaryDeleteView.as_view(), name='primary_delete'),

    # OCR
    path('ocr/health/', views.ocr_health, name='ocr_health'),
    path('ocr/upload/', views.ocr_scan_upload, name='ocr_scan_upload'),
    path('ocr/parse-text/', views.ocr_parse_text, name='ocr_parse_text'),
    path('ocr/scan/<int:pk>/', views.ocr_scan_certificate, name='ocr_scan_certificate'),
    path('waybills/<int:pk>/ocr/', views.waybill_ocr_extract, name='waybill_ocr_extract'),
    path('waybills/<int:pk>/ocr/rescan/', views.waybill_ocr_rescan_create_items, name='waybill_ocr_rescan'),
]
