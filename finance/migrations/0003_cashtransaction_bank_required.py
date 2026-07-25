# Generated manually to align CashTransaction with the desktop TransaksiKas behavior.

import django.db.models.deletion
from django.core.exceptions import ValidationError
from django.db import migrations, models


def ensure_no_null_cash_bank(apps, schema_editor):
    CashTransaction = apps.get_model('finance', 'CashTransaction')
    if CashTransaction.objects.filter(bank__isnull=True).exists():
        raise ValidationError('Tidak bisa membuat bank wajib karena masih ada Transaksi Kas tanpa Bank/Kas.')


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0002_alter_banktransaction_no_bukti_and_more'),
        ('master', '0002_tenant_config_key_value'),
    ]

    operations = [
        migrations.RunPython(ensure_no_null_cash_bank, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='cashtransaction',
            name='bank',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='cash_transactions', to='master.bankaccount'),
        ),
    ]