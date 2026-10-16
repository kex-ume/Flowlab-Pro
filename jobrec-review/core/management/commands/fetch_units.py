from django.core.management.base import BaseCommand

from core.unit_catalog import refresh_all_units


class Command(BaseCommand):
    help = 'Fetch units for each calibration scope from the online catalog (cached in the Unit table).'

    def handle(self, *args, **options):
        result = refresh_all_units()
        for scope_name, count in result.items():
            self.stdout.write(self.style.SUCCESS(f'{scope_name}: {count} unit(s) cached'))
        if not result:
            self.stdout.write(self.style.WARNING('No calibration scopes found — nothing to do.'))