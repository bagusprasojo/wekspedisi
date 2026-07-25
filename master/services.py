from django.core.exceptions import ValidationError

from master.models import ChartOfAccount, TenantConfig


def get_config_value(tenant, kode, *, required=True):
    config = TenantConfig.objects.filter(tenant=tenant, kode=kode, is_deleted=False).first()
    value = (config.nilai or '').strip() if config else ''
    if required and not value:
        raise ValidationError(f'Config {kode} belum diset.')
    return value


def get_config_account(tenant, kode, *, required=True):
    value = get_config_value(tenant, kode, required=required)
    if not value:
        return None

    queryset = ChartOfAccount.objects.filter(tenant=tenant, is_deleted=False, is_active=True)
    account = queryset.filter(pk=value).first() if value.isdigit() else None
    if account is None:
        account = queryset.filter(kode=value).first()
    if required and account is None:
        raise ValidationError(f'Config {kode} berisi akun yang tidak valid: {value}.')
    return account