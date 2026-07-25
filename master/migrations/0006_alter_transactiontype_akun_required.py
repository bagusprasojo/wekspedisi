# Generated manually after verifying no TransactionType rows have akun NULL.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('master', '0005_alter_chartofaccount_level'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transactiontype',
            name='akun',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='transaction_types', to='master.chartofaccount'),
        ),
    ]