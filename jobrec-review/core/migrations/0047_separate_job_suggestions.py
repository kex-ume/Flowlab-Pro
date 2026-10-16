from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def separate_proposals(apps, schema_editor):
    Job = apps.get_model('core', 'Job')
    for job in Job.objects.filter(workflow_managed=True, approval_state__in=['draft','awaiting','reverted']):
        job.suggested_personnel.set(job.assigned_to.all())
        job.suggested_primary_id = job.primary_assignee_id
        job.primary_assignee_id = None
        job.assigned_to.clear()
        job.save(update_fields=['suggested_primary','primary_assignee'])


class Migration(migrations.Migration):
    dependencies = [('core','0046_personnel_method_authorization')]
    operations = [
        migrations.AddField(model_name='job', name='suggested_personnel', field=models.ManyToManyField(blank=True, related_name='suggested_ei_jobs', to='core.personnel')),
        migrations.AddField(model_name='job', name='suggested_primary', field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name='suggested_primary_ei_jobs',to='core.personnel')),
        migrations.AlterField(model_name='workflowaudit', name='created_by', field=models.ForeignKey(null=True,on_delete=django.db.models.deletion.PROTECT,related_name='+',to=settings.AUTH_USER_MODEL)),
        migrations.RunPython(separate_proposals,migrations.RunPython.noop),
    ]
