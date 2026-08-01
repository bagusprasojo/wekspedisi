from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from accounting.models import Journal
from accounting.services import generated_transaction_key
from finance.models import BankTransaction, CashTransaction, EmployeeCashAdvance, EmployeeCashAdvancePayment, FuelPurchase
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
