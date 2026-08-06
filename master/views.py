from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from master.models import Armada, BankAccount, StakeHolder


def require_tenant(request):
    if request.user.is_superuser and request.tenant is None:
        raise PermissionDenied('Superadmin tidak berada di tenant. Gunakan menu Platform.')
    if request.tenant is None:
        raise PermissionDenied('User belum terhubung ke tenant.')


@login_required
def stakeholder_lookup(request):
    require_tenant(request)
    q = request.GET.get('q', '').strip()
    jenis = request.GET.get('jenis', '').strip()
    queryset = StakeHolder.objects.filter(tenant=request.tenant, is_deleted=False)
    if jenis:
        queryset = queryset.filter(jenis=jenis)
    if q:
        queryset = queryset.filter(Q(nama__icontains=q) | Q(telp__icontains=q))
    results = [
        {'id': stakeholder.pk, 'label': str(stakeholder)}
        for stakeholder in queryset.order_by('nama')[:20]
    ]
    return JsonResponse({'results': results})

@login_required
def bank_detail(request, uuid):
    require_tenant(request)
    bank = get_object_or_404(
        BankAccount.objects.filter(tenant=request.tenant, is_deleted=False).select_related('akun'),
        uuid=uuid,
    )
    return render(
        request,
        'master/bank_detail.html',
        {
            'title': f'Detail Bank/Kas {bank.nama_bank}',
            'object': bank,
            'cancel_url': reverse('master_bank_list'),
        },
    )

@login_required
def customer_detail(request, uuid):
    require_tenant(request)
    customer = get_object_or_404(
        StakeHolder.objects.filter(
            tenant=request.tenant,
            is_deleted=False,
            jenis=StakeHolder.StakeHolderType.CUSTOMER,
        ),
        uuid=uuid,
    )
    return render(
        request,
        'master/customer_detail.html',
        {
            'title': f'Detail Customer {customer.nama}',
            'object': customer,
            'cancel_url': reverse('master_customer_list'),
        },
    )

@login_required
def karyawan_detail(request, uuid):
    require_tenant(request)
    karyawan = get_object_or_404(
        StakeHolder.objects.filter(
            tenant=request.tenant,
            is_deleted=False,
            jenis=StakeHolder.StakeHolderType.KARYAWAN,
        ),
        uuid=uuid,
    )
    return render(
        request,
        'master/karyawan_detail.html',
        {
            'title': f'Detail Karyawan {karyawan.nama}',
            'object': karyawan,
            'cancel_url': reverse('master_karyawan_list'),
        },
    )

@login_required
def armada_detail(request, uuid):
    require_tenant(request)
    armada = get_object_or_404(
        Armada.objects.filter(tenant=request.tenant, is_deleted=False).select_related('driver'),
        uuid=uuid,
    )
    return render(
        request,
        'master/armada_detail.html',
        {
            'title': f'Detail Armada {armada.nopol}',
            'object': armada,
            'cancel_url': reverse('master_armada_list'),
        },
    )
