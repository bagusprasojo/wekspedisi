from django.contrib import admin

from .models import BankTransaction, CashTransaction, EmployeeCashAdvance, EmployeeCashAdvancePayment, FuelPurchase


@admin.register(CashTransaction)
class CashTransactionAdmin(admin.ModelAdmin):
    list_display = ('no_bukti', 'tanggal', 'akun_kas', 'nominal_masuk', 'nominal_keluar', 'tenant')
    list_filter = ('tenant', 'tanggal')
    search_fields = ('no_bukti', 'keterangan')


@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    list_display = ('no_bukti', 'tanggal', 'bank_utama', 'jenis_transaksi', 'debet', 'kredit', 'tenant')
    list_filter = ('tenant', 'tanggal')
    search_fields = ('no_bukti', 'uraian')


@admin.register(FuelPurchase)
class FuelPurchaseAdmin(admin.ModelAdmin):
    list_display = ('no_bukti', 'tanggal', 'armada', 'km_terakhir', 'km_sekarang', 'nominal_bbm', 'tenant')
    list_filter = ('tenant', 'tanggal')
    search_fields = ('no_bukti', 'keterangan', 'armada__nopol')


@admin.register(EmployeeCashAdvance)
class EmployeeCashAdvanceAdmin(admin.ModelAdmin):
    list_display = ('no_register', 'tanggal', 'karyawan', 'nominal', 'pelunasan', 'status_lunas', 'tenant')
    list_filter = ('tenant', 'tanggal', 'status_lunas')
    search_fields = ('no_register', 'keterangan', 'karyawan__nama')


@admin.register(EmployeeCashAdvancePayment)
class EmployeeCashAdvancePaymentAdmin(admin.ModelAdmin):
    list_display = ('no_register', 'tanggal', 'kas_bon_karyawan', 'nominal', 'tenant')
    list_filter = ('tenant', 'tanggal')
    search_fields = ('no_register', 'keterangan')
