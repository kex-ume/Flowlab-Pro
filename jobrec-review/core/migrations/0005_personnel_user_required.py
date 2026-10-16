from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0004_location_remove_personnel_designation_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='personnel',
            name='user',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='personnel_profile',
                to='auth.user',
            ),
        ),
    ]
