from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_seed_roles_and_permissions'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='personnel',
            name='role',
        ),
        migrations.RenameField(
            model_name='personnel',
            old_name='role_new',
            new_name='role',
        ),
    ]
