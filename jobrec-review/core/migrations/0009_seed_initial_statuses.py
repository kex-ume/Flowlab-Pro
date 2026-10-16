from django.db import migrations


def update_waybill_item_statuses(apps, schema_editor):
    WaybillItem = apps.get_model('core', 'WaybillItem')
    PreCalibrationLog = apps.get_model('core', 'PreCalibrationLog')
    for item in WaybillItem.objects.all():
        if item.calibration_logs.exists():
            logs = item.calibration_logs.all()
            if logs.filter(status='approved').exists():
                item.status = 'completed'
            else:
                item.status = 'result_pending'
        elif PreCalibrationLog.objects.filter(waybill_item=item).exists():
            item.status = 'cal_pending'
        else:
            item.status = 'pre_cal_pending'
        item.save()


def update_calibration_log_statuses(apps, schema_editor):
    CalibrationLog = apps.get_model('core', 'CalibrationLog')
    CalibrationLog.objects.filter(status='draft').update(status='pending_review')


def delete_staff_accounts(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    User.objects.filter(
        username__in=['staff1', 'staff2', 'staff3', 'staff4'],
        is_staff=True,
        personnel_profile__isnull=True,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0008_calibrationlog_approved_at_and_more'),
    ]

    operations = [
        migrations.RunPython(update_waybill_item_statuses),
        migrations.RunPython(update_calibration_log_statuses),
        migrations.RunPython(delete_staff_accounts),
    ]
