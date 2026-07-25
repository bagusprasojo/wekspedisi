from django.contrib import admin

from .models import CustomerInvoice, CustomerInvoicePayment


@admin.register(CustomerInvoice)
class CustomerInvoiceAdmin(admin.ModelAdmin):
    list_display = ('no_invoice', 'tanggal', 'customer', 'total', 'pelunasan', 'status_lunas', 'tenant')
    list_filter = ('tenant', 'tanggal', 'status_lunas')
    search_fields = ('no_invoice', 'pekerjaan', 'keterangan', 'customer__nama')


@admin.register(CustomerInvoicePayment)
class CustomerInvoicePaymentAdmin(admin.ModelAdmin):
    list_display = ('no_register', 'tanggal', 'tagihan_customer', 'nominal_kas', 'pph', 'tenant')
    list_filter = ('tenant', 'tanggal')
    search_fields = ('no_register', 'keterangan', 'sumber_dana')
