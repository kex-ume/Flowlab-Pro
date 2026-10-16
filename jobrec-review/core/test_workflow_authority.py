from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils import timezone
from .models import Personnel,Role,PersonnelAuthorization,Notification,WorkflowAudit
from .auth_utils import has_perm
from . import ei_workflow as service


class WorkflowAuthorityTests(TestCase):
    def setUp(self):
        from .tests import IntegratedEIWorkflowTests
        self.fx=IntegratedEIWorkflowTests(); self.fx.setUp(); self.addCleanup(self.fx.doCleanups)
        self.supervisor=User.objects.create_user('routine-supervisor',password='Test-Only-981!')
        self.person=Personnel.objects.create(user=self.supervisor,name='Routine Supervisor',role=Role.objects.get(name='Supervisor'),qualifications='',years_of_experience=1)
        PersonnelAuthorization.objects.create(personnel=self.person,activity='review',scope=self.fx.scope,effective_from=timezone.localdate(),**service.actor_fields(self.fx.lead))

    def calculated(self):
        job=self.fx.approved_job()
        record=service.start_record(self.fx.user,job.uuts.first(),'calibration')
        record=service.save_record(self.fx.user,record,{'reading':'2.4','runs':[{'reference':'2.5'}],
            'reference_standards':[self.fx.standard.pk]},0)
        return record

    def test_review_goes_to_supervisor_and_approval_to_chief(self):
        record=self.calculated()
        service.transition_record(self.fx.user,record,'submit')
        self.assertTrue(Notification.objects.filter(recipient=self.supervisor,message__contains=f'record {record.pk}: submitted').exists())
        service.transition_record(self.supervisor,record,'review')
        self.assertTrue(Notification.objects.filter(recipient=self.fx.lead,message__contains=f'record {record.pk}: reviewed').exists())
        self.fx.lead_person.authorizations.all().delete()
        self.fx.lead_person.competencies.all().delete()
        service.transition_record(self.fx.lead,record,'approve')
        record.refresh_from_db();self.assertEqual(record.status,'approved')
        self.assertEqual(record.reviewed_by_id,self.supervisor.pk)
        self.assertEqual(record.approved_by_id,self.fx.lead.pk)
        self.assertTrue(WorkflowAudit.objects.filter(event='record_approve',after__authority_basis='Chief/Admin role').exists())

    def test_supervisor_cannot_complete_final_approval(self):
        record=self.calculated();service.transition_record(self.fx.user,record,'submit');service.transition_record(self.supervisor,record,'review')
        self.assertFalse(has_perm(self.supervisor,'approve_calibration'))
        with self.assertRaises(PermissionDenied):service.transition_record(self.supervisor,record,'approve')

    def test_job_review_does_not_assign_or_allow_early_commencement(self):
        from .models import JobReview
        job=self.fx.draft();service.submit_job(self.fx.user,job)
        service.decide_job(self.supervisor,job,'sender')
        job.refresh_from_db()
        self.assertEqual(job.approval_state,'awaiting');self.assertFalse(job.assigned_to.exists())
        self.assertEqual(JobReview.objects.get(submission=job.submissions.first()).created_by_id,self.supervisor.pk)
        with self.assertRaises(PermissionDenied):service.commence_job(self.fx.user,job)
        with self.assertRaises(PermissionDenied):service.decide_job(self.supervisor,job,'sender')
        service.decide_job(self.fx.lead,job,'sender');job.refresh_from_db()
        self.assertEqual(job.approval_state,'approved');self.assertEqual(job.primary_assignee_id,self.fx.person.pk)

    def test_job_reviewer_cannot_also_be_final_approver(self):
        job=self.fx.draft();service.submit_job(self.fx.user,job)
        service.decide_job(self.fx.lead,job,'sender')
        with self.assertRaises(PermissionDenied):service.decide_job(self.fx.lead,job,'sender')

    def test_job_review_ui_shows_correct_stage_and_actions(self):
        job=self.fx.draft();service.submit_job(self.fx.user,job)
        self.client.force_login(self.supervisor)
        response=self.client.get(reverse('job_detail',args=[job.pk]))
        self.assertContains(response,'Submit Review to Chief')
        service.decide_job(self.supervisor,job,'sender')
        response=self.client.get(reverse('job_detail',args=[job.pk]))
        self.assertContains(response,'Awaiting Chief / Admin approval')
        self.assertNotContains(response,'Record Chief Approval')
        self.client.force_login(self.fx.lead)
        self.assertContains(self.client.get(reverse('job_detail',args=[job.pk])),'Record Chief Approval')

    def test_chief_access_does_not_allow_own_record_approval(self):
        record=self.calculated();service.transition_record(self.fx.user,record,'submit');service.transition_record(self.supervisor,record,'review');service.transition_record(self.fx.lead,record,'approve')
        revised=service.amend_record(self.fx.lead,record,'Correct retained input')
        service.transition_record(self.fx.lead,revised,'submit');service.transition_record(self.supervisor,revised,'review')
        with self.assertRaises(PermissionDenied):service.transition_record(self.fx.lead,revised,'approve')

    def test_ordinary_staff_api_permissions_and_personnel_privacy(self):
        self.client.force_login(self.fx.stranger)
        self.assertEqual(self.client.post(reverse('api:client-list'),{'name':'Forbidden Client'}).status_code,403)
        response=self.client.get(reverse('api:personnel-list'))
        self.assertEqual(response.status_code,200)
        rows=response.json().get('results',[])
        self.assertEqual({row['id'] for row in rows},{self.fx.stranger_person.pk})

    def test_busy_database_is_a_conflict_not_an_internal_error(self):
        from django.test import RequestFactory
        from django.db import OperationalError
        from .ei_views import api
        @api()
        def busy(request): raise OperationalError('database is locked')
        request=RequestFactory().post('/disposable-conflict-check/')
        request.user=self.fx.user
        response=busy(request)
        self.assertEqual(response.status_code,409)
        self.assertIn(b'not committed',response.content)

    def test_approved_signed_result_cannot_be_replaced(self):
        from .models import Waybill,WaybillItem,CalibrationLog
        from django.core.files.uploadedfile import SimpleUploadedFile
        bill=Waybill.objects.create(waybill_no='SIGNED-LOCK-TEST',waybill_type='incoming')
        item=WaybillItem.objects.create(waybill=bill,equipment_description='Test UUT',quantity=1,serial_no='SIGNED-TEST',scope=self.fx.scope)
        log=CalibrationLog.objects.create(waybill_item=item,scope=self.fx.scope,calibrated_at_date=timezone.localdate(),calibrated_by=self.fx.person,recorded_by=self.fx.user,status='approved',certificate='retained-original.pdf')
        self.client.force_login(self.fx.lead)
        response=self.client.post(reverse('api:calibrationlog-upload-certificate',args=[log.pk]),{'certificate':SimpleUploadedFile('replacement.pdf',b'%PDF-1.4\n%%EOF')})
        self.assertEqual(response.status_code,400)
        log.refresh_from_db();self.assertEqual(log.certificate.name,'retained-original.pdf')
