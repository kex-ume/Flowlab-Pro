from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0047_separate_job_suggestions')]
    operations = [migrations.AddField(model_name='calibrationtype', name='active', field=models.BooleanField(default=True))]
