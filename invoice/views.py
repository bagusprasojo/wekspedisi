from decimal import Decimal
from html import escape

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from accounting.models import Journal
from accounting.services import generated_transaction_key
from core.exporters import _money, _print_datetime_id, _tenant_logo_data_uri, _weasy_response
from invoice.models import CustomerInvoice, CustomerInvoicePayment, require_invoice_configs
from master.services import get_config_value


def require_tenant(request):
    if request.user.is_superuser and request.tenant is None:
        raise PermissionDenied('Superadmin tidak berada di tenant. Gunakan menu Platform.')
    if request.tenant is None:
        raise PermissionDenied('User belum terhubung ke tenant.')

def invoice_config_error_response(exc):
    message = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
    return HttpResponse(message, status=400, content_type='text/plain; charset=utf-8')

def _date_id(value):
    return value.strftime('%d %B %Y') if hasattr(value, 'strftime') else str(value or '')

def _wrapped(text, max_chars):
    words = str(text or '').replace('\r', '').split()
    lines = []
    current = ''
    for word in words:
        candidate = f'{current} {word}'.strip()
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
    if current:
        lines.append(current)
    return lines or ['']

def _company_header_html(tenant):
    logo = _tenant_logo_data_uri(tenant)
    logo_html = f'<img class="logo" src="{logo}">' if logo else '<div class="logo"></div>'
    return f'''
<div class="company-header">
{logo_html}
<div>
<div class="company">{escape(str(tenant.name or ""))}</div>
<div>Office : {escape(str(tenant.address or ""))}</div>
<div>Kab. {escape(str(tenant.city or ""))}, {escape(str(tenant.province or ""))}</div>
</div>
<div class="doc-date">Date: {escape(_print_datetime_id())}</div>
</div>'''

def _base_pdf_html(tenant, body, landscape=False):
    page_size = 'A4 landscape' if landscape else 'A4'
    return f'''<!doctype html>
<html><head><meta charset="utf-8">
<style>
@page {{ size: {page_size}; margin: 12mm 10mm; }}
body {{ font-family: Arial, sans-serif; font-size: 9pt; color: #000; }}
.company-header {{ display:grid; grid-template-columns:70px 1fr 135px; gap:10px; align-items:start; margin-bottom:12px; border-bottom:1px solid #000; padding-bottom:6px; }}
.logo {{ width:65px; height:60px; object-fit:contain; }}
.company {{ font-size:19pt; font-weight:700; line-height:1; margin-bottom:3px; }}
.doc-date {{ text-align:right; }}
.box {{ border:1px solid #000; }}
.grid {{ display:grid; gap:12px; }}
.two {{ grid-template-columns:1fr 210px; }}
.invoice-title {{ font-size:20pt; font-weight:700; text-align:center; border-bottom:1px solid #000; padding:6px 0; font-family:Verdana, sans-serif; }}
.pad {{ padding:10px; }}
.right {{ text-align:right; }}
.center {{ text-align:center; }}
.bold {{ font-weight:700; }}
.detail {{ min-height:480px; position:relative; padding:14px; margin-top:14px; }}
.top-amount-box {{ position:absolute; right:0; top:0; width:160px; height:80px; border-left:1px solid #000; border-bottom:1px solid #000; padding:10px; display:flex; justify-content:space-between; align-items:flex-start; }}
.summary-panel {{ position:absolute; right:14px; top:130px; width:280px; }}
.summary-row {{ display:grid; grid-template-columns:100px 24px 1fr; line-height:22px; align-items:center; }}
.summary-row.total-row {{ font-weight:700; border-top:1px solid #000; padding-top:4px; margin-top:6px; }}
.terbilang-box {{ position:absolute; left:14px; top:230px; width:calc(100% - 310px); }}
.footer-pay {{ position:absolute; left:14px; bottom:16px; width:300px; }}
.sign {{ position:absolute; right:20px; bottom:16px; width:220px; text-align:center; line-height:20px; }}
.sign .name-line {{ display:inline-block; border-bottom:1px solid #000; min-width:140px; margin-top:40px; font-weight:600; }}
</style></head><body>{body}</body></html>'''


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
    try:
        require_invoice_configs(request.tenant)
    except ValidationError as exc:
        return invoice_config_error_response(exc)
    invoice = get_object_or_404(
        CustomerInvoice.objects.filter(tenant=request.tenant, is_deleted=False).select_related('customer'),
        uuid=uuid,
    )
    dpp = (invoice.nilai_pekerjaan * Decimal('11') / Decimal('12')).quantize(Decimal('0.01'))
    payment_text = get_config_value(request.tenant, 'INVOICE_PAYMENT_TEXT')
    admin_name = get_config_value(request.tenant, 'INVOICE_ADMIN_NAME')
    return render(
        request,
        'invoice/customer_invoice_slip.html',
        {
            'object': invoice,
            'dpp': dpp,
            'payment_text': payment_text,
            'admin_name': admin_name,
            'tenant': request.tenant,
        },
    )

@login_required
def customer_invoice_receipt(request, uuid):
    require_tenant(request)
    try:
        require_invoice_configs(request.tenant)
    except ValidationError as exc:
        return invoice_config_error_response(exc)
    invoice = get_object_or_404(
        CustomerInvoice.objects.filter(tenant=request.tenant, is_deleted=False).select_related('customer'),
        uuid=uuid,
    )
    no_kwitansi = invoice.no_invoice.replace('INV', 'KWI')
    admin_name = get_config_value(request.tenant, 'INVOICE_ADMIN_NAME')
    return render(
        request,
        'invoice/customer_invoice_receipt.html',
        {
            'object': invoice,
            'no_kwitansi': no_kwitansi,
            'admin_name': admin_name,
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
