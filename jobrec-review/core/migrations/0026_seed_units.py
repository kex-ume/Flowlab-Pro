from django.db import migrations

UNITS_BY_SCOPE = {
    'General Calibration': [
        ('g', 'g'), ('kg', 'kg'), ('mg', 'mg'),
        ('mL', 'mL'), ('L', 'L'), ('µL', 'µL'),
        ('N', 'N'), ('V', 'V'), ('mA', 'mA'), ('A', 'A'),
        ('Ω', 'Ω'), ('kHz', 'kHz'), ('MHz', 'MHz'), ('GHz', 'GHz'),
        ('Hz', 'Hz'), ('m', 'm'), ('mm', 'mm'), ('µm', 'µm'),
        ('N·m', 'N·m'), ('s', 's'), ('min', 'min'),
    ],
    'Pressure Calibration': [
        ('Pa', 'Pa'), ('kPa', 'kPa'), ('MPa', 'MPa'),
        ('bar', 'bar'), ('mbar', 'mbar'), ('psi', 'psi'),
        ('kgf/cm²', 'kgf/cm²'), ('mmHg', 'mmHg'), ('inH₂O', 'inH₂O'),
        ('Torr', 'Torr'), ('atm', 'atm'),
    ],
    'Temperature Calibration': [
        ('°C', '°C'), ('°F', '°F'), ('K', 'K'), ('°R', '°R'),
    ],
}


def seed_units(apps, schema_editor):
    CalibrationType = apps.get_model('core', 'CalibrationType')
    Unit = apps.get_model('core', 'Unit')
    for scope_name, units in UNITS_BY_SCOPE.items():
        scope = CalibrationType.objects.filter(name=scope_name).first()
        if not scope:
            continue
        for name, symbol in units:
            Unit.objects.get_or_create(symbol=symbol, scope_id=scope.pk, defaults={'name': name})


def unseed_units(apps, schema_editor):
    Unit = apps.get_model('core', 'Unit')
    for units in UNITS_BY_SCOPE.values():
        for _name, symbol in units:
            Unit.objects.filter(symbol=symbol).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_remove_job_outgoing_waybill_remove_job_scope_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_units, unseed_units),
    ]