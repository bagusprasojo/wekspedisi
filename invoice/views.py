from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from accounting.models import Journal
from accounting.services import generated_transaction_key
from invoice.models import CustomerInvoice, CustomerInvoicePayment


def require_tenant(request):
    if request.user.is_superuser and request.tenant is None:
        raise PermissionDenied('Superadmin tidak berada di tenant. Gunakan menu Platform.')
    if request.tenant is None:
        raise PermissionDenied('User belum terhubung ke tenant.')


@login_required
def customer_invoice_detail(request, uuid):
    require_tenant(request)
    invoice = get_object_or_404(
        CustomerInvoice.objects.filter(tenant=request.tenant, is_deleted=False).select_related(
            'customer',
            'perkiraan_piutang',
        ),
        uuid=uuid,
    )
    journal = Journal.objects.filter(
        tenant=request.tenant,
        is_deleted=False,
        transaksi_id=invoice.pk,
        transaksi=generated_transaction_key(invoice),
    ).prefetch_related('lines__perkiraan').first()
    return render(
        request,
        'invoice/customer_invoice_detail.html',
        {
            'title': f'Detail Invoice Customer {invoice.no_invoice}',
            'object': invoice,
            'journal': journal,
            'cancel_url': reverse('invoice_invoice_customer_list'),
        },
    )

@login_required
def customer_invoice_slip(request, uuid):
    require_tenant(request)
    invoice = get_object_or_404(
        CustomerInvoice.objects.filter(tenant=request.tenant, is_deleted=False).select_related('customer'),
        uuid=uuid,
    )
    return render(
        request,
        'invoice/customer_invoice_slip.html',
        {
            'object': invoice,
            'tenant': request.tenant,
            'dpp': (invoice.nilai_pekerjaan * Decimal('11') / Decimal('12')).quantize(Decimal('0.01')),
        },
    )

@login_required
def customer_invoice_receipt(request, uuid):
    require_tenant(request)
    invoice = get_object_or_404(
        CustomerInvoice.objects.filter(tenant=request.tenant, is_deleted=False).select_related('customer'),
        uuid=uuid,
    )
    return render(
        request,
        'invoice/customer_invoice_receipt.html',
        {
            'object': invoice,
            'no_kwitansi': invoice.no_invoice.replace('INV', 'KWI'),
            'tenant': request.tenant,
        },
    )

@login_required
def customer_invoice_payment_receipt(request, uuid):
    require_tenant(request)
    payment = get_object_or_404(
        CustomerInvoicePayment.objects.filter(tenant=request.tenant, is_deleted=False).select_related(
            'tagihan_customer__customer',
        ),
        uuid=uuid,
    )
    return render(
        request,
        'invoice/customer_invoice_payment_receipt.html',
        {
            'object': payment,
            'invoice': payment.tagihan_customer,
            'no_kwitansi': payment.tagihan_customer.no_invoice.replace('INV', 'KWI'),
            'tenant': request.tenant,
        },
    )

@login_required
def customer_invoice_payment_detail(request, uuid):
    require_tenant(request)
    payment = get_object_or_404(
        CustomerInvoicePayment.objects.filter(tenant=request.tenant, is_deleted=False).select_related(
            'tagihan_customer__customer',
            'perkiraan_kas',
            'perkiraan_pph',
            'bank',
        ),
        uuid=uuid,
    )
    journal = Journal.objects.filter(
        tenant=request.tenant,
        is_deleted=False,
        transaksi_id=payment.pk,
        transaksi=generated_transaction_key(payment),
    ).prefetch_related('lines__perkiraan').first()
    return render(
        request,
        'invoice/customer_invoice_payment_detail.html',
        {
            'title': f'Detail Pembayaran Invoice {payment.no_register}',
            'object': payment,
            'journal': journal,
            'cancel_url': reverse('invoice_pembayaran_invoice_list'),
        },
    )
