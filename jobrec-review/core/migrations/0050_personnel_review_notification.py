from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies=[('core','0049_personnel_records')]
    operations=[migrations.AlterField('notification','notification_type',models.CharField(max_length=30,default='repair_complete',choices=[
        ('personnel_review','Personnel Record Review'),('repair_approved','Repair Approved'),('repair_complete','Repair Completed'),('dispatch_approved','Dispatch Approved'),('new_client_pending','New Client Pending Info'),('new_job_created','New Job Created'),('job_updated','Job Updated'),('job_overdue','Job Overdue'),('primary_due_reminder','Primary Due Recalibration'),('pending_review','Calibration Log Pending Review'),('pending_approval','Calibration Log Pending Approval'),('pending_qhse','Calibration Log Pending QHSE Approval'),('log_approved','Calibration Log Approved'),('log_rejected','Calibration Log Rejected'),('environment_reminder','Environment Recording Reminder'),('environment_recorded','Environment Recorded'),('procedure_assigned','Calibration Procedure Assigned'),('procedure_submitted','Calibration Procedure Submitted'),('procedure_approved','Calibration Procedure Approved'),('procedure_rejected','Calibration Procedure Rejected')]))]
