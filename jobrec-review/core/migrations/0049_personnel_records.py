from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion as deletion


def permissions(apps, schema_editor):
    Permission=apps.get_model('core','Permission')
    for code,name in [('verify_personnel_records','Verify personnel qualifications and experience'),('assess_personnel_competency','Designated personnel competency assessor'),('authorize_personnel','Approve, suspend and revoke technical personnel authorization')]:
        Permission.objects.get_or_create(codename=code,defaults={'name':name})


class Migration(migrations.Migration):
    dependencies=[('core','0048_scope_register'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(name='PersonnelReviewReminder',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('key',models.CharField(max_length=150,unique=True)),('created_at',models.DateTimeField(auto_now_add=True))]),
        migrations.AddField('personnelauthorization','suspended_at',models.DateTimeField(blank=True,null=True)),
        migrations.AddField('personnelauthorization','suspended_by',models.ForeignKey(blank=True,null=True,on_delete=deletion.PROTECT,related_name='+',to=settings.AUTH_USER_MODEL)),
        migrations.AddField('personnelauthorization','suspension_reason',models.TextField(blank=True)),
        migrations.AddField('personnelcompetency','previous',models.ForeignKey(blank=True,null=True,on_delete=deletion.PROTECT,related_name='revisions',to='core.personnelcompetency')),
        migrations.AddField('personnelevidence','expires_on',models.DateField(blank=True,null=True)),
        migrations.AddField('personnelevidence','previous',models.ForeignKey(blank=True,null=True,on_delete=deletion.PROTECT,related_name='revisions',to='core.personnelevidence')),
        migrations.AddField('personnelevidence','status',models.CharField(choices=[('pending','Pending Review'),('verified','Verified'),('superseded','Superseded')],default='pending',max_length=15)),
        migrations.AddField('personnelevidence','verified_at',models.DateTimeField(blank=True,null=True)),
        migrations.AddField('personnelevidence','verified_by',models.ForeignKey(blank=True,null=True,on_delete=deletion.PROTECT,related_name='+',to=settings.AUTH_USER_MODEL)),
        migrations.CreateModel(name='PersonnelCorrectionRequest',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('actor_name',models.CharField(max_length=200)),('created_at',models.DateTimeField(auto_now_add=True)),('details',models.TextField()),('status',models.CharField(default='pending',max_length=15)),('resolution',models.TextField(blank=True)),('resolved_at',models.DateTimeField(blank=True,null=True)),('created_by',models.ForeignKey(on_delete=deletion.PROTECT,related_name='+',to=settings.AUTH_USER_MODEL)),('personnel',models.ForeignKey(on_delete=deletion.PROTECT,related_name='correction_requests',to='core.personnel')),('resolved_by',models.ForeignKey(blank=True,null=True,on_delete=deletion.PROTECT,related_name='+',to=settings.AUTH_USER_MODEL))],options={'abstract':False}),
        migrations.RunPython(permissions,migrations.RunPython.noop),
    ]
