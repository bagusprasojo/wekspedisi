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


def next_document_number(tenant, document_type, date_value, model=None, field_name='no_bukti'):
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
        while True:
            sequence.last_number += 1
            candidate = f'{document_type}-{period}{sequence.last_number:04d}'
            if model is not None:
                if model.objects.filter(tenant=tenant, **{field_name: candidate}).exists():
                    continue
            sequence.save(update_fields=['last_number', 'updated_at'])
            return candidate


def next_invoice_number(tenant, date_value, model=None):
    from core.models import DocumentSequence
    from master.services import get_config_value

    period = date_value.strftime('%Y')
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
        roman_month = ROMAN_MONTHS[date_value.month]
        while True:
            sequence.last_number += 1
            candidate = f'{sequence.last_number:03d}/{roman_month}/{invoice_code}/{date_value.year}'
            if model is not None:
                if model.objects.filter(tenant=tenant, no_invoice=candidate).exists():
                    continue
            sequence.save(update_fields=['last_number', 'updated_at'])
            return candidate
