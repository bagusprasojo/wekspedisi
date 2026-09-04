from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import F, Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse

from core.templatetags.crud_extras import format_money
from finance.models import CashTransaction, EmployeeCashAdvance, FuelPurchase, LoanDebt, LoanReceivable
from invoice.models import CustomerInvoice
from master.models import Armada
from reports.services import saldo_bank

ZERO = Decimal('0')


@login_required
def dashboard(request):
    return render(request, 'dashboard.html')


@login_required
def dashboard_summary_api(request):
    if request.tenant is None:
        return JsonResponse({'error': 'Tenant belum terhubung'}, status=400)

    tenant = request.tenant
    today = date.today()
    first_of_month = today.replace(day=1)

    # 1. Piutang Customer Belum Lunas
    unpaid_invoices_qs = CustomerInvoice.objects.filter(
        tenant=tenant, is_deleted=False, status_lunas='Belum'
    )
    piutang_agg = unpaid_invoices_qs.aggregate(
        total_piutang=Sum(F('total') - F('pelunasan'))
    )
    total_piutang = piutang_agg['total_piutang'] or ZERO
    unpaid_count = unpaid_invoices_qs.count()

    # 2. Total Saldo Kas & Bank
    bank_list = saldo_bank(tenant)
    total_saldo_kas_bank = sum((item['saldo'] for item in bank_list), ZERO)

    # 3. Kas Bon Karyawan Belum Lunas
    unpaid_advances_qs = EmployeeCashAdvance.objects.filter(
        tenant=tenant, is_deleted=False, status_lunas='Belum'
    )
    kas_bon_agg = unpaid_advances_qs.aggregate(
        total_saldo=Sum(F('nominal') - F('pelunasan'))
    )
    total_kas_bon = kas_bon_agg['total_saldo'] or ZERO

    # 4. Biaya BBM Bulan Ini
    fuel_month_qs = FuelPurchase.objects.filter(
        tenant=tenant, is_deleted=False, tanggal__gte=first_of_month
    )
    total_bbm_month = fuel_month_qs.aggregate(total=Sum('nominal_bbm'))['total'] or ZERO

    # 5. Omset & Pengeluaran Kas Bulan Ini
    invoice_month_qs = CustomerInvoice.objects.filter(
        tenant=tenant, is_deleted=False, tanggal__gte=first_of_month
    )
    inv_month_agg = invoice_month_qs.aggregate(
        total_omset=Sum('total'),
        total_pelunasan=Sum('pelunasan')
    )
    total_omset_month = inv_month_agg['total_omset'] or ZERO
    total_pelunasan_month = inv_month_agg['total_pelunasan'] or ZERO

    cash_tx_month_qs = CashTransaction.objects.filter(
        tenant=tenant, is_deleted=False, tanggal__gte=first_of_month
    )
    total_pengeluaran_kas = cash_tx_month_qs.aggregate(total=Sum('nominal_keluar'))['total'] or ZERO

    # 6. Jumlah Armada Aktif
    armada_count = Armada.objects.filter(tenant=tenant, is_deleted=False).count()

    # 7. Hutang Pinjaman Belum Lunas
    unpaid_debt_qs = LoanDebt.objects.filter(
        tenant=tenant, is_deleted=False, status_lunas='Belum'
    )
    debt_agg = unpaid_debt_qs.aggregate(
        total_saldo=Sum(F('nominal') - F('pelunasan'))
    )
    total_hutang_pinjaman = debt_agg['total_saldo'] or ZERO
    debt_count = unpaid_debt_qs.count()

    # 8. Piutang Pinjaman Belum Lunas
    unpaid_receivable_qs = LoanReceivable.objects.filter(
        tenant=tenant, is_deleted=False, status_lunas='Belum'
    )
    rec_agg = unpaid_receivable_qs.aggregate(
        total_saldo=Sum(F('nominal') - F('pelunasan'))
    )
    total_piutang_pinjaman = rec_agg['total_saldo'] or ZERO
    receivable_count = unpaid_receivable_qs.count()

    # 7. 5 Invoice Belum Lunas Terbaru
    recent_unpaid = []
    for inv in unpaid_invoices_qs.select_related('customer').order_by('-tanggal', '-id')[:5]:
        recent_unpaid.append({
            'no_invoice': inv.no_invoice,
            'customer': inv.customer.nama if inv.customer else '-',
            'tanggal': inv.tanggal.strftime('%d/%m/%Y'),
            'total': format_money(inv.total),
            'saldo': format_money(inv.saldo),
            'detail_url': reverse('invoice_invoice_customer_detail', args=[inv.uuid]),
        })

    # 8. 5 Transaksi Terakhir (Kas & BBM)
    recent_cash = list(CashTransaction.objects.filter(tenant=tenant, is_deleted=False).select_related('akun_transaksi').order_by('-tanggal', '-id')[:5])
    recent_bbm = list(FuelPurchase.objects.filter(tenant=tenant, is_deleted=False).select_related('armada').order_by('-tanggal', '-id')[:5])

    combined = []
    for c in recent_cash:
        nominal = c.nominal_keluar if c.nominal_keluar > ZERO else c.nominal_masuk
        jenis = 'Keluar' if c.nominal_keluar > ZERO else 'Masuk'
        combined.append({
            'tanggal_obj': c.tanggal,
            'id': c.id,
            'tanggal': c.tanggal.strftime('%d/%m/%Y'),
            'type': f'Kas ({jenis})',
            'no_bukti': c.no_bukti or '-',
            'nominal': format_money(nominal),
            'uraian': c.keterangan or (c.akun_transaksi.nama if c.akun_transaksi else '-'),
        })
    for b in recent_bbm:
        combined.append({
            'tanggal_obj': b.tanggal,
            'id': b.id,
            'tanggal': b.tanggal.strftime('%d/%m/%Y'),
            'type': 'BBM',
            'no_bukti': b.no_bukti or '-',
            'nominal': format_money(b.nominal_bbm),
            'uraian': f'BBM Armada {b.armada.nopol if b.armada else "-"}',
        })
    combined.sort(key=lambda x: (x['tanggal_obj'], x['id']), reverse=True)

    return JsonResponse({
        'total_piutang': format_money(total_piutang),
        'unpaid_count': unpaid_count,
        'total_saldo_kas_bank': format_money(total_saldo_kas_bank),
        'total_kas_bon': format_money(total_kas_bon),
        'total_bbm_month': format_money(total_bbm_month),
        'total_omset_month': format_money(total_omset_month),
        'total_pelunasan_month': format_money(total_pelunasan_month),
        'total_pengeluaran_kas': format_money(total_pengeluaran_kas),
        'armada_count': armada_count,
        'total_hutang_pinjaman': format_money(total_hutang_pinjaman),
        'debt_count': debt_count,
        'total_piutang_pinjaman': format_money(total_piutang_pinjaman),
        'receivable_count': receivable_count,
        'recent_unpaid_invoices': recent_unpaid,
        'recent_transactions': combined[:5],
    })
