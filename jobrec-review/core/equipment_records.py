"""E&I equipment record layout and calibration programme using existing Primary IDs."""
import calendar
from datetime import timedelta
from pathlib import Path
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404,render
from django.urls import reverse
from django.utils import timezone
from .auth_utils import has_perm
from . import ei_workflow as service
from .ei_views import api,payload,office_preview
from .models import Primary,EquipmentRecord,PersonnelReviewReminder,Personnel,Notification


def access(user):
    if not (has_perm(user,'view_equipment') or service.supervisor(user)):raise PermissionDenied('Equipment records require laboratory equipment access.')


def due_status(asset,today=None):
    today=today or timezone.localdate()
    if asset.status=='inactive':return 'Inactive'
    if not asset.include_programme:return 'Not in programme'
    if not asset.calibration_due_date:return 'Schedule missing'
    if asset.calibration_due_date<today:return 'Expired'
    if asset.calibration_due_date<=today+timedelta(days=30):return 'Due within 30 days'
    if asset.status=='pending_maintenance':return 'Maintenance required'
    return 'Active'


def add_months(day,months):
    index=day.year*12+day.month-1+months;year,month=divmod(index,12);month+=1
    return day.replace(year=year,month=month,day=min(day.day,calendar.monthrange(year,month)[1]))


@login_required
def register(request,programme=False):
    access(request.user);rows=Primary.objects.select_related('scope','unit').order_by('name')
    if programme:rows=rows.filter(include_programme=True).exclude(status='inactive')
    search=request.GET.get('search','').strip()
    if search:rows=rows.filter(Q(name__icontains=search)|Q(asset_number__icontains=search)|Q(serial_no__icontains=search)|Q(scope__name__icontains=search))
    assets=list(rows)
    for asset in assets:asset.programme_status=due_status(asset)
    status=request.GET.get('status','')
    if status:assets=[a for a in assets if a.programme_status==status]
    return render(request,'core/equipment/assets.html',{'assets':assets,'programme':programme,'search':search,'status':status,'statuses':['Active','Due within 30 days','Expired','Schedule missing','Maintenance required','Inactive','Not in programme'],'may_edit':has_perm(request.user,'approve_calibration') or service.supervisor(request.user)})


@login_required
def detail(request,pk):
    access(request.user);asset=get_object_or_404(Primary,pk=pk)
    tab=request.GET.get('tab','overview')
    if tab not in ('overview','calibration','maintenance','uncertainty','files'):tab='overview'
    records=asset.retained_records.select_related('created_by','approved_by').order_by('-performed_on','-pk')
    return render(request,'core/equipment/asset_detail.html',{'asset':asset,'records':records,'tab':tab,'programme_status':due_status(asset),'may_edit':has_perm(request.user,'approve_calibration') or service.supervisor(request.user),'may_review':service.lab_authority(request.user),'may_upload':has_perm(request.user,'edit_calibration') or service.supervisor(request.user)})


@api()
def record_action(request,pk,action,record_id=None):
    access(request.user);data=payload(request)
    with transaction.atomic():
        asset=get_object_or_404(Primary.objects.select_for_update(),pk=pk)
        if action=='add':
            if not(has_perm(request.user,'edit_calibration') or service.supervisor(request.user)):raise PermissionDenied('Equipment record entry is restricted.')
            kind=data.get('kind')
            if kind not in ('calibration','maintenance'):raise ValidationError('Choose calibration or maintenance.')
            performed=service.parse_date(data.get('performed_on'),'Performed date',True)
            if performed>timezone.localdate():raise ValidationError('Performed date cannot be in the future.')
            details={key:str(data.get(key,'')).strip() for key in ('provider','certificate_no','method','findings','work','expanded_uncertainty','uncertainty_unit','coverage_factor')}
            if not details['provider']:raise ValidationError('Provider / actual performer is required.')
            interval=int(data.get('interval_months',asset.calibration_frequency))
            if not 1<=interval<=1200:raise ValidationError('Calibration interval must be between 1 and 1200 months.')
            details['interval_months']=interval
            due=add_months(performed,interval) if kind=='calibration' else None
            if kind=='calibration' and not details['certificate_no']:raise ValidationError('Certificate number is required.')
            if kind=='maintenance' and not details['work']:raise ValidationError('Describe the maintenance work.')
            incoming=request.FILES.get('file')
            if not incoming:raise ValidationError('Upload the calibration certificate or maintenance report.')
            mime,_=service.sniff_upload(incoming)
            row=EquipmentRecord(equipment=asset,kind=kind,performed_on=performed,due_date=due,details=details,mime_type=mime,original_name=Path(incoming.name.replace('\\','/')).name[:200],**service.actor_fields(request.user))
            row.file.save(row.original_name,incoming,save=False);request._ei_pending_files.append((row.file.storage,row.file.name));row.save()
            for person in service.active_personnel():
                if service.supervisor(person.user) and person.user_id!=request.user.pk:Notification.objects.create(recipient=person.user,notification_type='pending_review',message=f'{asset.name}: {kind} record awaits verification.',link=reverse('ei_equipment_detail',args=[asset.pk])+'?tab='+kind)
        elif action in ('approve','reject'):
            row=get_object_or_404(EquipmentRecord.objects.select_for_update(),pk=record_id,equipment=asset)
            if not service.lab_authority(request.user) or row.created_by_id==request.user.pk:raise PermissionDenied('An independent Chief or Administrator must approve this record.')
            if row.status!='pending':raise ValidationError('Approved/rejected records are view-only; add a new retained record.')
            row.review_comment=str(data.get('comment','')).strip()
            if action=='reject' and not row.review_comment:raise ValidationError('Rejection reason is required.')
            row.status='approved' if action=='approve' else 'rejected';row.approved_by=request.user;row.approved_at=timezone.now();row.save()
            if action=='approve' and row.kind=='calibration' and (not asset.last_calibrated or row.performed_on>=asset.last_calibrated):
                before={'last_calibrated':str(asset.last_calibrated),'due_date':str(asset.calibration_due_date),'certificate_no':asset.certificate_no}
                asset.last_calibrated=row.performed_on;asset.calibration_due_date=row.due_date;asset.calibration_frequency=row.details['interval_months'];asset.certificate_no=row.details['certificate_no']
                if asset.status!='inactive':asset.status='active' if row.due_date>=timezone.localdate() else 'pending_maintenance'
                asset.save();service.audit(request.user,None,'equipment_programme_updated',before=before,after={'equipment':asset.pk,'record':row.pk,'due_date':str(row.due_date)})
            Notification.objects.create(recipient=row.created_by,notification_type='log_approved' if action=='approve' else 'log_rejected',message=f'{asset.name}: equipment record {row.status}.',link=reverse('ei_equipment_detail',args=[asset.pk])+'?tab='+row.kind)
        else:raise ValidationError('Unknown equipment record action.')
        service.audit(request.user,None,'equipment_record_'+action,after={'equipment':asset.pk,'record':row.pk,'status':row.status})
    return {'id':row.pk,'url':reverse('ei_equipment_detail',args=[asset.pk])+'?tab='+row.kind}


@login_required
def document(request,pk):
    access(request.user);row=get_object_or_404(EquipmentRecord,pk=pk)
    if Path(row.original_name).suffix.lower() in ('.xlsx','.docx') and request.GET.get('download')!='1':return office_preview(request,row.file,row.original_name,reverse('ei_equipment_file',args=[pk]))
    response=FileResponse(row.file.open('rb'),content_type=row.mime_type,filename=row.original_name,as_attachment=request.GET.get('download')=='1')
    response['X-Content-Type-Options']='nosniff';response['Content-Security-Policy']="default-src 'none'; sandbox";return response


def evaluate_programme(today=None):
    today=today or timezone.localdate()
    recipients=[p.user_id for p in service.active_personnel() if service.supervisor(p.user)]
    if not recipients:return
    for asset in Primary.objects.filter(include_programme=True,calibration_due_date__lte=today+timedelta(days=30)).exclude(status='inactive'):
        phase='expired' if asset.calibration_due_date<today else '30day'
        key=f'equipment:{asset.pk}:{asset.calibration_due_date}:{phase}'
        with transaction.atomic():
            _,created=PersonnelReviewReminder.objects.get_or_create(key=key)
            if created:
                for recipient in set(recipients):Notification.objects.create(recipient_id=recipient,notification_type='primary_due_reminder',message=f'{asset.asset_number or asset.pk} · {asset.name}: calibration {"expired" if phase=="expired" else "due within 30 days"}, due {asset.calibration_due_date}.',link=reverse('ei_calibration_programme'))
