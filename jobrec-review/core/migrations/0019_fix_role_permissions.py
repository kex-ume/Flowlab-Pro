from django.db import migrations


ROLE_PERMISSION_MAP = {
    'Calibration Technician': [
        'create_jobs', 'edit_jobs', 'record_environment', 'perform_pre_calibration',
    ],
    'Lab Admin': [
        'create_waybills', 'create_jobs', 'edit_jobs', 'record_environment',
        'perform_pre_calibration', 'manage_roles',
    ],
}


def fix_role_permissions(apps, schema_editor):
    Permission = apps.get_model('core', 'Permission')
    Role = apps.get_model('core', 'Role')

    perm_cache = {p.codename: p for p in Permission.objects.all()}

    for role_name, codenames in ROLE_PERMISSION_MAP.items():
        try:
            role = Role.objects.get(name=role_name)
            for codename in codenames:
                if codename in perm_cache:
                    role.permissions.add(perm_cache[codename])
        except Role.DoesNotExist:
            pass


def reverse_fix(apps, schema_editor):
    Permission = apps.get_model('core', 'Permission')
    Role = apps.get_model('core', 'Role')
    perm_cache = {p.codename: p for p in Permission.objects.all()}

    for role_name, codenames in ROLE_PERMISSION_MAP.items():
        try:
            role = Role.objects.get(name=role_name)
            for codename in codenames:
                if codename in perm_cache:
                    role.permissions.remove(perm_cache[codename])
        except Role.DoesNotExist:
            pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_add_missing_permissions'),
    ]

    operations = [
        migrations.RunPython(fix_role_permissions, reverse_fix),
    ]
