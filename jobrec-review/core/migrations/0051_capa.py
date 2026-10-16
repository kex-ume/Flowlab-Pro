from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion as deletion
import core.private_storage


def actor_fields():
    return [('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('actor_name',models.CharField(max_length=200)),('created_at',models.DateTimeField(auto_now_add=True)),('created_by',models.ForeignKey(on_delete=deletion.PROTECT,related_name='+',to=settings.AUTH_USER_MODEL))]


class Migration(migrations.Migration):
    dependencies=[('core','0050_personnel_review_notification'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(name='CAPARecord',fields=actor_fields()+[
            ('ncr_number',models.CharField(max_length=60,unique=True)),('title',models.CharField(max_length=200)),('source',models.CharField(max_length=100)),('clause_reference',models.CharField(max_length=100,blank=True)),('description',models.TextField()),('owner',models.ForeignKey(on_delete=deletion.PROTECT,related_name='corrective_actions',to='core.personnel')),('job',models.ForeignKey(on_delete=deletion.PROTECT,null=True,blank=True,to='core.job')),('issued_date',models.DateField()),('target_close_date',models.DateField()),('immediate_correction',models.TextField(blank=True)),('root_cause',models.TextField(blank=True)),('corrective_action',models.TextField(blank=True)),('effectiveness',models.TextField(blank=True)),('status',models.CharField(max_length=15,default='open',choices=[('open','Open'),('submitted','Closure Review'),('reverted','Reverted'),('closed','Closed')])),('reviewer',models.ForeignKey(null=True,on_delete=deletion.PROTECT,related_name='+',to=settings.AUTH_USER_MODEL)),('submitted_by',models.ForeignKey(null=True,on_delete=deletion.PROTECT,related_name='+',to=settings.AUTH_USER_MODEL)),('submitted_at',models.DateTimeField(null=True)),('approved_by',models.ForeignKey(null=True,on_delete=deletion.PROTECT,related_name='+',to=settings.AUTH_USER_MODEL)),('closed_at',models.DateTimeField(null=True)),('review_comment',models.TextField(blank=True)),('version',models.PositiveIntegerField(default=0)),('archived',models.BooleanField(default=False))],options={'abstract':False}),
        migrations.CreateModel(name='CAPADocument',fields=actor_fields()+[('record',models.ForeignKey(on_delete=deletion.PROTECT,related_name='documents',to='core.caparecord')),('kind',models.CharField(max_length=15,choices=[('issued','Issued NCR'),('closeout','Close-out report'),('supporting','Supporting evidence')])),('file',models.FileField(storage=core.private_storage.private_storage,upload_to=core.private_storage.private_upload)),('original_name',models.CharField(max_length=200)),('mime_type',models.CharField(max_length=100))],options={'abstract':False}),
    ]
