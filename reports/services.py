from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum

from accounting.models import ClosingBankBalance, Journal, JournalLine
from accounting.services import normal_balance_amount
from finance.models import BankTransaction, CashTransaction, EmployeeCashAdvance, EmployeeCashAdvancePayment, FuelPurchase
from invoice.models import CustomerInvoice, CustomerInvoicePayment
from master.models import BankAccount, ChartOfAccount

ZERO = Decimal('0')


def filter_date_range(queryset, start_date=None, end_date=None, field='tanggal'):
    if start_date:
        queryset = queryset.filter(**{f'{field}__gte': start_date})
    if end_date:
        is_datetime = False
        try:
            model = queryset.model
            parts = field.split('__')
            curr_model = model
            for part in parts[:-1]:
                curr_model = curr_model._meta.get_field(part).related_model
            model_field = curr_model._meta.get_field(parts[-1])
            is_datetime = model_field.get_internal_type() == 'DateTimeField'
        except Exception:
            is_datetime = False

        if is_datetime:
            if isinstance(end_date, str):
                try:
                    end_date = date.fromisoformat(end_date)
                except ValueError:
                    pass
            if isinstance(end_date, date) and not isinstance(end_date, datetime):
                end_date = datetime.combine(end_date, time.max)
            queryset = queryset.filter(**{f'{field}__lte': end_date})
        else:
            queryset = queryset.filter(**{f'{field}__lte': end_date})
    return queryset


def daftar_jurnal(tenant, start_date=None, end_date=None):
    queryset = Journal.objects.filter(tenant=tenant, is_deleted=False).prefetch_related('lines__perkiraan')
    queryset = filter_date_range(queryset, start_date, end_date)
    return queryset.annotate(total_debet=Sum('lines__debet'), total_kredit=Sum('lines__kredit')).order_by('tanggal', 'id')


def journal_lines(tenant, start_date=None, end_date=None, account=None):
    queryset = JournalLine.objects.filter(
        tenant=tenant,
        is_deleted=False,
        journal__tenant=tenant,
        journal__is_deleted=False,
    ).select_related('journal', 'perkiraan')
    queryset = filter_date_range(queryset, start_date, end_date, field='journal__tanggal')
    if account:
        queryset = queryset.filter(perkiraan=account)
    return queryset.order_by('journal__tanggal', 'journal__id', 'id')


def opening_balance(tenant, account, start_date=None):
    if not start_date or not account:
        return ZERO
    totals = JournalLine.objects.filter(
        tenant=tenant,
        is_deleted=False,
        journal__tenant=tenant,
        journal__is_deleted=False,
        journal__tanggal__lt=start_date,
        perkiraan=account,
    ).aggregate(total_debet=Sum('debet'), total_kredit=Sum('kredit'))
    debet = totals['total_debet'] or ZERO
    kredit = totals['total_kredit'] or ZERO
    if account.saldo_normal == ChartOfAccount.NormalBalance.KREDIT:
        return kredit - debet
    return debet - kredit


def buku_besar(tenant, start_date=None, end_date=None, account=None):
    rows = []
    balance = opening_balance(tenant, account, start_date)
    for line in journal_lines(tenant, start_date, end_date, account=account):
        if account and account.saldo_normal == ChartOfAccount.NormalBalance.KREDIT:
            balance += line.kredit - line.debet
        elif account:
            balance += line.debet - line.kredit
        else:
            balance = None
        rows.append({'line': line, 'saldo': balance})
    return rows


def trial_balance(tenant, start_date=None, end_date=None, include_closing=False):
    end_cutoff = end_date or date.today()
    sow_totals_by_account = {}
    if start_date:
        sow_qs = JournalLine.objects.filter(
            tenant=tenant,
            is_deleted=False,
            journal__tenant=tenant,
            journal__is_deleted=False,
            journal__tanggal__lt=start_date,
        )
        # Saldo Awal (sebelum periode) SELALU memperhitungkan jurnal tutup tahun periode lalu
        sow_rows = sow_qs.values('perkiraan').annotate(total_debet=Sum('debet'), total_kredit=Sum('kredit'))
        for row in sow_rows:
            sow_totals_by_account[row['perkiraan']] = {
                'debet': row['total_debet'] or ZERO,
                'kredit': row['total_kredit'] or ZERO,
            }

    mutation_query = JournalLine.objects.filter(
        tenant=tenant,
        is_deleted=False,
        journal__tenant=tenant,
        journal__is_deleted=False,
        journal__tanggal__lte=end_cutoff,
    )
    if start_date:
        mutation_query = mutation_query.filter(journal__tanggal__gte=start_date)
    # Filter include/exclude jurnal penutup HANYA berlaku untuk mutasi di periode terpilih
    if not include_closing:
        mutation_query = mutation_query.exclude(journal__transaksi='jurnal_tutup_tahun')

    mutation_rows = (
        mutation_query.values('perkiraan')
        .annotate(total_debet=Sum('debet'), total_kredit=Sum('kredit'))
    )
    mutations_by_account = {
        row['perkiraan']: {
            'debet': row['total_debet'] or ZERO,
            'kredit': row['total_kredit'] or ZERO,
        }
        for row in mutation_rows
    }

    result = []
    accounts = ChartOfAccount.objects.filter(tenant=tenant, is_deleted=False, is_active=True).order_by('kode')
    for account in accounts:
        sow_raw = sow_totals_by_account.get(account.pk, {'debet': ZERO, 'kredit': ZERO})
        mut_raw = mutations_by_account.get(account.pk, {'debet': ZERO, 'kredit': ZERO})

        mut_debet = mut_raw['debet']
        mut_kredit = mut_raw['kredit']

        if account.saldo_normal == ChartOfAccount.NormalBalance.KREDIT:
            sow_debet = ZERO
            sow_kredit = sow_raw['kredit'] - sow_raw['debet']
            akhir_debet = ZERO
            akhir_kredit = sow_kredit + (mut_kredit - mut_debet)
        else:
            sow_debet = sow_raw['debet'] - sow_raw['kredit']
            sow_kredit = ZERO
            akhir_debet = sow_debet + (mut_debet - mut_kredit)
            akhir_kredit = ZERO

        if (
            sow_debet == ZERO
            and sow_kredit == ZERO
            and mut_debet == ZERO
            and mut_kredit == ZERO
            and akhir_debet == ZERO
            and akhir_kredit == ZERO
        ):
            continue

        result.append({
            'account': account,
            'sow_debet': sow_debet,
            'sow_kredit': sow_kredit,
            'debet': mut_debet,
            'kredit': mut_kredit,
            'akhir_debet': akhir_debet,
            'akhir_kredit': akhir_kredit,
        })
    return result


def saldo_bank(tenant, end_date=None):
    cutoff = end_date or date.today()
    totals = defaultdict(lambda: {'debet': ZERO, 'kredit': ZERO})
    rows = (
        JournalLine.objects.filter(
            tenant=tenant,
            is_deleted=False,
            journal__tenant=tenant,
            journal__is_deleted=False,
            journal__tanggal__lte=cutoff,
            perkiraan__bank_accounts__tenant=tenant,
            perkiraan__bank_accounts__is_deleted=False,
        )
        .values('perkiraan')
        .annotate(total_debet=Sum('debet'), total_kredit=Sum('kredit'))
    )
    for row in rows:
        totals[row['perkiraan']] = {'debet': row['total_debet'] or ZERO, 'kredit': row['total_kredit'] or ZERO}

    result = []
    for bank in BankAccount.objects.filter(tenant=tenant, is_deleted=False, akun__isnull=False).select_related('akun').order_by('nama_bank', 'no_rekening'):
        normal = normal_balance_amount(bank.akun, totals[bank.akun_id])
        result.append({'bank': bank, 'akun': bank.akun, 'saldo': normal['debet'] - normal['kredit']})
    return result

def rekap_transaksi_kas(tenant, start_date=None, end_date=None):
    queryset = CashTransaction.objects.filter(tenant=tenant, is_deleted=False).select_related(
        'akun_transaksi',
        'bank',
        'armada',
        'created_by',
    )
    queryset = filter_date_range(queryset, start_date, end_date)
    return queryset.order_by('tanggal', 'id')

def riwayat_pembelian_bbm(tenant, start_date=None, end_date=None, armada=None):
    if not armada:
        return FuelPurchase.objects.none()
    queryset = FuelPurchase.objects.filter(tenant=tenant, is_deleted=False, armada=armada).select_related(
        'armada',
        'driver',
        'created_by',
    )
    queryset = filter_date_range(queryset, start_date, end_date)
    return queryset.order_by('tanggal', 'id')

def rekap_transaksi_bank(tenant, start_date=None, end_date=None):
    queryset = BankTransaction.objects.filter(tenant=tenant, is_deleted=False).select_related(
        'bank_utama',
        'jenis_transaksi',
        'jenis_transaksi__akun',
        'created_by',
    )
    queryset = filter_date_range(queryset, start_date, end_date)
    return queryset.order_by('jenis_transaksi__akun__kode', 'tanggal', 'id')

def rekening_koran(tenant, start_date=None, end_date=None, bank=None):
    rows = bank_mutasi_rows(tenant, bank, start_date, end_date)
    return sorted(rows, key=lambda row: (row['tanggal'], row['order'], row['id']))

def rekening_koran_saldo_awal(tenant, start_date=None, bank=None):
    if not bank or not start_date:
        return ZERO
    cutoff = start_date - timedelta(days=1)
    closing = ClosingBankBalance.objects.filter(
        tenant=tenant,
        is_deleted=False,
        bank=bank,
        tanggal__lte=cutoff,
    ).order_by('-tanggal').first()
    saldo = closing.saldo_akhir if closing else ZERO
    after_closing = closing.tanggal + timedelta(days=1) if closing else None
    for row in bank_mutasi_rows(tenant, bank, after_closing, cutoff):
        saldo += row['kredit'] - row['debet']
    return saldo

def bank_mutasi_rows(tenant, bank, start_date=None, end_date=None):
    if not bank:
        return []

    def in_range(queryset):
        return filter_date_range(queryset, start_date, end_date)

    def username(obj):
        return obj.created_by.username if obj.created_by else ''

    rows = []
    for row in in_range(BankTransaction.objects.filter(tenant=tenant, is_deleted=False, bank_utama=bank).select_related('jenis_transaksi', 'created_by')):
        rows.append({'id': row.id, 'order': 10, 'tanggal': row.tanggal, 'kode': row.jenis_transaksi.kode, 'debet': row.debet, 'kredit': row.kredit, 'user_create': username(row), 'uraian': row.uraian})
        if row.biaya_adm_bank > ZERO:
            rows.append({'id': row.id, 'order': 40, 'tanggal': row.tanggal, 'kode': '08', 'debet': row.biaya_adm_bank, 'kredit': ZERO, 'user_create': username(row), 'uraian': 'Biaya administrasi bank'})

    for row in in_range(BankTransaction.objects.filter(tenant=tenant, is_deleted=False, bank_tujuan=bank).select_related('jenis_transaksi', 'created_by')):
        rows.append({'id': row.id, 'order': 50, 'tanggal': row.tanggal, 'kode': row.jenis_transaksi.kode, 'debet': row.kredit, 'kredit': row.debet, 'user_create': username(row), 'uraian': row.uraian})

    for row in in_range(CustomerInvoicePayment.objects.filter(tenant=tenant, is_deleted=False, bank=bank).select_related('tagihan_customer__customer', 'created_by')):
        invoice = row.tagihan_customer
        customer = invoice.customer
        suffix = f'{invoice.no_invoice}a.n. {customer.nama}'
        rows.append({'id': row.id, 'order': 20, 'tanggal': row.tanggal, 'kode': '00', 'debet': ZERO, 'kredit': row.nominal_kas + row.pph - row.ppn, 'user_create': username(row), 'uraian': f'Pembayaran Invoice {suffix}'})
        rows.append({'id': row.id, 'order': 21, 'tanggal': row.tanggal, 'kode': '00', 'debet': ZERO, 'kredit': row.ppn, 'user_create': username(row), 'uraian': f'Pembayaran PPN Invoice {suffix}'})
        rows.append({'id': row.id, 'order': 22, 'tanggal': row.tanggal, 'kode': '00', 'debet': row.pph, 'kredit': ZERO, 'user_create': username(row), 'uraian': f'Pembayaran PPH Invoice {suffix}'})

    for row in in_range(CashTransaction.objects.filter(tenant=tenant, is_deleted=False, bank=bank).select_related('akun_transaksi', 'created_by')):
        rows.append({'id': row.id, 'order': 60, 'tanggal': row.tanggal, 'kode': '00', 'debet': row.nominal_keluar, 'kredit': row.nominal_masuk, 'user_create': username(row), 'uraian': f'{row.akun_transaksi.nama} [Via Mutasi Kas]'})

    for row in in_range(EmployeeCashAdvancePayment.objects.filter(tenant=tenant, is_deleted=False, bank=bank).select_related('created_by')):
        rows.append({'id': row.id, 'order': 70, 'tanggal': row.tanggal, 'kode': '00', 'debet': ZERO, 'kredit': row.nominal, 'user_create': username(row), 'uraian': f'{row.keterangan} [Via Pembayaran Kas Bon]'})

    for row in in_range(EmployeeCashAdvance.objects.filter(tenant=tenant, is_deleted=False, bank=bank).select_related('karyawan', 'created_by')):
        rows.append({'id': row.id, 'order': 80, 'tanggal': row.tanggal, 'kode': '00', 'debet': row.nominal, 'kredit': ZERO, 'user_create': username(row), 'uraian': f'Kas Bon a.n. {row.karyawan.nama} [Via Kas Bon]'})

    for row in in_range(FuelPurchase.objects.filter(tenant=tenant, is_deleted=False, bank=bank).select_related('created_by')):
        rows.append({'id': row.id, 'order': 90, 'tanggal': row.tanggal, 'kode': '00', 'debet': row.nominal_bbm, 'kredit': ZERO, 'user_create': username(row), 'uraian': f'{row.keterangan} [Via Transaksi Pembelian BBM]'})

    return rows

def rekap_transaksi_kas_bon(tenant, start_date=None, end_date=None):
    rows = []
    advances = EmployeeCashAdvance.objects.filter(tenant=tenant, is_deleted=False).select_related(
        'karyawan',
        'perkiraan_pinjaman',
        'perkiraan_kas',
        'created_by',
    )
    advances = filter_date_range(advances, start_date, end_date)
    for row in advances:
        rows.append({
            'account_code': row.perkiraan_pinjaman.kode,
            'account_name': row.perkiraan_pinjaman.nama,
            'account_label': f'{row.perkiraan_pinjaman.kode} - {row.perkiraan_pinjaman.nama}',
            'karyawan': row.karyawan.nama,
            'no_register': row.no_register,
            'tanggal': row.tanggal,
            'akun_kas': f'{row.perkiraan_kas.kode} - {row.perkiraan_kas.nama}',
            'keterangan': row.keterangan,
            'keluar': row.nominal,
            'masuk': ZERO,
            'created_by': row.created_by.username if row.created_by else '',
        })
    payments = EmployeeCashAdvancePayment.objects.filter(tenant=tenant, is_deleted=False).select_related(
        'kas_bon_karyawan__karyawan',
        'kas_bon_karyawan__perkiraan_pinjaman',
        'perkiraan_kas',
        'created_by',
    )
    payments = filter_date_range(payments, start_date, end_date)
    for row in payments:
        advance = row.kas_bon_karyawan
        rows.append({
            'account_code': advance.perkiraan_pinjaman.kode,
            'account_name': advance.perkiraan_pinjaman.nama,
            'account_label': f'{advance.perkiraan_pinjaman.kode} - {advance.perkiraan_pinjaman.nama}',
            'karyawan': advance.karyawan.nama,
            'no_register': row.no_register,
            'tanggal': row.tanggal,
            'akun_kas': f'{row.perkiraan_kas.kode} - {row.perkiraan_kas.nama}',
            'keterangan': row.keterangan,
            'keluar': ZERO,
            'masuk': row.nominal,
            'created_by': row.created_by.username if row.created_by else '',
        })
    return sorted(rows, key=lambda row: (row['account_code'], row['tanggal'], row['no_register']))

def saldo_kas_bon(tenant, end_date=None):
    cutoff = end_date or date.today()
    rows = []
    advances = EmployeeCashAdvance.objects.filter(
        tenant=tenant,
        is_deleted=False,
        tanggal__lte=cutoff,
        status_lunas=EmployeeCashAdvance.StatusLunas.BELUM,
    ).select_related('karyawan', 'perkiraan_pinjaman', 'created_by').order_by('perkiraan_pinjaman__kode', 'no_register')
    for row in advances:
        rows.append({
            'account_code': row.perkiraan_pinjaman.kode,
            'account_name': row.perkiraan_pinjaman.nama,
            'account_label': f'{row.perkiraan_pinjaman.kode} - {row.perkiraan_pinjaman.nama}',
            'no_register': row.no_register,
            'tanggal': row.tanggal,
            'nama_karyawan': row.karyawan.nama,
            'alamat_karyawan': row.karyawan.alamat,
            'nominal': row.nominal,
            'pelunasan': row.pelunasan,
            'saldo': row.nominal - row.pelunasan,
            'created_by': row.created_by.username if row.created_by else '',
        })
    return rows

def rekap_invoice_customer(tenant, start_date=None, end_date=None):
    queryset = CustomerInvoice.objects.filter(tenant=tenant, is_deleted=False).select_related('customer', 'created_by')
    queryset = filter_date_range(queryset, start_date, end_date)
    return queryset.order_by('tanggal', 'id')

def rekap_pembayaran_invoice_customer(tenant, start_date=None, end_date=None):
    queryset = CustomerInvoicePayment.objects.filter(tenant=tenant, is_deleted=False).select_related(
        'tagihan_customer__customer',
        'bank',
        'created_by',
    )
    queryset = filter_date_range(queryset, start_date, end_date)
    return queryset.order_by('tanggal', 'id')
