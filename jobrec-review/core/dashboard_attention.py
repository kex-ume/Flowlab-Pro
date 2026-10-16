"""Read-only, permission-aware E&I action queue built from current records."""
from datetime import timedelta
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from . import ei_workflow as workflow
from .auth_utils import has_perm
from .personnel_records import designated, flags, authorized_log, compliance
from .models import (Job,TechnicalRecord,JobScheduleRevision,Personnel,PersonnelEvidence,
    PersonnelCompetency,PersonnelAuthorization,PersonnelCorrectionRequest,EnvironmentReminder,
    Primary,CalibrationLog,PreCalibrationLog,Client,CalibrationProcedure,Notification)


def dashboard_data(user):
    from .capa_views import visible as visible_capa
    today=timezone.localdate();soon=today+timedelta(days=30)
    jobs=workflow.visible_jobs(user) if has_perm(user,'view_jobs') else Job.objects.none()
    items=[]
    def add(key,title,count,url,severity='pending',category='Work'):
        if count:items.append({'key':key,'title':title,'count':count,'url':url,'severity':severity,'category':category})
    def link(name,*args):return reverse(name,args=args)
    managed=jobs.filter(workflow_managed=True)
    active=jobs.exclude(Q(workflow_managed=True,progress_status='completed')|Q(workflow_managed=False,job_status__in=['completed','dispatched']))
    add('overdue','Overdue jobs',active.filter(scheduled_end_date__lt=today).count(),link('job_list')+'?overdue=1','urgent','Jobs')
    if workflow.supervisor(user):
        add('job_approval','Jobs awaiting approval',managed.filter(approval_state='awaiting').count(),link('job_list')+'?approval=awaiting',category='Jobs')
        revisions=JobScheduleRevision.objects.filter(job__in=jobs,status='pending').exclude(created_by=user)
        for revision in revisions.select_related('job'):
            add('schedule_'+str(revision.pk),'Schedule revision · '+revision.job.job_code,1,link('job_detail',revision.job_id),category='Jobs')
    own=managed.filter(Q(creator=user)|Q(assigned_to__user=user)).distinct()
    for job in own.filter(approval_state__in=['draft','reverted']):
        if job.creator_id==user.pk:add('draft_'+str(job.pk),job.job_code+' · '+('Reverted submission' if job.approval_state=='reverted' else 'Continue saved draft'),1,link('job_detail',job.pk),category='Jobs')
    for job in own.filter(approval_state='approved',commenced_at__isnull=True):
        if job.primary_assignee_id and job.primary_assignee.user_id==user.pk:add('start_'+str(job.pk),'Commence approved job · '+job.job_code,1,link('job_detail',job.pk),category='Jobs')
    for row in TechnicalRecord.objects.filter(uut__job__in=jobs,status__in=['submitted','reviewed','rework','draft']).select_related('uut__job','uut__scope','uut__template'):
        action='review' if row.status=='submitted' else 'approve' if row.status=='reviewed' else None
        if action and row.created_by_id!=user.pk and workflow.can_contribute(user,row.uut,action):
            add('record_'+str(row.pk),row.get_kind_display()+' · '+action+' · '+row.uut.name,1,link('ei_record_view',row.pk),category='Technical records')
        elif row.status in ('draft','rework') and row.created_by_id==user.pk:
            add('record_'+str(row.pk),row.get_kind_display()+' · '+row.get_status_display()+' · '+row.uut.name,1,link('ei_record_view',row.pk),category='Technical records')
    for row in CalibrationLog.objects.filter(status__in=['pending_review','pending_approval','pending_qhse','rejected']).select_related('scope','calibrated_by'):
        activity='review' if row.status=='pending_review' else 'approve'
        if row.status=='rejected' and row.recorded_by_id==user.pk or row.status!='rejected' and has_perm(user,activity+'_calibration') and row.recorded_by_id!=user.pk and (not row.calibrated_by_id or row.calibrated_by.user_id!=user.pk) and authorized_log(user,row,activity):
            if activity=='review' and row.reviewer_id and row.reviewer_id!=user.pk:continue
            add('legacy_'+str(row.pk),'Calibration log '+str(row.pk)+' · '+row.get_status_display(),1,link('calibration_log_detail',row.pk),category='Technical records')
    if has_perm(user,'review_pre_calibration'):
        for row in PreCalibrationLog.objects.filter(review_decision__isnull=True).exclude(inspected_by=user)[:30]:
            add('pre_'+str(row.pk),'Pre-calibration assessment '+str(row.pk),1,link('pre_calibration_detail',row.pk),category='Technical records')
    people=Personnel.objects.all() if any(flags(user).values()) else Personnel.objects.filter(user=user)
    active_people=people.filter(user__is_active=True,employment_status='active')
    qualification_missing=0;training_missing=0
    for person in active_people:
        states=compliance(person)
        qualification_missing+=states['qualification']['code']=='missing'
        training_missing+=states['training']['code']=='missing'
    add('qualification_missing','Personnel qualification evidence not uploaded',qualification_missing,link('personnel_list')+'?category=qualification&status=missing',category='Personnel')
    add('training_missing','Personnel training evidence not uploaded',training_missing,link('personnel_list')+'?category=training&status=missing',category='Personnel')
    if designated(user,'verify_personnel_records'):
        for row in PersonnelEvidence.objects.filter(status='pending').exclude(created_by=user).select_related('personnel'):
            add('evidence_'+str(row.pk),'Verify '+row.personnel.name+' · '+row.title,1,link('ei_personnel_workspace',row.personnel_id),category='Personnel')
    if flags(user)['may_manage'] or designated(user,'verify_personnel_records'):
        for row in PersonnelCorrectionRequest.objects.filter(status='pending',personnel__in=people):
            add('correction_'+str(row.pk),'Personnel correction request',1,link('ei_personnel_workspace',row.personnel_id),category='Personnel')
    for model,code in [(PersonnelCompetency,'competency'),(PersonnelAuthorization,'authorization')]:
        rows=model.objects.filter(personnel__in=people,expires_on__lte=soon)
        if code=='competency':rows=rows.filter(revisions__isnull=True)
        else:rows=rows.filter(revoked_at__isnull=True)
        for row in rows.select_related('personnel'):
            expiry=row.expires_on<today
            add(code+'_'+str(row.pk),row.personnel.name+' · '+code+(' expired' if expiry else ' review due '+str(row.expires_on)),1,link('ei_personnel_workspace',row.personnel_id),'urgent' if expiry else 'upcoming','Personnel')
    for row in PersonnelAuthorization.objects.filter(personnel__in=people,suspended_at__isnull=False,revoked_at__isnull=True).select_related('personnel'):
        add('suspended_'+str(row.pk),row.personnel.name+' · authorization suspended',1,link('ei_personnel_workspace',row.personnel_id),'urgent','Personnel')
    for row in PersonnelEvidence.objects.filter(personnel__in=people,status='verified',expires_on__lte=soon).select_related('personnel'):
        add('expiry_evidence_'+str(row.pk),row.personnel.name+' · '+row.title+' expiry '+str(row.expires_on),1,link('ei_personnel_workspace',row.personnel_id),'urgent' if row.expires_on<today else 'upcoming','Personnel')
    if has_perm(user,'record_environment'):
        current_hour=timezone.localtime().hour
        count=EnvironmentReminder.objects.filter(date=today,is_recorded=False,time__lte=f'{current_hour:02d}').count()
        add('environment','Environmental recordings due',count,link('environment_list'),category='Laboratory')
    if has_perm(user,'view_equipment') or workflow.supervisor(user):
        assets=Primary.objects.filter(include_programme=True).exclude(status='inactive')
        add('reference_expired','Equipment calibration overdue / maintenance',assets.filter(Q(status='pending_maintenance')|Q(calibration_due_date__lt=today)).count(),link('ei_calibration_programme'),'urgent','Laboratory')
        add('reference_due','Equipment calibration due within 30 days',assets.filter(calibration_due_date__gte=today,calibration_due_date__lte=soon).count(),link('ei_calibration_programme'),'upcoming','Laboratory')
        add('equipment_schedule_missing','Equipment missing calibration schedule',assets.filter(calibration_due_date__isnull=True).count(),link('ei_calibration_programme'),category='Laboratory')
        from .models import EquipmentRecord
        if workflow.supervisor(user):
            for row in EquipmentRecord.objects.filter(status='pending').exclude(created_by=user).select_related('equipment'):
                add('equipment_record_'+str(row.pk),row.equipment.name+' · '+row.kind+' report verification',1,link('ei_equipment_detail',row.equipment_id)+'?tab='+row.kind,category='Equipment')
    if has_perm(user,'create_clients'):add('clients','Client information incomplete',Client.objects.filter(status='pending_info').count(),link('client_list')+'?status=pending_info',category='Records')
    if has_perm(user,'approve_procedures') or workflow.supervisor(user):add('procedures','Procedures awaiting approval',CalibrationProcedure.objects.filter(status='pending_approval').count(),link('procedure_list'),category='Documents')
    capa=visible_capa(user).filter(archived=False)
    add('capa_overdue','Overdue corrective actions',capa.filter(target_close_date__lt=today).exclude(status='closed').count(),link('ei_capa_list')+'?overdue=1','urgent','CAPA')
    add('capa_review','CAPA closure approvals',capa.filter(status='submitted',reviewer=user).exclude(Q(created_by=user)|Q(owner__user=user)|Q(submitted_by=user)).count(),link('ei_capa_list')+'?status=submitted',category='CAPA')
    add('capa_open','Open corrective actions',capa.filter(status='open',owner__user=user).count(),link('ei_capa_list')+'?status=open',category='CAPA')
    add('capa_reverted','Returned corrective actions',capa.filter(status='reverted',owner__user=user).count(),link('ei_capa_list')+'?status=reverted',category='CAPA')
    ranks={'urgent':0,'pending':1,'upcoming':2};items.sort(key=lambda x:(ranks[x['severity']],x['category'],x['title']))
    notifications=Notification.objects.filter(recipient=user,is_read=False)
    return {'attention_items':items,'attention_total':sum(x['count'] for x in items),'urgent_total':sum(x['count'] for x in items if x['severity']=='urgent'),
        'upcoming_total':sum(x['count'] for x in items if x['severity']=='upcoming'),'visible_jobs':jobs,'active_jobs':active,
        'notifications':notifications[:8],'unread_notification_count':notifications.count(),
        'recent_jobs':active.select_related('client').order_by('-created_at')[:6],
        'total_jobs':jobs.count(),'ongoing_jobs':active.count(),'completed_jobs':jobs.filter(Q(workflow_managed=True,progress_status='completed')|Q(workflow_managed=False,job_status__in=['completed','dispatched'])).count()}
