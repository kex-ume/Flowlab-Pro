from django.db import migrations


ROLES = {
    'personnel': {'name': 'Personnel', 'description': 'Standard personnel'},
    'lab_lead': {'name': 'Lab Lead', 'description': 'Laboratory lead who can review and manage calibration processes'},
    'manager': {'name': 'Manager', 'description': 'Manager who can approve calibration logs and manage the system'},
}

ALL_PERMISSIONS = [
    ('create_clients', 'Create Clients', 'Can create new client records'),
    ('manage_personnel', 'Manage Personnel', 'Can create, edit, and delete personnel records'),
    ('view_settings', 'View & Edit Settings', 'Can access the settings page'),
    ('view_jobs', 'View Jobs', 'Can view jobs list and details'),
    ('view_waybills', 'View Waybills', 'Can view waybills list and details'),
    ('review_calibration', 'Review Calibration Logs', 'Can review calibration logs (send to approval)'),
    ('approve_calibration', 'Approve Calibration Logs', 'Can approve calibration logs'),
    ('reject_calibration', 'Reject Calibration Logs', 'Can reject calibration logs'),
    ('edit_calibration', 'Edit Calibration Logs', 'Can edit calibration logs'),
    ('review_pre_calibration', 'Review Pre-Calibration', 'Can review pre-calibration logs'),
    ('repair_equipment', 'Repair Equipment', 'Can mark equipment as repaired'),
    ('dispatch_equipment', 'Dispatch Equipment', 'Can dispatch equipment from pre-cal failure'),
    ('view_equipment', 'View Equipment', 'Can view the equipment page'),
    ('create_waybills', 'Create Waybills', 'Can create incoming and outgoing waybills'),
    ('create_jobs', 'Create Jobs', 'Can create new job records'),
    ('edit_jobs', 'Edit Jobs', 'Can edit existing job records'),
    ('record_environment', 'Record Environment', 'Can record environmental conditions'),
    ('perform_pre_calibration', 'Perform Pre-Calibration', 'Can create pre-calibration logs'),
    ('manage_roles', 'Manage Roles', 'Can create, edit, and delete roles'),
]

ROLE_PERMISSIONS = {
    'personnel': ['view_jobs', 'view_waybills', 'view_equipment', 'edit_calibration',
                  'create_jobs', 'edit_jobs', 'record_environment', 'perform_pre_calibration'],
    'lab_lead': ['view_jobs', 'view_waybills', 'view_equipment', 'edit_calibration',
                 'review_calibration', 'reject_calibration', 'review_pre_calibration',
                 'repair_equipment', 'dispatch_equipment',
                 'create_waybills', 'create_jobs', 'edit_jobs', 'record_environment',
                 'perform_pre_calibration', 'manage_roles'],
    'manager': ['view_jobs', 'view_waybills', 'view_equipment', 'edit_calibration',
                'review_calibration', 'approve_calibration', 'reject_calibration',
                'review_pre_calibration', 'repair_equipment', 'dispatch_equipment',
                'create_clients', 'manage_personnel', 'view_settings',
                'create_waybills', 'create_jobs', 'edit_jobs', 'record_environment',
                'perform_pre_calibration', 'manage_roles'],
}

OLD_ROLE_MAP = {
    'personnel': 'personnel',
    'lab_lead': 'lab_lead',
    'manager': 'manager',
}


def seed_roles_and_permissions(apps, schema_editor):
    Permission = apps.get_model('core', 'Permission')
    Role = apps.get_model('core', 'Role')
    Personnel = apps.get_model('core', 'Personnel')

    # Create permissions
    perm_map = {}
    for codename, name, desc in ALL_PERMISSIONS:
        perm, _ = Permission.objects.get_or_create(
            codename=codename,
            defaults={'name': name, 'description': desc}
        )
        perm_map[codename] = perm

    # Create roles and assign permissions
    for slug, data in ROLES.items():
        role, _ = Role.objects.get_or_create(
            name=data['name'],
            defaults={'description': data['description']}
        )
        permissions_for_role = [perm_map[c] for c in ROLE_PERMISSIONS.get(slug, []) if c in perm_map]
        role.permissions.add(*permissions_for_role)

    # Map old role values to new FK
    for slug, role_name in OLD_ROLE_MAP.items():
        try:
            role = Role.objects.get(name=ROLES[role_name]['name'])
            Personnel.objects.filter(role=slug).update(role_new=role)
        except (Role.DoesNotExist, KeyError):
            pass


def reverse_seed(apps, schema_editor):
    Permission = apps.get_model('core', 'Permission')
    Role = apps.get_model('core', 'Role')
    Role.objects.all().delete()
    Permission.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_permission_remove_personnel_job_title_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_roles_and_permissions, reverse_seed),
    ]
