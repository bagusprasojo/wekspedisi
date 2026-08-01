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
.company-header {{ display:grid; grid-template-columns:70px 1fr 135px; gap:10px; align-items:start; margin-bottom:18px; }}
.logo {{ width:65px; height:60px; object-fit:contain; }}
.company {{ font-size:19pt; font-weight:700; line-height:1; margin-bottom:3px; }}
.doc-date {{ text-align:right; }}
.box {{ border:1px solid #000; }}
.grid {{ display:grid; gap:10px; }}
.two {{ grid-template-columns:1fr 196px; }}
.invoice-title {{ font-size:20pt; font-weight:700; text-align:center; border-bottom:1px solid #000; padding:7px 0; }}
.pad {{ padding:10px; }}
.right {{ text-align:right; }}
.center {{ text-align:center; }}
.bold {{ font-weight:700; }}
.money-table {{ width:100%; border-collapse:collapse; }}
.money-table td {{ padding:4px 0; }}
.detail {{ min-height:370px; position:relative; padding:12px; }}
.amounts {{ position:absolute; right:0; top:0; width:146px; height:189px; border-left:1px solid #000; border-bottom:1px solid #000; padding:12px 6px; }}
.amount-row {{ display:grid; grid-template-columns:1fr 22px 1fr; margin-bottom:10px; }}
.footer-pay {{ position:absolute; left:12px; bottom:12px; width:270px; }}
.sign {{ position:absolute; right:30px; bottom:12px; width:190px; text-align:center; }}
.receipt-page {{ border:1px solid #000; padding:12px 12px 20px; min-height:430px; }}
.receipt-title {{ border:1px solid #000; font-size:20pt; font-weight:700; text-align:center; padding:8px; margin-left:75px; }}
.receipt-body {{ border:1px solid #000; margin:12px 0 0 70px; padding:18px 14px; min-height:340px; }}
.receipt-row {{ display:grid; grid-template-columns:130px 18px 1fr; gap:4px; margin-bottom:14px; font-size:11pt; }}
.receipt-box {{ border:1px solid #000; padding:6px; font-weight:700; }}
.receipt-total {{ border-top:1px solid #000; border-bottom:1px solid #000; display:flex; justify-content:space-between; width:310px; padding:12px 0; font-size:16pt; margin-top:20px; }}
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
    pekerjaan = '<br>'.join(escape(line) for line in _wrapped(invoice.pekerjaan, 62)[:2])
    terbilang = '<br>'.join(escape(line) for line in _wrapped(invoice.terbilang, 48)[:2])
    payment_lines = '<br>'.join(escape(line) for line in str(payment_text).splitlines()[:2])
    body = f'''
{_company_header_html(request.tenant)}
<div class="grid two">
<div class="box pad">
<div>Kepada</div>
<div class="bold" style="font-size:10pt;margin-top:8px">{escape(str(invoice.customer.nama or ""))}</div>
<div style="margin-top:8px">{escape(str(invoice.customer.alamat or ""))}</div>
</div>
<div class="box">
<div class="invoice-title">Invoice</div>
<div class="pad">
<div>No Invoice : {escape(invoice.no_invoice)}</div>
<div style="margin-top:10px">Tanggal : {escape(_date_id(invoice.tanggal))}</div>
</div>
</div>
</div>
<div class="box detail" style="margin-top:74px">
<div>{pekerjaan}</div>
<div class="right" style="margin-right:153px;margin-top:-15px">Rp&nbsp;&nbsp;{escape(_money(invoice.nilai_pekerjaan))}</div>
<div class="amounts">
<div class="amount-row"><span>Sub Total</span><span>Rp</span><span class="right">{escape(_money(invoice.nilai_pekerjaan))}</span></div>
<div class="amount-row"><span>DPP</span><span>Rp</span><span class="right">{escape(_money(dpp))}</span></div>
<div class="amount-row"><span>PPN 12%</span><span>Rp</span><span class="right">{escape(_money(invoice.ppn))}</span></div>
<div style="border-top:1px solid #000;margin:12px -6px 14px"></div>
<div class="amount-row bold"><span>Total</span><span>Rp</span><span class="right">{escape(_money(invoice.total))}</span></div>
</div>
<div style="position:absolute;left:12px;top:178px">
<div>Terbilag :</div>
<div class="bold" style="font-size:10pt;margin-top:10px">{terbilang}</div>
</div>
<div class="footer-pay">
<div>Pembayaran Melalui :</div>
<div style="margin-top:10px">{payment_lines}</div>
</div>
<div class="sign">
<div>Sukoharjo, {escape(_date_id(invoice.tanggal))}</div>
<div style="margin-top:14px">{escape(str(request.tenant.name or ""))}</div>
<div style="margin-top:46px;border-bottom:1px solid #000">{escape(str(admin_name))}</div>
<div>Admin</div>
</div>
</div>'''
    return _weasy_response(f'invoice-{invoice.no_invoice}.pdf', _base_pdf_html(request.tenant, body), inline=True)

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
    receipt_rows = [
        ('Nomor', no_kwitansi, False),
        ('Telah terima dari', invoice.customer.nama, False),
        ('Uang sejumlah', invoice.terbilang, True),
        ('Untuk pembayaran', f'{invoice.pekerjaan}\nNo Invoice : {invoice.no_invoice}', True),
    ]
    rows_html = []
    for label, value, boxed in receipt_rows:
        value_html = '<br>'.join(escape(line) for line in _wrapped(value, 60)[:4])
        if boxed:
            value_html = f'<div class="receipt-box">{value_html}</div>'
        else:
            value_html = f'<div class="bold">{value_html}</div>'
        rows_html.append(f'<div class="receipt-row"><div>{escape(label)}</div><div>:</div>{value_html}</div>')
    body = f'''
<div class="receipt-page">
<div class="receipt-title">KWITANSI</div>
<div class="receipt-body">
{''.join(rows_html)}
<div style="display:grid;grid-template-columns:1fr 210px;gap:20px;margin-top:18px">
<div>
<div class="receipt-total"><span>Terbilang Rp</span><strong>{escape(_money(invoice.total))}</strong></div>
</div>
<div class="center bold">
<div>Sukoharjo, {escape(_date_id(invoice.tanggal))}</div>
<div style="margin-top:16px">{escape(str(request.tenant.name or ""))}</div>
<div style="margin-top:70px;border-bottom:1px solid #000">{escape(str(admin_name))}</div>
</div>
</div>
</div>
</div>'''
    return _weasy_response(f'kwitansi-{no_kwitansi}.pdf', _base_pdf_html(request.tenant, body, landscape=True), inline=True)

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
