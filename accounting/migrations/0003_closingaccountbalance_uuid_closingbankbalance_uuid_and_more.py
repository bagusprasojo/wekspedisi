# Generated manually to add public UUIDs safely.

import uuid
from django.db import migrations, models

MODELS = [
    'ClosingAccountBalance',
    'ClosingBankBalance',
    'ClosingPeriod',
    'Journal',
    'JournalLine',
]


def populate_uuid(apps, schema_editor):
    for model_name in MODELS:
        model = apps.get_model('accounting', model_name)
        for obj in model.objects.filter(uuid__isnull=True):
            obj.uuid = uuid.uuid4()
            obj.save(update_fields=['uuid'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0002_alter_journal_no_jurnal'),
    ]

    operations = [
        migrations.AddField(model_name='closingaccountbalance', name='uuid', field=models.UUIDField(db_index=True, editable=False, null=True)),
        migrations.AddField(model_name='closingbankbalance', name='uuid', field=models.UUIDField(db_index=True, editable=False, null=True)),
        migrations.AddField(model_name='closingperiod', name='uuid', field=models.UUIDField(db_index=True, editable=False, null=True)),
        migrations.AddField(model_name='journal', name='uuid', field=models.UUIDField(db_index=True, editable=False, null=True)),
        migrations.AddField(model_name='journalline', name='uuid', field=models.UUIDField(db_index=True, editable=False, null=True)),
        migrations.RunPython(populate_uuid, migrations.RunPython.noop),
        migrations.AlterField(model_name='closingaccountbalance', name='uuid', field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
        migrations.AlterField(model_name='closingbankbalance', name='uuid', field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
        migrations.AlterField(model_name='closingperiod', name='uuid', field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
        migrations.AlterField(model_name='journal', name='uuid', field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
        migrations.AlterField(model_name='journalline', name='uuid', field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
    ]