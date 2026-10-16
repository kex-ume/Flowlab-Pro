from django.db import migrations


NEW_PERMISSIONS = [
    ('create_waybills', 'Create Waybills', 'Can create incoming and outgoing waybills'),
    ('create_jobs', 'Create Jobs', 'Can create new job records'),
    ('edit_jobs', 'Edit Jobs', 'Can edit existing job records'),
    ('record_environment', 'Record Environment', 'Can record environmental conditions'),
    ('perform_pre_calibration', 'Perform Pre-Calibration', 'Can create pre-calibration logs'),
    ('manage_roles', 'Manage Roles', 'Can create, edit, and delete roles'),
]

ROLE_PERMISSION_MAP = {
    'Personnel': ['create_jobs', 'edit_jobs', 'record_environment', 'perform_pre_calibration'],
    'Lab Lead': ['create_waybills', 'create_jobs', 'edit_jobs', 'record_environment',
                 'perform_pre_calibration', 'manage_roles'],
    'Manager': ['create_waybills', 'create_jobs', 'edit_jobs', 'record_environment',
                'perform_pre_calibration', 'manage_roles'],
}


def add_missing_permissions(apps, schema_editor):
    Permission = apps.get_model('core', 'Permission')
    Role = apps.get_model('core', 'Role')

    perm_map = {}
    for codename, name, desc in NEW_PERMISSIONS:
        perm, _ = Permission.objects.get_or_create(
            codename=codename,
            defaults={'name': name, 'description': desc}
        )
        perm_map[codename] = perm

    for role_name, codenames in ROLE_PERMISSION_MAP.items():
        try:
            role = Role.objects.get(name=role_name)
            for codename in codenames:
                if codename in perm_map:
                    role.permissions.add(perm_map[codename])
        except Role.DoesNotExist:
            pass


def reverse_migration(apps, schema_editor):
    Permission = apps.get_model('core', 'Permission')
    codenames = [p[0] for p in NEW_PERMISSIONS]
    Permission.objects.filter(codename__in=codenames).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_client_status_alter_notification_notification_type'),
    ]

    operations = [
        migrations.RunPython(add_missing_permissions, reverse_migration),
    ]
