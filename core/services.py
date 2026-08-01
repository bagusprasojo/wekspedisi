from django.db import transaction


ROMAN_MONTHS = {
    1: 'I',
    2: 'II',
    3: 'III',
    4: 'IV',
    5: 'V',
    6: 'VI',
    7: 'VII',
    8: 'VIII',
    9: 'IX',
    10: 'X',
    11: 'XI',
    12: 'XII',
}


def format_period(date_value):
    return date_value.strftime('%Y%m')


def next_document_number(tenant, document_type, date_value):
    from core.models import DocumentSequence

    period = format_period(date_value)
    with transaction.atomic():
        sequence, _ = (
            DocumentSequence.objects.select_for_update()
            .get_or_create(
                tenant=tenant,
                document_type=document_type,
                period=period,
                defaults={'last_number': 0},
            )
        )
        sequence.last_number += 1
        sequence.save(update_fields=['last_number', 'updated_at'])
        return f'{document_type}-{period}{sequence.last_number:04d}'


def next_invoice_number(tenant, date_value):
    from core.models import DocumentSequence
    from master.services import get_config_value

    period = date_value.strftime('%Y%m')
    invoice_code = get_config_value(tenant, 'INVOICE_CODE')
    with transaction.atomic():
        sequence, _ = (
            DocumentSequence.objects.select_for_update()
            .get_or_create(
                tenant=tenant,
                document_type='INV',
                period=period,
                defaults={'last_number': 0},
            )
        )
        sequence.last_number += 1
        sequence.save(update_fields=['last_number', 'updated_at'])
        roman_month = ROMAN_MONTHS[date_value.month]
        return f'{sequence.last_number:03d}/{roman_month}/{invoice_code}/{date_value.year}'
