# Generated manually for TenantConfig key-value model alignment.

from django.db import migrations, models


def copy_account_id_to_value(apps, schema_editor):
    TenantConfig = apps.get_model('master', 'TenantConfig')
    for config in TenantConfig.objects.all():
        account_id = getattr(config, 'akun_id', None)
        if account_id and not (config.nilai or '').strip():
            config.nilai = str(account_id)
            config.save(update_fields=['nilai'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('master', '0001_initial'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='TenantAccountConfig',
            new_name='TenantConfig',
        ),
        migrations.RunPython(copy_account_id_to_value, noop_reverse),
        migrations.RemoveField(
            model_name='tenantconfig',
            name='akun',
        ),
        migrations.RemoveConstraint(
            model_name='tenantconfig',
            name='uniq_tenantaccountconfig_tenant_kode',
        ),
        migrations.AddConstraint(
            model_name='tenantconfig',
            constraint=models.UniqueConstraint(fields=('tenant', 'kode'), name='uniq_tenantconfig_tenant_kode'),
        ),
    ]