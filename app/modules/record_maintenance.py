"""Administrative soft archiving. Never removes calculations, files or audit rows."""
from django.utils import timezone

FLOW_TYPES = {
    'flow_environment':('flow_environment_readings','flow_environment','id','location','is_deleted'),
    'flow_environment_legacy':('environmental_records','environmental_record','id','record_date','is_deleted'),
    'flow_project':('projects','project','project_number','project_name','is_deleted'),
    'flow_job':('calibration_jobs','calibration_job','job_number','job_title','is_deleted'),
    'flow_equipment':('laboratory_equipment','equipment','asset_number','equipment_name','is_active'),
    'flow_document':('controlled_documents','controlled_document','document_number','title','is_deleted'),
    'flow_quality':('quality_records','quality_record','reference_number','title','is_deleted'),
    'flow_calibration':('calibration_history','calibration_history','id','calibration_date','is_deleted'),
    'flow_maintenance':('maintenance_history','maintenance_history','id','maintenance_type','is_deleted'),
    'flow_decision':('conformity_assessments','conformity_assessment','id','status','is_deleted'),
    'flow_cover':('generated_report_covers','generated_report_cover','id','output_format','is_deleted'),
    'flow_personnel_document':('personnel_documents','personnel_document','id','document_type','is_deleted'),
    'flow_uncertainty':('uncertainty_calculations','uncertainty_calculation','calculation_uid','method_name','status'),
    'flow_cmc':('cmc_revisions','cmc_revision','id','method_name','status'),
    'flow_capa':('capa_records','capa_record','id','title','is_deleted'),
    'flow_clause_evidence':('iso_clause_evidence','iso_clause_evidence','document_number','title','is_deleted'),
    'flow_service_request':('lab_service_requests','lab_service_request','request_number','original_filename','status'),
}
EI_TYPES = {
    'ei_job':('Job','administratively_archived',True,'description'),
    'ei_client':('Client','status','inactive','name'),
    'ei_equipment':('Primary','status','inactive','name'),
    'ei_personnel':('Personnel','employment_status','inactive','name'),
    'ei_capa':('CAPARecord','archived',True,'title'),
}
EI_RETAINED = {
    'ei_environment':('EnvironmentRecord','date'),
    'ei_waybill':('Waybill','waybill_no'),
    'ei_received':('WaybillItem','equipment_description'),
    'ei_uut':('JobUUT','name'),
    'ei_precal':('PreCalibrationLog','doc_no'),
    'ei_calibration':('CalibrationLog','certificate_no'),
    'ei_technical':('TechnicalRecord','id'),
    'ei_procedure':('CalibrationProcedure','title'),
    'ei_scope':('CalibrationType','name'),
    'ei_training':('PersonnelEvidence','id'),
    'ei_competency':('PersonnelCompetency','id'),
    'ei_authorization':('PersonnelAuthorization','id'),
    'ei_job_document':('JobDocument','id'),
    'ei_equipment_record':('EquipmentRecord','id'),
    'ei_capa_document':('CAPADocument','id'),
    'ei_template':('CalibrationLogTemplate','title'),
    'ei_budget':('UncertaintyBudget','title'),
}
LABELS = {'flow_project':'FlowLab Projects','flow_job':'FlowLab Jobs','flow_equipment':'FlowLab Lab Equipment','flow_document':'FlowLab Controlled Documents','flow_quality':'FlowLab Quality Records','ei_job':'E&I Jobs','ei_client':'E&I Clients','ei_equipment':'E&I Lab Equipment','ei_personnel':'E&I Personnel','ei_capa':'E&I CAPA / NCR'}
LABELS.update({key:key.replace('flow_','FlowLab ').replace('ei_','E&I ').replace('_',' ').title() for key in (*FLOW_TYPES,*EI_RETAINED) if key not in LABELS})


def listing(connection, kind):
    from core.models import AdministrativeArchive
    archived = {item.object_id:item for item in AdministrativeArchive.objects.filter(target_type=kind,restored_at__isnull=True)}
    if kind in FLOW_TYPES:
        table, _, number, label, flag = FLOW_TYPES[kind]
        # Field names come exclusively from this fixed internal catalog.
        rows = connection.execute(f'SELECT id,{number},{label},{flag} FROM {table} ORDER BY id DESC LIMIT 200').fetchall()
        return [{'id':row[0], 'label':str(row[1] or '')+' · '+str(row[2] or ''), 'archived':row[3]=='Deleted' if flag=='status' else not row[3] if flag=='is_active' else bool(row[3]), 'tracked':row[0] in archived} for row in rows]
    from django.apps import apps
    if kind in EI_RETAINED:
        model_name,label = EI_RETAINED[kind]
        model = apps.get_model('core',model_name)
        return [{'id':row.pk,'label':str(getattr(row,label)),'archived':row.pk in archived,'tracked':row.pk in archived} for row in model._base_manager.order_by('-pk')[:200]]
    model_name, flag, value, label = EI_TYPES[kind]
    model = apps.get_model('core',model_name)
    return [{'id':row.pk,'label':str(getattr(row,label)),'archived':getattr(row,flag)==value,'tracked':row.pk in archived} for row in model._base_manager.order_by('-pk')[:200]]


def change(connection, kind, pk, action, reason, actor):
    from core.models import AdministrativeArchive
    if kind not in LABELS or action not in {'archive','restore'}:
        raise ValueError('Unsupported record type or action.')
    if len(reason.strip()) < 5:
        raise ValueError('Enter a meaningful reason of at least five characters.')
    entry = AdministrativeArchive.objects.filter(target_type=kind,object_id=pk).first()
    display = f'{LABELS[kind]} #{pk}'
    if action=='restore' and (not entry or entry.restored_at):
        raise ValueError('Only records archived through this workspace can be restored here. Other FlowLab deletions remain in the Recycle Bin.')
    if kind in FLOW_TYPES:
        table, entity, number, label, flag = FLOW_TYPES[kind]
        row = connection.execute(f'SELECT {flag},{number},{label} FROM {table} WHERE id=?',(pk,)).fetchone()
        if not row:
            raise ValueError('Record was not found.')
        old = row[0]
        display = str(row[1] or '')+' · '+str(row[2] or '')
        archived_value = 'Deleted' if flag=='status' else 0 if flag=='is_active' else 1
        if action=='archive' and old==archived_value:
            raise ValueError('This record is already inactive or archived.')
        new = entry.previous_state['value'] if action=='restore' else archived_value
        connection.execute(f'UPDATE {table} SET {flag}=? WHERE id=?',(new,pk))
    elif kind in EI_RETAINED:
        from django.apps import apps
        model = apps.get_model('core',EI_RETAINED[kind][0])
        record = model._base_manager.select_for_update().filter(pk=pk).first()
        if not record:
            raise ValueError('Record was not found.')
        display = str(getattr(record,EI_RETAINED[kind][1]))
        if action=='archive' and entry and not entry.restored_at:
            raise ValueError('This record is already removed.')
        old = False
    else:
        from django.apps import apps
        model_name, flag, archived_value, _ = EI_TYPES[kind]
        model = apps.get_model('core',model_name)
        row = model._base_manager.select_for_update().filter(pk=pk).first()
        if not row:
            raise ValueError('Record was not found.')
        old = getattr(row,flag)
        display = str(getattr(row,EI_TYPES[kind][3]))
        if action=='archive' and old==archived_value:
            raise ValueError('This record is already inactive or archived.')
        setattr(row,flag,entry.previous_state['value'] if action=='restore' else archived_value)
        row.save(update_fields=[flag])
    if action=='archive':
        entry, _ = AdministrativeArchive.objects.update_or_create(target_type=kind,object_id=pk,defaults={'previous_state':{'value':old,'display':display},'reason':reason,'actor_name':actor,'restored_at':None,'archived_at':timezone.now()})
    else:
        entry.reason += '\nRestored: ' + reason
        entry.actor_name = actor
        entry.restored_at = timezone.now()
        entry.save(update_fields=['reason','actor_name','restored_at'])
