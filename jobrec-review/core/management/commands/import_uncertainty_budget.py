from django.core.files import File
from django.core.management.base import BaseCommand

from core.models import CalibrationType, UncertaintyBudget, UncertaintyBudgetComponent
from core.uncertainty_budget import parse_budget_file


class Command(BaseCommand):
    help = (
        'Import an EATL uncertainty-budget workbook (.xlsx) as the active budget for a scope. '
        'Usage: manage.py import_uncertainty_budget <workbook.xlsx> --scope <pk> [--title "..."]'
    )

    def add_arguments(self, parser):
        parser.add_argument('workbook', help='Path to the .xlsx uncertainty-budget workbook.')
        parser.add_argument('--scope', type=int, required=True, help='CalibrationType pk the budget belongs to.')
        parser.add_argument('--title', default='', help='Optional human-readable title.')
        parser.add_argument('--deactivate-existing', action='store_true', help='Deactivate any existing active budget for the scope.')

    def handle(self, *args, **options):
        import os

        path = options['workbook']
        if not path.lower().endswith('.xlsx'):
            raise self.CommandError('Only .xlsx workbooks are supported.')

        scope = CalibrationType.objects.filter(pk=options['scope']).first()
        if scope is None:
            raise self.CommandError(f'No CalibrationType with pk={options["scope"]}.')
        if scope.uncertainty_budgets.filter(active=True).exists() and not options['deactivate_existing']:
            self.stdout.write(self.style.WARNING(
                f'{scope.name} already has an active budget. Pass --deactivate-existing to replace it.'
            ))
            return

        title = options['title'] or filesystem_name(scope.name)

        budget = UncertaintyBudget(scope=scope, title=title, active=False)
        with open(path, 'rb') as fh:
            budget.file.save(os.path.basename(path), File(fh), save=True)

        try:
            parsed = parse_budget_file(budget.file.path)
        except Exception as exc:
            budget.parse_status = 'error'
            budget.parse_error = f'{type(exc).__name__}: {exc}'
            budget.save(update_fields=['parse_status', 'parse_error'])
            raise self.CommandError(f'Could not parse workbook: {exc}')

        comps = parsed['components']
        if not comps:
            budget.parse_status = 'error'
            budget.parse_error = 'No Type-B uncertainty table found in the workbook.'
            budget.save(update_fields=['parse_status', 'parse_error'])
            raise self.CommandError('No Type-B uncertainty-components table found in the workbook.')

        UncertaintyBudgetComponent.objects.bulk_create([
            UncertaintyBudgetComponent(budget=budget, **c) for c in comps
        ])
        header = parsed['header']
        budget.doc_ref = header['doc_ref']
        budget.revision = header['revision']
        budget.revised_on = header['revised_on']
        budget.component_count = len(comps)
        budget.parse_status = 'ok'
        budget.parse_error = '\n'.join(parsed['warnings'])
        budget.save(update_fields=[
            'doc_ref', 'revision', 'revised_on', 'title',
            'component_count', 'parse_status', 'parse_error',
        ])
        scope.uncertainty_budgets.exclude(pk=budget.pk).update(active=False)
        budget.active = True
        budget.save(update_fields=['active'])

        self.stdout.write(self.style.SUCCESS(
            f'Imported "{header["doc_ref"]}" rev {header["revision"] or "—"} for {scope.name}: '
            f'{len(comps)} components, {len(parsed["points"])} points. Active budget set.'
        ))


def filesystem_name(name):
    import re

    return re.sub(r'[^\w\s-]', '', name).strip()[:120]