from django.core.management.base import BaseCommand
from core.models import CalibrationProcedure, EnvironmentRecord, PreCalibrationLog


class Command(BaseCommand):
    help = 'Backfill lab accreditation document numbers (doc_no) on existing rows missing one.'

    def handle(self, *args, **options):
        totals = {}
        for model, label in (
            (PreCalibrationLog, 'pre-calibration logs'),
            (EnvironmentRecord, 'environment records'),
            (CalibrationProcedure, 'calibration procedures'),
        ):
            count = 0
            for obj in model.objects.filter(doc_no='').order_by('created_at'):
                if obj.assign_doc_no():
                    count += 1
            totals[label] = count
            self.stdout.write(f'{label}: assigned {count} document number(s)')
        self.stdout.write(self.style.SUCCESS('Done.'))