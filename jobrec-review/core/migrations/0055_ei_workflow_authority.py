from django.db import migrations


def roles(apps,schema_editor):
    Role=apps.get_model('core','Role'); Permission=apps.get_model('core','Permission')
    supervisor,_=Role.objects.get_or_create(name='Supervisor',defaults={'description':'E&I job coordination and technical review; final approval is Chief / Administrator.'})
    codes=('view_jobs','view_waybills','view_equipment','create_jobs','edit_jobs','create_waybills',
        'create_clients','manage_ei_jobs','manage_personnel','review_calibration','reject_calibration','review_pre_calibration',
        'record_environment','verify_personnel_records','assess_personnel_competency')
    for code in codes:
        permission,_=Permission.objects.get_or_create(codename=code,defaults={'name':code.replace('_',' ').title()})
        supervisor.permissions.add(permission)
    for role in Role.objects.filter(name__in=('Chief','Chief Meteorologist','Chief Metrologist','Administrator','HOD')):
        role.permissions.add(*Permission.objects.all())


class Migration(migrations.Migration):
    dependencies=[('core','0054_chief_metrologist')]
    operations=[migrations.RunPython(roles,migrations.RunPython.noop)]
