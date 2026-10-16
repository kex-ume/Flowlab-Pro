from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0045_ei_controlled_workflow')]
    operations = [migrations.AddField(model_name='personnelauthorization', name='method_reference', field=models.CharField(blank=True, max_length=150))]
