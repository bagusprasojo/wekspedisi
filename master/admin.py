from django.contrib import admin

from .models import Armada, BankAccount, ChartOfAccount, StakeHolder, TenantConfig, TransactionType


@admin.register(StakeHolder)
class StakeHolderAdmin(admin.ModelAdmin):
    list_display = ('nama', 'jenis', 'tenant', 'telp')
    list_filter = ('jenis', 'tenant')
    search_fields = ('nama', 'alamat', 'telp')


@admin.register(ChartOfAccount)
class ChartOfAccountAdmin(admin.ModelAdmin):
    list_display = ('kode', 'nama', 'saldo_normal', 'tenant', 'parent', 'is_active')
    list_filter = ('saldo_normal', 'is_active', 'tenant')
    search_fields = ('kode', 'nama')


@admin.register(Armada)
class ArmadaAdmin(admin.ModelAdmin):
    list_display = ('nopol', 'kendaraan', 'pemilik', 'driver', 'tenant')
    list_filter = ('tenant',)
    search_fields = ('nopol', 'kendaraan', 'pemilik')


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ('nama_bank', 'no_rekening', 'atas_nama', 'is_kas', 'tenant')
    list_filter = ('is_kas', 'tenant')
    search_fields = ('nama_bank', 'no_rekening', 'atas_nama')


@admin.register(TransactionType)
class TransactionTypeAdmin(admin.ModelAdmin):
    list_display = ('kode', 'nama', 'akun', 'tenant')
    list_filter = ('tenant',)
    search_fields = ('kode', 'nama')


@admin.register(TenantConfig)
class TenantConfigAdmin(admin.ModelAdmin):
    list_display = ('kode', 'nilai', 'keterangan', 'tenant')
    list_filter = ('tenant',)
    search_fields = ('kode', 'nilai')
