from django import template
from decimal import Decimal, ROUND_HALF_UP

register = template.Library()

MONEY_FIELDS = {
    'debet',
    'kredit',
    'biaya_adm_bank',
    'nilai_pekerjaan',
    'nominal',
    'nominal_bbm',
    'nominal_keluar',
    'nominal_masuk',
    'nominal_kas',
    'pelunasan',
    'pph',
    'ppn',
    'saldo',
    'hutang',
    'saldo_hutang',
    'total',
    'total_pembayaran',
}


@register.filter
def get_attr(obj, attr_name):
    value = obj
    for part in attr_name.split('.'):
        value = value.get(part, '') if isinstance(value, dict) else getattr(value, part, '')
        if callable(value):
            value = value()
    return value


@register.filter
def humanize_field(value):
    return str(value).replace('_', ' ').title()


@register.filter
def is_money_field(field_name):
    return field_name.split('.')[-1] in MONEY_FIELDS


@register.filter
def format_money(value):
    if value in (None, ''):
        return ''
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return value
    formatted = f'{amount:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')
    return formatted[:-3] if formatted.endswith(',00') else formatted

@register.filter
def format_money_integer(value):
    if value in (None, ''):
        return ''
    try:
        amount = Decimal(value).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    except Exception:
        return value
    return f'{amount:,.0f}'.replace(',', '.')

@register.filter
def sum_attr(items, attr_name):
    total = Decimal('0')
    for item in items:
        value = get_attr(item, attr_name)
        if value in (None, ''):
            continue
        try:
            total += Decimal(value)
        except Exception:
            continue
    return format_money(total)
