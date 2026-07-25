from django.contrib import admin

from .models import ClosingAccountBalance, ClosingBankBalance, ClosingPeriod, Journal, JournalLine


class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 0


@admin.register(Journal)
class JournalAdmin(admin.ModelAdmin):
    list_display = ('no_jurnal', 'tanggal', 'transaksi', 'tenant')
    list_filter = ('tanggal', 'transaksi', 'tenant')
    search_fields = ('no_jurnal', 'keterangan')
    inlines = [JournalLineInline]


@admin.register(ClosingPeriod)
class ClosingPeriodAdmin(admin.ModelAdmin):
    list_display = ('tanggal', 'tenant', 'keterangan')
    list_filter = ('tenant',)
    search_fields = ('keterangan',)


@admin.register(ClosingBankBalance)
class ClosingBankBalanceAdmin(admin.ModelAdmin):
    list_display = ('closing', 'bank', 'saldo_akhir', 'tenant')
    list_filter = ('tenant', 'closing')


@admin.register(ClosingAccountBalance)
class ClosingAccountBalanceAdmin(admin.ModelAdmin):
    list_display = ('closing', 'perkiraan', 'saldo_normal', 'debet', 'kredit', 'tenant')
    list_filter = ('tenant', 'closing', 'saldo_normal')
