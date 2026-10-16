from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def administrator_role(apps, schema_editor):
    Role = apps.get_model('core', 'Role')
    Permission = apps.get_model('core', 'Permission')
    role, _ = Role.objects.get_or_create(name='Administrator', defaults={'description':'Integrated account and record administration; no automatic technical authorization.'})
    for code in ('view_settings','manage_personnel','manage_ei_jobs','view_jobs','view_equipment','view_waybills','create_clients','administer_lab'):
        permission, _ = Permission.objects.get_or_create(codename=code, defaults={'name':code.replace('_',' ').title()})
        role.permissions.add(permission)


class Migration(migrations.Migration):
    dependencies = [('core','0052_equipment_programme'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='AdminAccountLink', fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('flowlab_user_id',models.PositiveIntegerField(unique=True)),
            ('enabled',models.BooleanField(default=True)),
            ('previous_role_id',models.PositiveIntegerField(null=True,blank=True)),
            ('updated_at',models.DateTimeField(auto_now=True)),
            ('user',models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,related_name='integrated_admin_link',to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name='AdministrativeArchive', fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('target_type',models.CharField(max_length=40)),('object_id',models.PositiveIntegerField()),
            ('previous_state',models.JSONField(default=dict)),('reason',models.TextField()),
            ('actor_name',models.CharField(max_length=200)),('archived_at',models.DateTimeField(auto_now_add=True)),
            ('restored_at',models.DateTimeField(null=True,blank=True)),
        ], options={'constraints':[models.UniqueConstraint(fields=('target_type','object_id'),name='ei_admin_archive_target')]}),
        migrations.AddField('job','administratively_archived',models.BooleanField(default=False)),
        migrations.AlterField('client','status',models.CharField(max_length=20,default='active',choices=[('active','Active'),('pending_info','Pending Info'),('inactive','Inactive')])),
        migrations.RunPython(administrator_role, migrations.RunPython.noop),
    ]
