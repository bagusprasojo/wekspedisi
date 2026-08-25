from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from accounting.models import Journal
from accounting.services import generated_transaction_key
from finance.models import BankTransaction, CashTransaction, EmployeeCashAdvance, EmployeeCashAdvancePayment, FuelPurchase, LoanDebt, LoanDebtPayment
from master.models import ChartOfAccount


def require_tenant(request):
    if request.user.is_superuser and request.tenant is None:
        raise PermissionDenied('Superadmin tidak berada di tenant. Gunakan menu Platform.')
    if request.tenant is None:
        raise PermissionDenied('User belum terhubung ke tenant.')


def transaction_journal(request, transaction):
    return Journal.objects.filter(
        tenant=request.tenant,
        is_deleted=False,
        transaksi_id=transaction.pk,
        transaksi=generated_transaction_key(transaction),
    ).prefetch_related('lines__perkiraan').first()

@login_required
def fuel_purchase_last_km(request):
    require_tenant(request)
    armada_id = request.GET.get('armada')
    last_purchase = (
        FuelPurchase.objects.filter(tenant=request.tenant, is_deleted=False, armada_id=armada_id)
        .order_by('-tanggal', '-id')
        .first()
        if armada_id
        else None
    )
    return JsonResponse({'km_terakhir': last_purchase.km_sekarang if last_purchase else 0})

@login_required
def cash_transaction_account_lookup(request):
    require_tenant(request)
    from django.db.models import Exists, OuterRef, Q

    q = request.GET.get('q', '').strip()
    child_accounts = ChartOfAccount.objects.filter(
        tenant=request.tenant,
        is_deleted=False,
        parent=OuterRef('pk'),
    )
    accounts = (
        ChartOfAccount.objects.filter(tenant=request.tenant, is_deleted=False, is_active=True)
        .annotate(has_children=Exists(child_accounts))
        .filter(has_children=False)
    )
    if q:
        accounts = accounts.filter(Q(kode__icontains=q) | Q(nama__icontains=q))
    return JsonResponse({
        'results': [
            {'id': account.pk, 'label': str(account)}
            for account in accounts.order_by('kode')[:20]
        ]
    })


@login_required
def cash_advance_lookup(request):
    require_tenant(request)
    from django.db.models import Q
    from core.templatetags.crud_extras import format_money

    q = request.GET.get('q', '').strip()
    queryset = EmployeeCashAdvance.objects.filter(
        tenant=request.tenant,
        is_deleted=False,
        status_lunas='Belum',
    ).select_related('karyawan')
    if q:
        queryset = queryset.filter(
            Q(no_register__icontains=q)
            | Q(karyawan__nama__icontains=q)
            | Q(keterangan__icontains=q)
        )
    results = []
    for adv in queryset.order_by('-tanggal', '-id')[:20]:
        saldo_val = format_money(adv.saldo)
        label = f"{adv.no_register} - {adv.karyawan.nama if adv.karyawan else ''} (Sisa: {saldo_val})"
        results.append({
            'id': adv.pk,
            'label': label,
            'no_register': adv.no_register,
            'nama': adv.karyawan.nama if adv.karyawan else '',
            'alamat': adv.karyawan.alamat if adv.karyawan else '',
            'saldo': saldo_val,
        })
    return JsonResponse({'results': results})


@login_required
def cash_transaction_detail(request, uuid):
    require_tenant(request)
    transaction = get_object_or_404(
        CashTransaction.objects.filter(tenant=request.tenant, is_deleted=False).select_related(
            'akun_kas',
            'akun_transaksi',
            'armada',
            'bank',
        ),
        uuid=uuid,
    )
    return render(
        request,
        'finance/cash_transaction_detail.html',
        {
            'title': f'Detail Transaksi Kas {transaction.no_bukti}',
            'object': transaction,
            'journal': transaction_journal(request, transaction),
            'cancel_url': reverse('finance_transaksi_kas_list'),
        },
    )


@login_required
def fuel_purchase_detail(request, uuid):
    require_tenant(request)
    transaction = get_object_or_404(
        FuelPurchase.objects.filter(tenant=request.tenant, is_deleted=False).select_related(
            'armada',
            'driver',
            'bank',
        ),
        uuid=uuid,
    )
    return render(
        request,
        'finance/fuel_purchase_detail.html',
        {
            'title': f'Detail Pembelian BBM {transaction.no_bukti}',
            'object': transaction,
            'journal': transaction_journal(request, transaction),
            'cancel_url': reverse('finance_pembelian_bbm_list'),
        },
    )



@login_required
def bank_transaction_detail(request, uuid):
    require_tenant(request)
    transaction = get_object_or_404(
        BankTransaction.objects.filter(tenant=request.tenant, is_deleted=False).select_related(
            'bank_utama',
            'bank_utama__akun',
            'bank_tujuan',
            'bank_tujuan__akun',
            'jenis_transaksi',
            'jenis_transaksi__akun',
        ),
        uuid=uuid,
    )
    return render(
        request,
        'finance/bank_transaction_detail.html',
        {
            'title': f'Detail Transaksi Bank {transaction.no_bukti}',
            'object': transaction,
            'journal': transaction_journal(request, transaction),
            'cancel_url': reverse('finance_transaksi_bank_list'),
        },
    )


@login_required
def cash_advance_detail(request, uuid):
    require_tenant(request)
    transaction = get_object_or_404(
        EmployeeCashAdvance.objects.filter(tenant=request.tenant, is_deleted=False).select_related(
            'karyawan',
            'perkiraan_pinjaman',
            'perkiraan_kas',
            'bank',
        ),
        uuid=uuid,
    )
    return render(
        request,
        'finance/cash_advance_detail.html',
        {
            'title': f'Detail Kas Bon Karyawan {transaction.no_register}',
            'object': transaction,
            'journal': transaction_journal(request, transaction),
            'cancel_url': reverse('finance_kas_bon_list'),
        },
    )


@login_required
def cash_advance_payment_detail(request, uuid):
    require_tenant(request)
    transaction = get_object_or_404(
        EmployeeCashAdvancePayment.objects.filter(tenant=request.tenant, is_deleted=False).select_related(
            'kas_bon_karyawan',
            'kas_bon_karyawan__karyawan',
            'kas_bon_karyawan__perkiraan_pinjaman',
            'perkiraan_kas',
            'bank',
        ),
        uuid=uuid,
    )
    return render(
        request,
        'finance/cash_advance_payment_detail.html',
        {
            'title': f'Detail Pembayaran Kas Bon {transaction.no_register}',
            'object': transaction,
            'journal': transaction_journal(request, transaction),
            'cancel_url': reverse('finance_pembayaran_kas_bon_list'),
        },
    )


@login_required
def loan_debt_lookup(request):
    require_tenant(request)
    from django.db.models import Q
    from core.templatetags.crud_extras import format_money

    q = request.GET.get('q', '').strip()
    queryset = LoanDebt.objects.filter(
        tenant=request.tenant,
        is_deleted=False,
        status_lunas='Belum',
    ).select_related('pemberi_pinjaman')
    if q:
        queryset = queryset.filter(
            Q(no_register__icontains=q)
            | Q(pemberi_pinjaman__nama__icontains=q)
            | Q(keterangan__icontains=q)
        )
    results = []
    for debt in queryset.order_by('-tanggal', '-id')[:20]:
        saldo_val = format_money(debt.saldo)
        label = f"{debt.no_register} - {debt.pemberi_pinjaman.nama if debt.pemberi_pinjaman else ''} (Sisa: {saldo_val})"
        results.append({
            'id': debt.pk,
            'label': label,
            'no_register': debt.no_register,
            'nama': debt.pemberi_pinjaman.nama if debt.pemberi_pinjaman else '',
            'alamat': debt.pemberi_pinjaman.alamat if debt.pemberi_pinjaman else '',
            'saldo': saldo_val,
        })
    return JsonResponse({'results': results})


@login_required
def loan_debt_detail(request, uuid):
    require_tenant(request)
    transaction = get_object_or_404(
        LoanDebt.objects.filter(tenant=request.tenant, is_deleted=False).select_related(
            'pemberi_pinjaman',
            'perkiraan_hutang',
            'perkiraan_kas',
            'bank',
        ),
        uuid=uuid,
    )
    return render(
        request,
        'finance/loan_debt_detail.html',
        {
            'title': f'Detail Hutang Pinjaman {transaction.no_register}',
            'object': transaction,
            'journal': transaction_journal(request, transaction),
            'cancel_url': reverse('finance_hutang_pinjaman_list'),
        },
    )


@login_required
def loan_debt_payment_detail(request, uuid):
    require_tenant(request)
    transaction = get_object_or_404(
        LoanDebtPayment.objects.filter(tenant=request.tenant, is_deleted=False).select_related(
            'hutang_pinjaman',
            'hutang_pinjaman__pemberi_pinjaman',
            'hutang_pinjaman__perkiraan_hutang',
            'perkiraan_kas',
            'bank',
        ),
        uuid=uuid,
    )
    return render(
        request,
        'finance/loan_debt_payment_detail.html',
        {
            'title': f'Detail Pembayaran Hutang {transaction.no_register}',
            'object': transaction,
            'journal': transaction_journal(request, transaction),
            'cancel_url': reverse('finance_pembayaran_hutang_list'),
        },
    )
