# Generated manually to add public UUIDs safely.

import uuid
from django.db import migrations, models

MODELS = [
    'CustomerInvoice',
    'CustomerInvoicePayment',
]


def populate_uuid(apps, schema_editor):
    for model_name in MODELS:
        model = apps.get_model('invoice', model_name)
        for obj in model.objects.filter(uuid__isnull=True):
            obj.uuid = uuid.uuid4()
            obj.save(update_fields=['uuid'])


class Migration(migrations.Migration):

    dependencies = [
        ('invoice', '0002_alter_customerinvoice_no_invoice_and_more'),
    ]

    operations = [
        migrations.AddField(model_name='customerinvoice', name='uuid', field=models.UUIDField(db_index=True, editable=False, null=True)),
        migrations.AddField(model_name='customerinvoicepayment', name='uuid', field=models.UUIDField(db_index=True, editable=False, null=True)),
        migrations.RunPython(populate_uuid, migrations.RunPython.noop),
        migrations.AlterField(model_name='customerinvoice', name='uuid', field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
        migrations.AlterField(model_name='customerinvoicepayment', name='uuid', field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
    ]