"""E&I NCR/CAPA lifecycle, separate from Flask CAPA records."""
from pathlib import Path
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from . import ei_workflow as service
from .ei_views import api, payload, office_preview
from .models import CAPARecord, CAPADocument, Notification, WorkflowAudit


def visible(user):
    rows=CAPARecord.objects.select_related('owner__user','job','created_by','reviewer')
    return rows if service.supervisor(user) else rows.filter(Q(created_by=user)|Q(owner__user=user)|Q(reviewer=user))


def require_edit(user,record):
    if not (service.supervisor(user) or record.created_by_id==user.pk or record.owner.user_id==user.pk):
        raise PermissionDenied('Only the NCR owner, originator or supervisor can maintain this CAPA.')


def snapshot(record):
    return {name:str(getattr(record,name)) for name in ('ncr_number','status','title','source','description','owner_id','target_close_date','immediate_correction','root_cause','corrective_action','effectiveness','version','archived','review_comment','approved_by_id','closed_at')}


def notify(record,users,message):
    for user_id in set(x for x in users if x):
        Notification.objects.create(recipient_id=user_id,notification_type='job_updated',message=f'{record.ncr_number}: {message}',link=reverse('ei_capa_detail',args=[record.pk]))


@login_required
def register(request):
    rows=visible(request.user).filter(archived=request.GET.get('archived')=='1')
    search=request.GET.get('search','').strip()
    if search: rows=rows.filter(Q(ncr_number__icontains=search)|Q(title__icontains=search)|Q(owner__name__icontains=search))
    status=request.GET.get('status','')
    if status in ('open','submitted','reverted','closed'): rows=rows.filter(status=status)
    if request.GET.get('overdue')=='1': rows=rows.filter(target_close_date__lt=timezone.localdate()).exclude(status='closed')
    return render(request,'core/capa/list.html',{'records':rows.order_by('target_close_date','pk'),'people':service.active_personnel(),'search':search,'status':status,'jobs':service.visible_jobs(request.user) if service.has_perm(request.user,'view_jobs') else [],'today':timezone.localdate()})


@login_required
def detail(request,pk):
    record=get_object_or_404(visible(request.user),pk=pk)
    return render(request,'core/capa/detail.html',{'record':record,'may_edit':service.supervisor(request.user) or record.created_by_id==request.user.pk or record.owner.user_id==request.user.pk,'may_review':service.lab_authority(request.user) and request.user.pk not in (record.created_by_id,record.owner.user_id,record.submitted_by_id),'may_archive':service.supervisor(request.user),'reviewers':[p for p in service.active_personnel() if service.lab_authority(p.user)],'history':WorkflowAudit.objects.filter(after__capa=pk),'people':service.active_personnel()})


def upload(request,record,kind,field):
    incoming=request.FILES.get(field)
    if not incoming:return
    mime,_=service.sniff_upload(incoming)
    doc=CAPADocument(record=record,kind=kind,mime_type=mime,original_name=Path(incoming.name.replace('\\','/')).name[:200],**service.actor_fields(request.user))
    doc.file.save(doc.original_name,incoming,save=False)
    request._ei_pending_files.append((doc.file.storage,doc.file.name));doc.save()


@api()
def action(request,action,pk=None):
    if not pk and action!='save':raise ValidationError('Create the NCR before this action.')
    data=payload(request)
    with transaction.atomic():
        record=get_object_or_404(visible(request.user).select_for_update(),pk=pk) if pk else CAPARecord(**service.actor_fields(request.user))
        before=snapshot(record) if pk else {}
        if pk and int(data.get('version',-1)) != record.version: raise service.Conflict('This CAPA was changed elsewhere. Reload the current record.')
        if record.archived and action not in ('restore','archive'):raise ValidationError('Restore the archived record before modifying it.')
        if action in ('archive','restore'):
            if not service.supervisor(request.user):raise PermissionDenied('Only supervisors can archive or restore CAPA records.')
            record.archived=action=='archive'
        elif action in ('approve','revert'):
            if record.status != 'submitted' or not service.lab_authority(request.user) or request.user.pk in (record.created_by_id,record.owner.user_id,record.submitted_by_id):
                raise PermissionDenied('An independent Chief or Administrator must decide closure.')
            comment=str(data.get('comment','')).strip()
            if action=='revert' and not comment:raise ValidationError('A reversion comment is required.')
            record.review_comment=comment;record.status='closed' if action=='approve' else 'reverted'
            if action=='approve': record.approved_by=request.user;record.closed_at=timezone.now()
            notify(record,[record.created_by_id,record.owner.user_id],f'Closure {record.status}. {comment}')
        else:
            if pk:require_edit(request.user,record)
            if record.archived or record.status not in ('open','reverted'):raise ValidationError('Submitted or closed CAPA records are view-only.')
            if action=='save':
                if not pk:
                    record.ncr_number=str(data.get('ncr_number','')).strip().upper()
                    if not record.ncr_number or len(record.ncr_number)>60:raise ValidationError('A unique NCR number of up to 60 characters is required.')
                    record.title=str(data.get('title','')).strip()[:200];record.source=str(data.get('source','')).strip()[:100];record.description=str(data.get('description','')).strip()
                    if not all([record.title,record.source,record.description]):raise ValidationError('Title, source and nonconformity description are required.')
                    record.clause_reference=str(data.get('clause_reference',''))[:100]
                    record.issued_date=service.parse_date(data.get('issued_date'),'Issued date',True)
                    if record.issued_date>timezone.localdate():raise ValidationError('Issued date cannot be in the future.')
                    if data.get('job'):
                        record.job=get_object_or_404(service.visible_jobs(request.user),pk=data['job']);service.require_job_read(request.user,record.job)
                record.owner=get_object_or_404(service.active_personnel(),pk=data.get('owner'))
                record.target_close_date=service.parse_date(data.get('target_close_date'),'Target close-out date',True)
                if record.target_close_date<record.issued_date:raise ValidationError('Target close-out date cannot precede issue.')
                for field in ('immediate_correction','root_cause','corrective_action','effectiveness'): setattr(record,field,str(data.get(field,getattr(record,field))).strip())
                record.save();upload(request,record,'issued','issued_ncr');upload(request,record,'closeout','closeout_report');upload(request,record,'supporting','supporting')
                if not record.documents.filter(kind='issued').exists():raise ValidationError('Upload the issued NCR before saving.')
            elif action=='submit':
                if not all([record.immediate_correction,record.root_cause,record.corrective_action,record.effectiveness]) or not record.documents.filter(kind='closeout').exists():
                    raise ValidationError('Correction, root cause, corrective action, effectiveness verification and close-out report are required.')
                reviewer=get_object_or_404(service.active_personnel(),pk=data.get('reviewer'))
                if not service.lab_authority(reviewer.user) or reviewer.user_id in (request.user.pk,record.created_by_id,record.owner.user_id):raise ValidationError('Choose an independent Chief or Administrator for closure approval.')
                record.reviewer=reviewer.user;record.submitted_by=request.user;record.submitted_at=timezone.now();record.status='submitted'
                notify(record,[reviewer.user_id],'Closure review requires attention.')
            else:raise ValidationError('Unknown CAPA action.')
        record.version+=1;record.save()
        service.audit(request.user,record.job,'capa_'+action,before=before,after={'capa':record.pk,**snapshot(record)})
    return {'id':record.pk,'url':reverse('ei_capa_detail',args=[record.pk])}


@login_required
def document(request,pk):
    doc=get_object_or_404(CAPADocument,pk=pk)
    get_object_or_404(visible(request.user),pk=doc.record_id)
    if Path(doc.original_name).suffix.lower() in ('.xlsx','.docx') and request.GET.get('download')!='1':return office_preview(request,doc.file,doc.original_name,reverse('ei_capa_document',args=[doc.pk]))
    response=FileResponse(doc.file.open('rb'),content_type=doc.mime_type,filename=doc.original_name,as_attachment=request.GET.get('download')=='1')
    response['X-Content-Type-Options']='nosniff';response['Content-Security-Policy']="default-src 'none'; sandbox"
    return response
