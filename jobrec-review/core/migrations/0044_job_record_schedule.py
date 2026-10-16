from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0043_remove_calibrationlog_maximum_permissible_error')]

    operations = [
        migrations.AddField(model_name='job', name='job_type', field=models.CharField(choices=[('lab', 'Lab'), ('field', 'Field')], default='lab', max_length=10)),
        migrations.AddField(model_name='job', name='request_type', field=models.CharField(choices=[('calibration', 'Calibration'), ('repair', 'Repair'), ('calibration_repair', 'Calibration and Repair')], default='calibration', max_length=20)),
        migrations.AddField(model_name='job', name='received_started_date', field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name='job', name='scheduled_end_date', field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name='job', name='delay_remark', field=models.TextField(blank=True, default='')),
        migrations.AddField(model_name='job', name='delay_notified_on', field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name='job', name='record_status_override', field=models.CharField(blank=True, choices=[('scheduled', 'Scheduled'), ('pending', 'Pending'), ('ongoing', 'Ongoing')], default='', max_length=10)),
        migrations.AlterField(model_name='notification', name='notification_type', field=models.CharField(choices=[('repair_approved', 'Repair Approved'), ('repair_complete', 'Repair Completed'), ('dispatch_approved', 'Dispatch Approved'), ('new_client_pending', 'New Client Pending Info'), ('new_job_created', 'New Job Created'), ('job_updated', 'Job Updated'), ('job_overdue', 'Job Overdue'), ('primary_due_reminder', 'Primary Due Recalibration'), ('pending_review', 'Calibration Log Pending Review'), ('pending_approval', 'Calibration Log Pending Approval'), ('pending_qhse', 'Calibration Log Pending QHSE Approval'), ('log_approved', 'Calibration Log Approved'), ('log_rejected', 'Calibration Log Rejected'), ('environment_reminder', 'Environment Recording Reminder'), ('environment_recorded', 'Environment Recorded'), ('procedure_assigned', 'Calibration Procedure Assigned'), ('procedure_submitted', 'Calibration Procedure Submitted'), ('procedure_approved', 'Calibration Procedure Approved'), ('procedure_rejected', 'Calibration Procedure Rejected')], default='repair_complete', max_length=30)),
    ]
