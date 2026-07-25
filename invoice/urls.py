from django.urls import path

from core.crud import CrudConfig, build_crud_views
from invoice import views
from invoice.forms import CustomerInvoiceForm, CustomerInvoicePaymentForm
from invoice.models import CustomerInvoice, CustomerInvoicePayment

CONFIGS = {
    'invoice-customer': CrudConfig(model=CustomerInvoice, form_class=CustomerInvoiceForm, title='Invoice Customer', list_display=['no_invoice', 'customer.nama', 'tanggal', 'pekerjaan', 'nilai_pekerjaan', 'ppn_persen', 'ppn', 'total', 'pelunasan', 'saldo', 'status_lunas', 'keterangan', 'created_by'], list_labels={'no_invoice': 'No Invoice', 'customer.nama': 'Customer', 'nilai_pekerjaan': 'Nilai Pekerjaan', 'ppn_persen': 'PPN %', 'status_lunas': 'Status Lunas', 'created_by': 'Pc'}, search_fields=['no_invoice', 'pekerjaan', 'keterangan', 'customer__nama'], success_url_name='invoice_invoice_customer_list', detail_url_name='invoice_invoice_customer_detail', hide_list_edit=True, list_actions=[{'label': 'Invoice', 'url_name': 'invoice_invoice_customer_slip', 'target': '_blank'}, {'label': 'Kwitansi', 'url_name': 'invoice_invoice_customer_receipt', 'target': '_blank'}]),
    'pembayaran-invoice': CrudConfig(model=CustomerInvoicePayment, form_class=CustomerInvoicePaymentForm, title='Pembayaran Invoice', list_display=['no_register', 'tagihan_customer.no_invoice', 'tagihan_customer.customer.nama', 'tagihan_customer.customer.alamat', 'tanggal', 'sumber_dana', 'nominal_kas', 'pph_persen', 'pph', 'total_pembayaran', 'ppn', 'keterangan', 'created_by'], list_labels={'no_register': 'No Register', 'tagihan_customer.no_invoice': 'No Invoice', 'tagihan_customer.customer.nama': 'Nama', 'tagihan_customer.customer.alamat': 'Alamat', 'sumber_dana': 'Sumber Dana', 'nominal_kas': 'Nominal Kas/Bank', 'pph_persen': 'PPH Persen', 'total_pembayaran': 'Total', 'created_by': 'Pc'}, search_fields=['no_register', 'keterangan', 'sumber_dana', 'tagihan_customer__no_invoice', 'tagihan_customer__customer__nama', 'tagihan_customer__customer__alamat'], success_url_name='invoice_pembayaran_invoice_list', detail_url_name='invoice_pembayaran_invoice_detail', hide_list_edit=True, list_actions=[{'label': 'Kwitansi', 'url_name': 'invoice_pembayaran_invoice_receipt', 'target': '_blank'}]),
}

urlpatterns = [
    path('invoice-customer/<uuid:uuid>/', views.customer_invoice_detail, name='invoice_invoice_customer_detail'),
    path('invoice-customer/<uuid:uuid>/slip/', views.customer_invoice_slip, name='invoice_invoice_customer_slip'),
    path('invoice-customer/<uuid:uuid>/kwitansi/', views.customer_invoice_receipt, name='invoice_invoice_customer_receipt'),
    path('pembayaran-invoice/<uuid:uuid>/', views.customer_invoice_payment_detail, name='invoice_pembayaran_invoice_detail'),
    path('pembayaran-invoice/<uuid:uuid>/kwitansi/', views.customer_invoice_payment_receipt, name='invoice_pembayaran_invoice_receipt'),
]
for slug, config in CONFIGS.items():
    list_view, create_view, update_view, delete_view = build_crud_views(config)
    prefix = slug.replace('-', '_')
    urlpatterns += [
        path(f'{slug}/', list_view.as_view(), name=f'invoice_{prefix}_list'),
        path(f'{slug}/new/', create_view.as_view(), name=f'invoice_{prefix}_create'),
        path(f'{slug}/<uuid:uuid>/edit/', update_view.as_view(), name=f'invoice_{prefix}_update'),
        path(f'{slug}/<uuid:uuid>/delete/', delete_view.as_view(), name=f'invoice_{prefix}_delete'),
    ]
