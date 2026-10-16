"""Read-only index of retained originals, without duplicating private records."""
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse
from . import ei_workflow as service
from .personnel_records import flags
from .models import (Personnel,PersonnelEvidence,PersonnelCompetency,PersonnelAuthorization,TechnicalRecord,PreCalibrationLog,CalibrationLog,EquipmentRecord,CAPADocument)


@login_required
def register(request):
    from .capa_views import visible as visible_capa
    rows=[]
    def add(group,title,actor,date,status,url,identifier):rows.append({'group':group,'title':title,'actor':actor,'date':date,'status':status,'url':url,'identifier':identifier})
    people=Personnel.objects.all() if any(flags(request.user).values()) else Personnel.objects.filter(user=request.user)
    for row in PersonnelEvidence.objects.filter(personnel__in=people).select_related('personnel'):
        if row.file:add(row.kind.replace('_',' ').title(),row.personnel.name+' · '+row.title,row.actor_name,row.created_at,row.get_status_display(),reverse('ei_personnel_file',args=[row.pk]),'PE-'+str(row.pk))
    for row in PersonnelCompetency.objects.filter(personnel__in=people).select_related('personnel','scope'):
        add('Competency Assessment',row.personnel.name+' · '+row.scope.name+' · '+row.method_reference,row.actor_name,row.created_at,row.get_result_display(),reverse('ei_personnel_snapshot',args=['competency',row.pk]),'CO-'+str(row.pk))
    from .personnel_records import authorization_status
    for row in PersonnelAuthorization.objects.filter(personnel__in=people).select_related('personnel','scope'):
        add('Technical Authorization',row.personnel.name+' · '+row.get_activity_display(),row.actor_name,row.created_at,authorization_status(row.personnel,row),reverse('ei_personnel_snapshot',args=['authorization',row.pk]),'AU-'+str(row.pk))
    if service.has_perm(request.user,'view_jobs'):
        jobs=service.visible_jobs(request.user)
        for row in TechnicalRecord.objects.filter(uut__job__in=jobs).exclude(status='draft').select_related('uut'):
            add(row.get_kind_display(),row.uut.name,row.actor_name,row.created_at,row.get_status_display(),reverse('ei_record_view',args=[row.pk])+'?readonly=1','TR-'+str(row.pk))
    if service.has_perm(request.user,'perform_pre_calibration') or service.has_perm(request.user,'review_pre_calibration'):
        for row in PreCalibrationLog.objects.select_related('waybill_item','inspected_by'):
            add('Assessment',row.waybill_item.equipment_description,row.inspected_by.username if row.inspected_by else 'Not recorded',row.created_at,'Reviewed' if row.reviewed_at else 'Pending Review',reverse('pre_calibration_detail',args=[row.pk]),row.doc_no or 'PC-'+str(row.pk))
    logs=CalibrationLog.objects.filter(Q(recorded_by=request.user)|Q(calibrated_by__user=request.user)|Q(reviewed_by=request.user)|Q(approved_by=request.user))
    if service.supervisor(request.user):logs=CalibrationLog.objects.all()
    for row in logs.select_related('waybill_item','recorded_by'):
        add('Calibration Log',row.waybill_item.equipment_description,row.recorded_by.username if row.recorded_by else 'Not recorded',row.created_at,row.get_status_display(),reverse('calibration_log_detail',args=[row.pk]),'CL-'+str(row.pk))
    if service.supervisor(request.user) or service.has_perm(request.user,'view_equipment'):
        for row in EquipmentRecord.objects.select_related('equipment'):
            add('Equipment '+row.kind,row.equipment.name+' · '+row.original_name,row.actor_name,row.created_at,row.get_status_display(),reverse('ei_equipment_file',args=[row.pk]),'ER-'+str(row.pk))
    for doc in CAPADocument.objects.filter(record__in=visible_capa(request.user)).select_related('record'):
        add('CAPA Evidence',doc.record.ncr_number+' · '+doc.get_kind_display(),doc.actor_name,doc.created_at,doc.record.get_status_display(),reverse('ei_capa_document',args=[doc.pk]),'CA-'+str(doc.pk))
    search=request.GET.get('search','').strip().lower();category=request.GET.get('category','')
    categories=sorted(set(row['group'] for row in rows))
    rows=[row for row in rows if (not category or row['group']==category) and (not search or search in (row['title']+' '+row['identifier']+' '+row['actor']).lower())]
    rows.sort(key=lambda r:r['date'],reverse=True)
    return render(request,'core/records/retained.html',{'records':rows,'categories':categories,'search':request.GET.get('search',''),'category':category})


@login_required
def personnel_snapshot(request,kind,pk):
    from django.shortcuts import get_object_or_404
    from django.http import Http404
    from .ei_views import require_personnel
    from .personnel_records import authorization_status
    if kind not in ('competency','authorization'):raise Http404('Record type not found.')
    model=PersonnelCompetency if kind=='competency' else PersonnelAuthorization
    row=get_object_or_404(model.objects.select_related('personnel','scope'),pk=pk)
    require_personnel(request.user,row.personnel)
    from django.utils import timezone
    fields=[('Personnel',row.personnel.name),('Personnel ID',row.personnel_id),('Scope',row.scope.name if row.scope else 'All authorized scopes'),('Actual Officer / Assessor',row.actor_name),('Recorded At',timezone.localtime(row.created_at).strftime('%d %b %Y %H:%M')),('Method',row.method_reference or 'Scope-wide')]
    if kind=='competency':
        fields.extend([('Assessment Date',row.assessed_on),('Reassessment Due',row.expires_on or 'Not set'),('Result',row.get_result_display()),('Previous Record',row.previous_id or 'None')]);evidence=row.evidence
    else:
        fields.extend([('Activity',row.get_activity_display()),('Current Status',authorization_status(row.personnel,row)),('Effective Date',row.effective_from),('Expiry',row.expires_on or 'No expiry'),('Version',row.version),('Authority / Revision Reason',row.reason),('Suspension Reason',row.suspension_reason),('Revocation Reason',row.revocation_reason)]);evidence=row.memo
    return render(request,'core/records/snapshot.html',{'title':'Competency Assessment' if kind=='competency' else 'Technical Authorization','fields':fields,'evidence':evidence})
