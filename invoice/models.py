from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Sum

from accounting.services import assign_number, delete_generated_journal, ensure_open_period, refresh_journal
from core.models import TenantScopedModel
from core.services import next_invoice_number


ZERO = Decimal('0')
LEGACY_PPN_PERCENT = Decimal('11')
SATUAN = [
    '', 'Satu', 'Dua', 'Tiga', 'Empat', 'Lima', 'Enam', 'Tujuh', 'Delapan', 'Sembilan', 'Sepuluh', 'Sebelas',
]

def terbilang(angka):
    angka = int(angka)
    if angka < 12:
        return SATUAN[angka]
    if angka < 20:
        return f'{SATUAN[angka - 10]} Belas'
    if angka < 100:
        return f'{SATUAN[angka // 10]} Puluh {terbilang(angka % 10)}'
    if angka < 200:
        return f'Seratus {terbilang(angka - 100)}'
    if angka < 1000:
        return f'{SATUAN[angka // 100]} Ratus {terbilang(angka % 100)}'
    if angka < 2000:
        return f'Seribu {terbilang(angka - 1000)}'
    if angka < 1000000:
        return f'{terbilang(angka // 1000)} Ribu {terbilang(angka % 1000)}'
    if angka < 1000000000:
        return f'{terbilang(angka // 1000000)} Juta {terbilang(angka % 1000000)}'
    if angka < 1000000000000:
        return f'{terbilang(angka // 1000000000)} Miliar {terbilang(angka % 1000000000)}'
    return 'Angka terlalu besar'


class CustomerInvoice(TenantScopedModel):
    class StatusLunas(models.TextChoices):
        BELUM = 'Belum', 'Belum'
        LUNAS = 'Lunas', 'Lunas'

    customer = models.ForeignKey('master.StakeHolder', related_name='invoices', on_delete=models.PROTECT)
    no_invoice = models.CharField(max_length=50, blank=True)
    tanggal = models.DateField()
    pekerjaan = models.TextField(blank=True)
    nilai_pekerjaan = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    ppn_persen = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    ppn = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    terbilang = models.TextField(blank=True)
    pelunasan = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status_lunas = models.CharField(max_length=10, choices=StatusLunas.choices, default=StatusLunas.BELUM)
    keterangan = models.TextField(blank=True)
    perkiraan_piutang = models.ForeignKey('master.ChartOfAccount', related_name='customer_invoices', on_delete=models.PROTECT)

    class Meta:
        ordering = ['-tanggal', '-id']
        constraints = [models.UniqueConstraint(fields=['tenant', 'no_invoice'], name='uniq_customerinvoice_tenant_no_invoice')]

    def __str__(self):
        return self.no_invoice or 'Invoice Customer'

    @property
    def saldo(self):
        return self.total - self.pelunasan

    @transaction.atomic
    def save_with_business_rules(self, user=None):
        from master.services import get_config_account
        old = type(self).objects.filter(pk=self.pk).first() if self.pk else None
        ensure_open_period(self.tenant, self.tanggal, old.tanggal if old else None)
        if old and old.pelunasan > ZERO:
            raise ValidationError('Invoice tidak bisa diubah karena sudah ada pembayaran.')
        if not self.customer:
            raise ValidationError('Customer belum dipilih.')
        if not self.pekerjaan.strip():
            raise ValidationError('Nama pekerjaan belum diisi.')
        if self.nilai_pekerjaan <= ZERO:
            raise ValidationError('Nilai pekerjaan belum diisi.')
        self.ppn_persen = LEGACY_PPN_PERCENT
        self.perkiraan_piutang = get_config_account(self.tenant, 'PIUTANG_JASA_ID')
        if not self.no_invoice:
            self.no_invoice = next_invoice_number(self.tenant, self.tanggal)
        self.ppn = (self.nilai_pekerjaan * self.ppn_persen / Decimal('100')).quantize(Decimal('0.01'))
        if self.ppn <= ZERO:
            raise ValidationError('Nilai PPN belum diisi.')
        self.total = self.nilai_pekerjaan + self.ppn
        self.terbilang = f'{terbilang(self.total).strip()} Rupiah'
        self.status_lunas = self.StatusLunas.LUNAS if self.total <= self.pelunasan else self.StatusLunas.BELUM
        pendapatan = get_config_account(self.tenant, 'AKUN_PENDAPATAN_JASA')
        ppn_account = get_config_account(self.tenant, 'AKUN_PPN_ID') if self.ppn > ZERO else None
        self.save()
        lines = [
            {'account': self.perkiraan_piutang, 'debet': self.total},
            {'account': pendapatan, 'kredit': self.nilai_pekerjaan},
        ]
        if self.ppn > ZERO:
            lines.append({'account': ppn_account, 'kredit': self.ppn})
        refresh_journal(obj=self, no_jurnal=self.no_invoice, tanggal=self.tanggal, keterangan=self.keterangan, lines=lines, user=user)
        return self

    def delete_with_business_rules(self, user=None):
        ensure_open_period(self.tenant, self.tanggal)
        if self.pelunasan > ZERO:
            raise ValidationError('Invoice tidak bisa dihapus karena sudah ada pembayaran.')
        delete_generated_journal(self)
        self.delete()


class CustomerInvoicePayment(TenantScopedModel):
    no_register = models.CharField(max_length=50, blank=True)
    tagihan_customer = models.ForeignKey(CustomerInvoice, related_name='payments', on_delete=models.PROTECT)
    tanggal = models.DateField()
    nominal_kas = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    pph = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    pph_persen = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    perkiraan_kas = models.ForeignKey('master.ChartOfAccount', related_name='invoice_payments_cash', on_delete=models.PROTECT)
    bank = models.ForeignKey('master.BankAccount', null=True, blank=True, related_name='invoice_payments', on_delete=models.PROTECT)
    perkiraan_pph = models.ForeignKey('master.ChartOfAccount', null=True, blank=True, related_name='invoice_payments_pph', on_delete=models.PROTECT)
    keterangan = models.TextField(blank=True)
    sumber_dana = models.CharField(max_length=100, blank=True)
    terbilang = models.TextField(blank=True)
    ppn = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        ordering = ['-tanggal', '-id']
        constraints = [models.UniqueConstraint(fields=['tenant', 'no_register'], name='uniq_invoicepayment_tenant_no_register')]

    def __str__(self):
        return self.no_register or 'Pembayaran Invoice'

    @property
    def total_pembayaran(self):
        return self.nominal_kas + self.pph

    @transaction.atomic
    def save_with_business_rules(self, user=None):
        from master.services import get_config_account
        old = type(self).objects.filter(pk=self.pk).first() if self.pk else None
        ensure_open_period(self.tenant, self.tanggal, old.tanggal if old else None)
        if not self.tagihan_customer:
            raise ValidationError('Invoice belum dipilih.')
        if not self.bank:
            raise ValidationError('Bank belum dipilih.')
        if not self.bank.akun:
            raise ValidationError('Akun pada Kas/Bank wajib diisi di master Bank/Kas.')
        if self.nominal_kas <= ZERO:
            raise ValidationError('Nominal belum diisi.')
        if self.pph < ZERO:
            raise ValidationError('PPH tidak boleh minus.')
        paid_before_this = self.tagihan_customer.payments.filter(is_deleted=False).exclude(pk=self.pk).aggregate(total=Sum('nominal_kas') + Sum('pph'))['total'] or ZERO
        available_balance = self.tagihan_customer.total - paid_before_this
        if self.total_pembayaran > available_balance:
            raise ValidationError('Pembayaran melebihi saldo piutang.')
        assign_number(self, 'no_register', 'BKM')
        self.ppn = (self.total_pembayaran / Decimal('111') * Decimal('11')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        if self.tagihan_customer.ppn > ZERO and self.ppn <= ZERO:
            raise ValidationError('PPN belum diisi.')
        self.perkiraan_kas = self.bank.akun
        self.sumber_dana = str(self.bank)
        self.terbilang = f'{terbilang(self.nominal_kas).strip()} Rupiah'
        if self.pph > ZERO and not self.perkiraan_pph:
            self.perkiraan_pph = get_config_account(self.tenant, 'AKUN_PPH_ID', required=False)
        if self.pph > ZERO and not self.perkiraan_pph:
            raise ValidationError('Akun PPH wajib diisi jika PPH lebih dari 0.')
        self.save()
        lines = [{'account': self.perkiraan_kas, 'debet': self.nominal_kas}]
        if self.pph > ZERO:
            lines.append({'account': self.perkiraan_pph, 'debet': self.pph})
        lines.append({'account': self.tagihan_customer.perkiraan_piutang, 'kredit': self.total_pembayaran})
        refresh_journal(obj=self, no_jurnal=self.no_register, tanggal=self.tanggal, keterangan=self.keterangan, lines=lines, user=user)
        refresh_invoice_status(self.tagihan_customer)
        if old and old.tagihan_customer_id != self.tagihan_customer_id:
            refresh_invoice_status(old.tagihan_customer)
        return self

    def delete_with_business_rules(self, user=None):
        ensure_open_period(self.tenant, self.tanggal)
        invoice = self.tagihan_customer
        delete_generated_journal(self)
        self.delete()
        refresh_invoice_status(invoice)


def refresh_invoice_status(invoice):
    total = invoice.payments.filter(is_deleted=False).aggregate(total=Sum('nominal_kas') + Sum('pph'))['total'] or ZERO
    invoice.pelunasan = total
    invoice.status_lunas = CustomerInvoice.StatusLunas.LUNAS if invoice.total <= total else CustomerInvoice.StatusLunas.BELUM
    invoice.save(update_fields=['pelunasan', 'status_lunas', 'updated_at'])


