from django.conf import settings
from django.db import migrations,models
import django.db.models.deletion as deletion
import core.private_storage


def asset_ids(apps,schema_editor):
    for asset in apps.get_model('core','Primary').objects.filter(asset_number__isnull=True).iterator():
        asset.asset_number=f'EI-REF-{asset.pk:04d}';asset.save(update_fields=['asset_number'])


class Migration(migrations.Migration):
    dependencies=[('core','0051_capa'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.AddField('primary','asset_number',models.CharField(max_length=100,unique=True,null=True,blank=True)),
        migrations.AddField('primary','equipment_type',models.CharField(max_length=100,blank=True)),
        migrations.AddField('primary','include_programme',models.BooleanField(default=True)),
        migrations.AddField('primary','is_reference',models.BooleanField(default=True)),
        migrations.AddField('primary','laboratory_location',models.CharField(max_length=150,blank=True)),
        migrations.RunPython(asset_ids,migrations.RunPython.noop),
        migrations.CreateModel(name='EquipmentRecord',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('actor_name',models.CharField(max_length=200)),('created_at',models.DateTimeField(auto_now_add=True)),('created_by',models.ForeignKey(on_delete=deletion.PROTECT,related_name='+',to=settings.AUTH_USER_MODEL)),('equipment',models.ForeignKey(on_delete=deletion.PROTECT,related_name='retained_records',to='core.primary')),('kind',models.CharField(max_length=15,choices=[('calibration','Calibration'),('maintenance','Maintenance')])),('performed_on',models.DateField()),('due_date',models.DateField(null=True,blank=True)),('details',models.JSONField(default=dict)),('file',models.FileField(storage=core.private_storage.private_storage,upload_to=core.private_storage.private_upload)),('original_name',models.CharField(max_length=200)),('mime_type',models.CharField(max_length=100)),('status',models.CharField(max_length=12,default='pending',choices=[('pending','Pending Review'),('approved','Approved'),('rejected','Rejected')])),('approved_by',models.ForeignKey(null=True,on_delete=deletion.PROTECT,related_name='+',to=settings.AUTH_USER_MODEL)),('approved_at',models.DateTimeField(null=True)),('review_comment',models.TextField(blank=True))],options={'abstract':False}),
    ]
