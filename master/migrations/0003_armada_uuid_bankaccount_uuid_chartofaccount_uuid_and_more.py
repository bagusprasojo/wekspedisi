# Generated manually to add public UUIDs safely.

import uuid
from django.db import migrations, models

MODELS = [
    'Armada',
    'BankAccount',
    'ChartOfAccount',
    'StakeHolder',
    'TenantConfig',
    'TransactionType',
]


def populate_uuid(apps, schema_editor):
    for model_name in MODELS:
        model = apps.get_model('master', model_name)
        for obj in model.objects.filter(uuid__isnull=True):
            obj.uuid = uuid.uuid4()
            obj.save(update_fields=['uuid'])


class Migration(migrations.Migration):

    dependencies = [
        ('master', '0002_tenant_config_key_value'),
    ]

    operations = [
        migrations.AddField(model_name='armada', name='uuid', field=models.UUIDField(db_index=True, editable=False, null=True)),
        migrations.AddField(model_name='bankaccount', name='uuid', field=models.UUIDField(db_index=True, editable=False, null=True)),
        migrations.AddField(model_name='chartofaccount', name='uuid', field=models.UUIDField(db_index=True, editable=False, null=True)),
        migrations.AddField(model_name='stakeholder', name='uuid', field=models.UUIDField(db_index=True, editable=False, null=True)),
        migrations.AddField(model_name='tenantconfig', name='uuid', field=models.UUIDField(db_index=True, editable=False, null=True)),
        migrations.AddField(model_name='transactiontype', name='uuid', field=models.UUIDField(db_index=True, editable=False, null=True)),
        migrations.RunPython(populate_uuid, migrations.RunPython.noop),
        migrations.AlterField(model_name='armada', name='uuid', field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
        migrations.AlterField(model_name='bankaccount', name='uuid', field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
        migrations.AlterField(model_name='chartofaccount', name='uuid', field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
        migrations.AlterField(model_name='stakeholder', name='uuid', field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
        migrations.AlterField(model_name='tenantconfig', name='uuid', field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
        migrations.AlterField(model_name='transactiontype', name='uuid', field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
    ]