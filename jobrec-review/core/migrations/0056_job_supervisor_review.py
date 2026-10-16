from django.conf import settings
from django.db import migrations,models
import django.db.models.deletion as deletion


class Migration(migrations.Migration):
    dependencies=[('core','0055_ei_workflow_authority'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[migrations.CreateModel(name='JobReview',fields=[
        ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
        ('actor_name',models.CharField(max_length=200)),('created_at',models.DateTimeField(auto_now_add=True)),
        ('branch',models.CharField(max_length=25)),('comment',models.TextField(blank=True)),
        ('created_by',models.ForeignKey(on_delete=deletion.PROTECT,related_name='+',to=settings.AUTH_USER_MODEL)),
        ('proposed_assignee',models.ForeignKey(on_delete=deletion.PROTECT,to='core.personnel')),
        ('submission',models.OneToOneField(on_delete=deletion.PROTECT,related_name='review',to='core.jobsubmission')),
    ],options={'abstract':False})]
