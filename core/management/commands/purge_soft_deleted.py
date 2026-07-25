from django.apps import apps
from django.core.management.base import BaseCommand
from django.db.models.deletion import ProtectedError

PURGE_ORDER = [
    'accounting.ClosingBankBalance',
    'accounting.ClosingAccountBalance',
    'accounting.JournalLine',
    'invoice.CustomerInvoicePayment',
    'finance.EmployeeCashAdvancePayment',
    'invoice.CustomerInvoice',
    'finance.EmployeeCashAdvance',
    'finance.FuelPurchase',
    'finance.BankTransaction',
    'finance.CashTransaction',
    'accounting.Journal',
    'accounting.ClosingPeriod',
    'master.TenantConfig',
    'master.TransactionType',
    'master.BankAccount',
    'master.Armada',
    'master.ChartOfAccount',
    'master.StakeHolder',
]


class Command(BaseCommand):
    help = 'Hard delete rows that were previously soft-deleted. Protected rows are kept and reported.'

    def handle(self, *args, **options):
        all_models = {
            model._meta.label: model for model in apps.get_models()
            if any(field.name == 'is_deleted' for field in model._meta.fields)
        }
        ordered_models = [all_models.pop(label) for label in PURGE_ORDER if label in all_models]
        ordered_models.extend(all_models.values())

        total_deleted = 0
        total_protected = 0
        for model in ordered_models:
            queryset = model.objects.filter(is_deleted=True)
            model_deleted = 0
            model_protected = 0
            for obj in queryset.iterator():
                try:
                    deleted_count, _ = obj.delete()
                    model_deleted += deleted_count
                except ProtectedError:
                    model_protected += 1
            total_deleted += model_deleted
            total_protected += model_protected
            if model_deleted or model_protected:
                self.stdout.write(f'{model._meta.label}: deleted={model_deleted}, protected={model_protected}')
        self.stdout.write(self.style.SUCCESS(f'Done. deleted={total_deleted}, protected={total_protected}'))
