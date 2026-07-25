# Generated manually to add public UUIDs safely.

import uuid
from django.db import migrations, models

MODELS = [
    'BankTransaction',
    'CashTransaction',
    'EmployeeCashAdvance',
    'EmployeeCashAdvancePayment',
    'FuelPurchase',
]


def populate_uuid(apps, schema_editor):
    for model_name in MODELS:
        model = apps.get_model('finance', model_name)
        for obj in model.objects.filter(uuid__isnull=True):
            obj.uuid = uuid.uuid4()
            obj.save(update_fields=['uuid'])


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0003_cashtransaction_bank_required'),
    ]

    operations = [
        migrations.AddField(model_name='banktransaction', name='uuid', field=models.UUIDField(db_index=True, editable=False, null=True)),
        migrations.AddField(model_name='cashtransaction', name='uuid', field=models.UUIDField(db_index=True, editable=False, null=True)),
        migrations.AddField(model_name='employeecashadvance', name='uuid', field=models.UUIDField(db_index=True, editable=False, null=True)),
        migrations.AddField(model_name='employeecashadvancepayment', name='uuid', field=models.UUIDField(db_index=True, editable=False, null=True)),
        migrations.AddField(model_name='fuelpurchase', name='uuid', field=models.UUIDField(db_index=True, editable=False, null=True)),
        migrations.RunPython(populate_uuid, migrations.RunPython.noop),
        migrations.AlterField(model_name='banktransaction', name='uuid', field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
        migrations.AlterField(model_name='cashtransaction', name='uuid', field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
        migrations.AlterField(model_name='employeecashadvance', name='uuid', field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
        migrations.AlterField(model_name='employeecashadvancepayment', name='uuid', field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
        migrations.AlterField(model_name='fuelpurchase', name='uuid', field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
    ]