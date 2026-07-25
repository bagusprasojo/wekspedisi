from django.db import models, transaction

from accounting.services import assign_number, ensure_last_day_of_month, ensure_next_closing_month, ensure_open_period, refresh_closing_snapshots
from core.models import TenantScopedModel


class Journal(TenantScopedModel):
    no_jurnal = models.CharField(max_length=50, blank=True)
    tanggal = models.DateField()
    transaksi_id = models.PositiveBigIntegerField(default=0)
    transaksi = models.CharField(max_length=150, blank=True)
    keterangan = models.TextField(blank=True)

    class Meta:
        ordering = ['-tanggal', '-id']
        constraints = [models.UniqueConstraint(fields=['tenant', 'no_jurnal'], name='uniq_journal_tenant_no_jurnal')]

    def __str__(self):
        return self.no_jurnal or 'Jurnal'

    @transaction.atomic
    def save_with_business_rules(self, user=None):
        old = type(self).objects.filter(pk=self.pk).first() if self.pk else None
        ensure_open_period(self.tenant, self.tanggal, old.tanggal if old else None)
        if not self.transaksi:
            self.transaksi = 'jurnal_memorial'
        assign_number(self, 'no_jurnal', 'JUR')
        self.save()
        return self

    def delete_with_business_rules(self, user=None):
        ensure_open_period(self.tenant, self.tanggal)
        self.lines.all().delete()
        self.delete()


class JournalLine(TenantScopedModel):
    journal = models.ForeignKey(Journal, related_name='lines', on_delete=models.CASCADE)
    perkiraan = models.ForeignKey('master.ChartOfAccount', related_name='journal_lines', on_delete=models.PROTECT)
    debet = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    kredit = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.journal} - {self.perkiraan}'


class ClosingPeriod(TenantScopedModel):
    tanggal = models.DateField()
    keterangan = models.TextField(blank=True)

    class Meta:
        ordering = ['-tanggal']
        constraints = [models.UniqueConstraint(fields=['tenant', 'tanggal'], name='uniq_closingperiod_tenant_tanggal')]

    def __str__(self):
        return str(self.tanggal)

    @transaction.atomic
    def save_with_business_rules(self, user=None):
        ensure_last_day_of_month(self.tanggal)
        ensure_next_closing_month(self.tenant, self.tanggal, current_pk=self.pk)
        self.save()
        refresh_closing_snapshots(self, user=user)
        return self

    def delete_with_business_rules(self, user=None):
        last = ClosingPeriod.objects.filter(tenant=self.tenant, is_deleted=False).order_by('-tanggal').first()
        if last and last.pk != self.pk:
            from accounting.services import BusinessRuleError
            raise BusinessRuleError('Hanya closing terakhir yang bisa dihapus.')
        self.bank_balances.all().delete()
        self.account_balances.all().delete()
        self.delete()


class ClosingBankBalance(TenantScopedModel):
    closing = models.ForeignKey(ClosingPeriod, related_name='bank_balances', on_delete=models.CASCADE)
    bank = models.ForeignKey('master.BankAccount', related_name='closing_balances', on_delete=models.PROTECT)
    tanggal = models.DateField()
    saldo_akhir = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        ordering = ['bank__nama_bank']


class ClosingAccountBalance(TenantScopedModel):
    closing = models.ForeignKey(ClosingPeriod, related_name='account_balances', on_delete=models.CASCADE)
    perkiraan = models.ForeignKey('master.ChartOfAccount', related_name='closing_balances', on_delete=models.PROTECT)
    saldo_normal = models.CharField(max_length=10)
    tanggal = models.DateField()
    debet = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    kredit = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        ordering = ['perkiraan__kode']



