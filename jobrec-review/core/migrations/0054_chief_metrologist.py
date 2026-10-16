from django.db import migrations


def seed_chief(apps, schema_editor):
    Role = apps.get_model('core','Role')
    Permission = apps.get_model('core','Permission')
    role, _ = Role.objects.get_or_create(name='Chief Metrologist',defaults={
        'description':'Laboratory personnel registration and record oversight; technical authorization remains explicitly approved.'})
    for code in ('manage_personnel','view_jobs','view_equipment','view_waybills','record_environment'):
        permission, _ = Permission.objects.get_or_create(codename=code,defaults={'name':code.replace('_',' ').title()})
        role.permissions.add(permission)
    # Preserve legacy Chief records and their existing grants; add registration only.
    registration=Permission.objects.get(codename='manage_personnel')
    for legacy in Role.objects.filter(name__in=('Chief','Chief Meteorologist')):
        legacy.permissions.add(registration)


class Migration(migrations.Migration):
    dependencies=[('core','0053_integrated_administration')]
    operations=[migrations.RunPython(seed_chief,migrations.RunPython.noop)]
