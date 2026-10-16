"""Apply additive E&I personnel migration and assert existing records are preserved."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import integrated_app
from django.core.management import call_command
from core.models import Personnel, Job, CalibrationLog, PersonnelEvidence, PersonnelCompetency, PersonnelAuthorization, Primary


def snapshot():
    return {
        'personnel':list(Personnel.objects.order_by('pk').values('id','user_id','name','position','qualifications','years_of_experience','employment_status','verification_token')),
        'jobs':list(Job.objects.order_by('pk').values('id','client_id','creator_id','job_status','progress_status','approval_state')),
        'logs':list(CalibrationLog.objects.order_by('pk').values('id','recorded_by_id','calibrated_by_id','reviewed_by_id','approved_by_id','status')),
        'evidence':list(PersonnelEvidence.objects.order_by('pk').values('id','personnel_id','created_by_id','kind','details','file')),
        'competency':list(PersonnelCompetency.objects.order_by('pk').values('id','personnel_id','scope_id','result','assessed_on','expires_on')),
        'authorization':list(PersonnelAuthorization.objects.order_by('pk').values('id','personnel_id','scope_id','activity','effective_from','expires_on','revoked_at','version')),
        'equipment':list(Primary.objects.order_by('pk').values('id','name','serial_no','scope_id','certificate_no','calibration_frequency','last_calibrated','calibration_due_date','standard_uncertainty','status')),
    }


before=snapshot()
call_command('makemigrations','core',check=True,dry_run=True)
call_command('migrate',interactive=False)
after=snapshot()
if before != after:
    raise RuntimeError('Existing E&I record preservation check failed. Inspect backup before proceeding.')
print('Existing record preservation verified:',{key:len(value) for key,value in before.items()})
