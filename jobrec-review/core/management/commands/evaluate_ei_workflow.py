from django.core.management.base import BaseCommand
from core.ei_workflow import evaluate_clocks


class Command(BaseCommand):
    help = 'Evaluate E&I 48-hour approvals and overdue deadlines idempotently.'

    def handle(self, *args, **options):
        evaluate_clocks()
        self.stdout.write(self.style.SUCCESS('E&I workflow clocks evaluated.'))
