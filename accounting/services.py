from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from core.services import next_document_number


class BusinessRuleError(ValidationError):
    pass


def ensure_open_period(tenant, tanggal, old_tanggal=None):
    from accounting.models import ClosingPeriod
    last_closing = ClosingPeriod.objects.filter(tenant=tenant, is_deleted=False).order_by('-tanggal').first()
    if not last_closing:
        return
    if tanggal <= last_closing.tanggal:
        raise BusinessRuleError('Transaksi tidak bisa disimpan karena periode sudah closing.')
    if old_tanggal and old_tanggal <= last_closing.tanggal:
        raise BusinessRuleError('Transaksi lama sudah masuk periode closing dan tidak bisa diubah.')


def ensure_last_day_of_month(date_value):
    last_day = monthrange(date_value.year, date_value.month)[1]
    if date_value.day != last_day:
        raise BusinessRuleError('Tanggal closing harus akhir bulan.')


def month_end(year, month):
    return date(year, month, monthrange(year, month)[1])

def next_month_end(date_value):
    year = date_value.year + (1 if date_value.month == 12 else 0)
    month = 1 if date_value.month == 12 else date_value.month + 1
    return month_end(year, month)

def oldest_transaction_date(tenant):
    from accounting.models import Journal

    journal = Journal.objects.filter(tenant=tenant, is_deleted=False).order_by('tanggal', 'id').first()
    return journal.tanggal if journal else None

def expected_closing_date(tenant):
    from accounting.models import ClosingPeriod

    last = ClosingPeriod.objects.filter(tenant=tenant, is_deleted=False).order_by('-tanggal').first()
    if last:
        return next_month_end(last.tanggal)
    oldest = oldest_transaction_date(tenant)
    if oldest:
        return month_end(oldest.year, oldest.month)
    return None

def ensure_next_closing_month(tenant, date_value, current_pk=None):
    from accounting.models import ClosingPeriod
    last = ClosingPeriod.objects.filter(tenant=tenant, is_deleted=False).exclude(pk=current_pk).order_by('-tanggal').first()
    if not last:
        return
    year = last.tanggal.year + (1 if last.tanggal.month == 12 else 0)
    month = 1 if last.tanggal.month == 12 else last.tanggal.month + 1
    if date_value.year != year or date_value.month != month:
        raise BusinessRuleError('Closing harus dilakukan berurutan tiap bulan.')

def ensure_expected_closing_date(tenant, date_value, current_pk=None):
    if current_pk:
        return
    expected = expected_closing_date(tenant)
    if not expected:
        raise BusinessRuleError('Belum ada transaksi yang bisa diclosing.')
    if date_value != expected:
        raise BusinessRuleError(f'Tanggal closing berikutnya harus {expected.strftime("%d/%m/%Y")}.')


def validate_leaf_account(account):
    if account and not account.is_leaf:
        raise BusinessRuleError(f'Akun {account.kode} tidak bisa dipakai transaksi karena punya akun anak.')
    if account is None:
        raise BusinessRuleError('Akun jurnal belum lengkap.')


def generated_transaction_key(obj):
    return f'{obj._meta.app_label}.{obj._meta.model_name}'


@transaction.atomic
def refresh_journal(*, obj, no_jurnal, tanggal, keterangan, lines, user):
    from accounting.models import Journal, JournalLine
    ensure_open_period(obj.tenant, tanggal)
    for line in lines:
        validate_leaf_account(line['account'])
    Journal.objects.filter(
        tenant=obj.tenant,
        transaksi_id=obj.pk,
        transaksi=generated_transaction_key(obj),
    ).delete()
    journal = Journal.objects.create(
        tenant=obj.tenant,
        no_jurnal=no_jurnal,
        tanggal=tanggal,
        transaksi_id=obj.pk,
        transaksi=generated_transaction_key(obj),
        keterangan=keterangan or '',
        created_by=user,
    )
    for line in lines:
        JournalLine.objects.create(
            tenant=obj.tenant,
            journal=journal,
            perkiraan=line['account'],
            debet=Decimal(line.get('debet', 0) or 0),
            kredit=Decimal(line.get('kredit', 0) or 0),
            created_by=user,
        )
    return journal


def delete_generated_journal(obj):
    from accounting.models import Journal
    Journal.objects.filter(
        tenant=obj.tenant,
        transaksi_id=obj.pk,
        transaksi=generated_transaction_key(obj),
    ).delete()


def assign_number(obj, field_name, document_type):
    if not getattr(obj, field_name):
        setattr(obj, field_name, next_document_number(obj.tenant, document_type, obj.tanggal))


def account_totals_until(tenant, tanggal):
    from accounting.models import JournalLine
    rows = (
        JournalLine.objects.filter(
            tenant=tenant,
            is_deleted=False,
            journal__tenant=tenant,
            journal__is_deleted=False,
            journal__tanggal__lte=tanggal,
        )
        .values('perkiraan')
        .annotate(total_debet=Sum('debet'), total_kredit=Sum('kredit'))
    )
    return {
        row['perkiraan']: {
            'debet': row['total_debet'] or Decimal('0'),
            'kredit': row['total_kredit'] or Decimal('0'),
        }
        for row in rows
    }


def normal_balance_amount(account, totals):
    debet = totals.get('debet', Decimal('0'))
    kredit = totals.get('kredit', Decimal('0'))
    if account.saldo_normal == 'KREDIT':
        amount = kredit - debet
        return {'debet': Decimal('0'), 'kredit': amount} if amount >= 0 else {'debet': abs(amount), 'kredit': Decimal('0')}
    amount = debet - kredit
    return {'debet': amount, 'kredit': Decimal('0')} if amount >= 0 else {'debet': Decimal('0'), 'kredit': abs(amount)}


@transaction.atomic
def refresh_closing_snapshots(closing, user=None):
    from accounting.models import ClosingAccountBalance, ClosingBankBalance
    from master.models import BankAccount, ChartOfAccount

    totals_by_account = account_totals_until(closing.tenant, closing.tanggal)
    ClosingBankBalance.objects.filter(closing=closing).delete()
    ClosingAccountBalance.objects.filter(closing=closing).delete()

    bank_rows = []
    for bank in BankAccount.objects.filter(tenant=closing.tenant, is_deleted=False, akun__isnull=False).select_related('akun'):
        totals = totals_by_account.get(bank.akun_id, {'debet': Decimal('0'), 'kredit': Decimal('0')})
        normal = normal_balance_amount(bank.akun, totals)
        saldo_akhir = normal['debet'] - normal['kredit']
        bank_rows.append(
            ClosingBankBalance(
                tenant=closing.tenant,
                closing=closing,
                bank=bank,
                tanggal=closing.tanggal,
                saldo_akhir=saldo_akhir,
                created_by=user,
            )
        )
    if bank_rows:
        ClosingBankBalance.objects.bulk_create(bank_rows)

    account_rows = []
    accounts = ChartOfAccount.objects.filter(tenant=closing.tenant, is_deleted=False, is_active=True)
    for account in accounts:
        totals = totals_by_account.get(account.pk, {'debet': Decimal('0'), 'kredit': Decimal('0')})
        normal = normal_balance_amount(account, totals)
        if normal['debet'] == 0 and normal['kredit'] == 0:
            continue
        account_rows.append(
            ClosingAccountBalance(
                tenant=closing.tenant,
                closing=closing,
                perkiraan=account,
                saldo_normal=account.saldo_normal,
                tanggal=closing.tanggal,
                debet=normal['debet'],
                kredit=normal['kredit'],
                created_by=user,
            )
        )
    if account_rows:
        ClosingAccountBalance.objects.bulk_create(account_rows)
