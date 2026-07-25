from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Sum

from accounting.services import assign_number, delete_generated_journal, ensure_open_period, refresh_journal
from core.models import TenantScopedModel


ZERO = Decimal('0')


class CashTransaction(TenantScopedModel):
    no_bukti = models.CharField(max_length=50, blank=True)
    tanggal = models.DateField()
    akun_kas = models.ForeignKey('master.ChartOfAccount', related_name='cash_account_transactions', on_delete=models.PROTECT)
    akun_transaksi = models.ForeignKey('master.ChartOfAccount', related_name='cash_offset_transactions', on_delete=models.PROTECT)
    nominal_masuk = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    nominal_keluar = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    keterangan = models.TextField(blank=True)
    armada = models.ForeignKey('master.Armada', null=True, blank=True, related_name='cash_transactions', on_delete=models.PROTECT)
    bank = models.ForeignKey('master.BankAccount', related_name='cash_transactions', on_delete=models.PROTECT)

    class Meta:
        ordering = ['-tanggal', '-id']
        constraints = [models.UniqueConstraint(fields=['tenant', 'no_bukti'], name='uniq_cashtransaction_tenant_no_bukti')]

    def __str__(self):
        return self.no_bukti or 'Transaksi Kas'

    @transaction.atomic
    def save_with_business_rules(self, user=None):
        old = type(self).objects.filter(pk=self.pk).first() if self.pk else None
        ensure_open_period(self.tenant, self.tanggal, old.tanggal if old else None)
        if not self.bank:
            raise ValidationError('Kas/Bank wajib dipilih.')
        if not self.bank.akun:
            raise ValidationError('Akun pada Kas/Bank wajib diisi di master Bank/Kas.')
        self.akun_kas = self.bank.akun
        if self.nominal_masuk <= ZERO and self.nominal_keluar <= ZERO:
            raise ValidationError('Nominal masuk atau keluar harus diisi.')
        if self.nominal_masuk > ZERO and self.nominal_keluar > ZERO:
            raise ValidationError('Nominal masuk dan keluar tidak boleh diisi bersamaan.')
        assign_number(self, 'no_bukti', 'KAS')
        self.save()
        amount = self.nominal_masuk if self.nominal_masuk > ZERO else self.nominal_keluar
        if self.nominal_masuk > ZERO:
            lines = [{'account': self.akun_kas, 'debet': amount}, {'account': self.akun_transaksi, 'kredit': amount}]
        else:
            lines = [{'account': self.akun_transaksi, 'debet': amount}, {'account': self.akun_kas, 'kredit': amount}]
        refresh_journal(obj=self, no_jurnal=self.no_bukti, tanggal=self.tanggal, keterangan=self.keterangan, lines=lines, user=user)
        return self

    def delete_with_business_rules(self, user=None):
        ensure_open_period(self.tenant, self.tanggal)
        delete_generated_journal(self)
        self.delete()


class BankTransaction(TenantScopedModel):
    no_bukti = models.CharField(max_length=50, blank=True)
    tanggal = models.DateField()
    bank_utama = models.ForeignKey('master.BankAccount', related_name='bank_transactions_primary', on_delete=models.PROTECT)
    jenis_transaksi = models.ForeignKey('master.TransactionType', related_name='bank_transactions', on_delete=models.PROTECT)
    debet = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    kredit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    bank_tujuan = models.ForeignKey('master.BankAccount', null=True, blank=True, related_name='bank_transactions_target', on_delete=models.PROTECT)
    akun_utama = models.ForeignKey('master.ChartOfAccount', null=True, blank=True, related_name='bank_transactions_primary', on_delete=models.PROTECT)
    akun_tujuan = models.ForeignKey('master.ChartOfAccount', null=True, blank=True, related_name='bank_transactions_target', on_delete=models.PROTECT)
    biaya_adm_bank = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    uraian = models.TextField(blank=True)

    class Meta:
        ordering = ['-tanggal', '-id']
        constraints = [models.UniqueConstraint(fields=['tenant', 'no_bukti'], name='uniq_banktransaction_tenant_no_bukti')]

    def __str__(self):
        return self.no_bukti or 'Transaksi Bank'

    @transaction.atomic
    def save_with_business_rules(self, user=None):
        old = type(self).objects.filter(pk=self.pk).first() if self.pk else None
        ensure_open_period(self.tenant, self.tanggal, old.tanggal if old else None)
        if not self.bank_utama.akun:
            raise ValidationError('Akun pada bank utama wajib diisi di master Bank/Kas.')
        if not self.jenis_transaksi.akun:
            raise ValidationError('Akun pada jenis transaksi wajib diisi di master Jenis Transaksi.')
        kode = self.jenis_transaksi.kode
        if kode in {'01', '03'}:
            self.debet = ZERO
            if self.kredit <= ZERO:
                raise ValidationError('Nilai kredit belum diisi.')
        elif kode in {'02', '08'}:
            self.kredit = ZERO
            if self.debet <= ZERO:
                raise ValidationError('Nilai debet belum diisi.')
        elif kode in {'04', '06'}:
            if self.kredit <= ZERO and self.debet <= ZERO:
                raise ValidationError('Nilai debet/kredit belum diisi.')
        elif kode == '20':
            self.kredit = ZERO
            if self.debet <= ZERO:
                raise ValidationError('Debet wajib lebih dari 0 untuk transfer antar bank.')
            if not self.bank_tujuan:
                raise ValidationError('Bank tujuan wajib diisi untuk transfer antar bank.')
            if self.biaya_adm_bank <= ZERO:
                raise ValidationError('Biaya adm bank tujuan belum diisi.')
            if not self.bank_tujuan.akun:
                raise ValidationError('Akun pada bank tujuan wajib diisi di master Bank/Kas.')
            amount = self.debet
            lines = [
                {'account': self.bank_tujuan.akun, 'debet': amount},
                {'account': self.bank_utama.akun, 'kredit': amount + self.biaya_adm_bank},
                {'account': self.jenis_transaksi.akun, 'debet': self.biaya_adm_bank},
            ]
        if kode != '20':
            if self.kredit > ZERO:
                lines = [{'account': self.bank_utama.akun, 'debet': self.kredit}, {'account': self.jenis_transaksi.akun, 'kredit': self.kredit}]
            elif self.debet > ZERO:
                lines = [{'account': self.jenis_transaksi.akun, 'debet': self.debet}, {'account': self.bank_utama.akun, 'kredit': self.debet}]
            else:
                raise ValidationError('Debet atau kredit harus diisi.')
        assign_number(self, 'no_bukti', 'BNK')
        self.save()
        refresh_journal(obj=self, no_jurnal=self.no_bukti, tanggal=self.tanggal, keterangan=self.uraian, lines=lines, user=user)
        return self

    def delete_with_business_rules(self, user=None):
        ensure_open_period(self.tenant, self.tanggal)
        delete_generated_journal(self)
        self.delete()


class FuelPurchase(TenantScopedModel):
    no_bukti = models.CharField(max_length=50, blank=True)
    armada = models.ForeignKey('master.Armada', related_name='fuel_purchases', on_delete=models.PROTECT)
    tanggal = models.DateField()
    km_terakhir = models.PositiveIntegerField(default=0)
    km_sekarang = models.PositiveIntegerField(default=0)
    nominal_bbm = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    keterangan = models.TextField(blank=True)
    driver = models.ForeignKey('master.StakeHolder', null=True, blank=True, related_name='fuel_purchases_as_driver', on_delete=models.PROTECT)
    bank = models.ForeignKey('master.BankAccount', related_name='fuel_purchases', on_delete=models.PROTECT)

    class Meta:
        ordering = ['-tanggal', '-id']
        constraints = [models.UniqueConstraint(fields=['tenant', 'no_bukti'], name='uniq_fuelpurchase_tenant_no_bukti')]

    def __str__(self):
        return self.no_bukti or 'Pembelian BBM'

    @property
    def jarak_tempuh(self):
        return self.km_sekarang - self.km_terakhir

    @transaction.atomic
    def save_with_business_rules(self, user=None):
        from master.services import get_config_account
        old = type(self).objects.filter(pk=self.pk).first() if self.pk else None
        ensure_open_period(self.tenant, self.tanggal, old.tanggal if old else None)
        assign_number(self, 'no_bukti', 'BBM')
        akun_bbm = get_config_account(self.tenant, 'AKUN_BBM_ID')
        if not self.bank.akun:
            raise ValidationError('Akun pada bank wajib diisi di master Bank/Kas.')
        self.save()
        lines = [{'account': akun_bbm, 'debet': self.nominal_bbm}, {'account': self.bank.akun, 'kredit': self.nominal_bbm}]
        refresh_journal(obj=self, no_jurnal=self.no_bukti, tanggal=self.tanggal, keterangan=self.keterangan, lines=lines, user=user)
        return self

    def delete_with_business_rules(self, user=None):
        ensure_open_period(self.tenant, self.tanggal)
        delete_generated_journal(self)
        self.delete()


class EmployeeCashAdvance(TenantScopedModel):
    class StatusLunas(models.TextChoices):
        BELUM = 'Belum', 'Belum'
        LUNAS = 'Lunas', 'Lunas'

    no_register = models.CharField(max_length=50, blank=True)
    tanggal = models.DateField()
    karyawan = models.ForeignKey('master.StakeHolder', related_name='cash_advances', on_delete=models.PROTECT)
    perkiraan_pinjaman = models.ForeignKey('master.ChartOfAccount', related_name='cash_advances_loan', on_delete=models.PROTECT)
    perkiraan_kas = models.ForeignKey('master.ChartOfAccount', related_name='cash_advances_cash', on_delete=models.PROTECT)
    nominal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    keterangan = models.TextField(blank=True)
    bank = models.ForeignKey('master.BankAccount', null=True, blank=True, related_name='cash_advances', on_delete=models.PROTECT)
    sumber_dana = models.CharField(max_length=100, blank=True)
    pelunasan = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status_lunas = models.CharField(max_length=10, choices=StatusLunas.choices, default=StatusLunas.BELUM)

    class Meta:
        ordering = ['-tanggal', '-id']
        constraints = [models.UniqueConstraint(fields=['tenant', 'no_register'], name='uniq_cashadvance_tenant_no_register')]

    def __str__(self):
        return self.no_register or 'Kas Bon Karyawan'

    @property
    def saldo(self):
        return self.nominal - self.pelunasan

    @transaction.atomic
    def save_with_business_rules(self, user=None):
        old = type(self).objects.filter(pk=self.pk).first() if self.pk else None
        ensure_open_period(self.tenant, self.tanggal, old.tanggal if old else None)
        if old and old.pelunasan > ZERO:
            raise ValidationError('Kas bon tidak bisa diubah karena sudah ada pembayaran.')
        if not self.bank:
            raise ValidationError('Bank belum dipilih.')
        if not self.bank.akun:
            raise ValidationError('Akun pada Kas/Bank wajib diisi di master Bank/Kas.')
        if self.nominal <= ZERO:
            raise ValidationError('Nominal belum diisi.')
        self.perkiraan_kas = self.bank.akun
        self.sumber_dana = str(self.bank)
        assign_number(self, 'no_register', 'BON')
        self.status_lunas = self.StatusLunas.LUNAS if self.nominal <= self.pelunasan else self.StatusLunas.BELUM
        self.save()
        lines = [{'account': self.perkiraan_pinjaman, 'debet': self.nominal}, {'account': self.perkiraan_kas, 'kredit': self.nominal}]
        refresh_journal(obj=self, no_jurnal=self.no_register, tanggal=self.tanggal, keterangan=self.keterangan, lines=lines, user=user)
        return self

    def delete_with_business_rules(self, user=None):
        ensure_open_period(self.tenant, self.tanggal)
        if self.pelunasan > ZERO:
            raise ValidationError('Kas bon tidak bisa dihapus karena sudah ada pembayaran.')
        delete_generated_journal(self)
        self.delete()


class EmployeeCashAdvancePayment(TenantScopedModel):
    no_register = models.CharField(max_length=50, blank=True)
    tanggal = models.DateField()
    kas_bon_karyawan = models.ForeignKey(EmployeeCashAdvance, related_name='payments', on_delete=models.PROTECT)
    perkiraan_kas = models.ForeignKey('master.ChartOfAccount', related_name='cash_advance_payments', on_delete=models.PROTECT)
    nominal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    keterangan = models.TextField(blank=True)
    bank = models.ForeignKey('master.BankAccount', null=True, blank=True, related_name='cash_advance_payments', on_delete=models.PROTECT)
    sumber_dana = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-tanggal', '-id']
        constraints = [models.UniqueConstraint(fields=['tenant', 'no_register'], name='uniq_cashadvancepayment_tenant_no_register')]

    def __str__(self):
        return self.no_register or 'Pembayaran Kas Bon'

    @property
    def hutang(self):
        return self.kas_bon_karyawan.nominal

    @property
    def saldo_hutang(self):
        return self.kas_bon_karyawan.nominal - self.nominal

    @transaction.atomic
    def save_with_business_rules(self, user=None):
        old = type(self).objects.filter(pk=self.pk).first() if self.pk else None
        ensure_open_period(self.tenant, self.tanggal, old.tanggal if old else None)
        if not self.bank:
            raise ValidationError('Via bank belum dipilih.')
        if not self.bank.akun:
            raise ValidationError('Akun pada Kas/Bank wajib diisi di master Bank/Kas.')
        if self.nominal <= ZERO:
            raise ValidationError('Nominal belum diisi.')
        paid_before_this = self.kas_bon_karyawan.payments.filter(is_deleted=False).exclude(pk=self.pk).aggregate(total=Sum('nominal'))['total'] or ZERO
        available_balance = self.kas_bon_karyawan.nominal - paid_before_this
        if self.nominal > available_balance:
            raise ValidationError('Pembayaran melebihi saldo hutang.')
        self.perkiraan_kas = self.bank.akun
        self.sumber_dana = str(self.bank)
        assign_number(self, 'no_register', 'BYR')
        self.save()
        lines = [{'account': self.perkiraan_kas, 'debet': self.nominal}, {'account': self.kas_bon_karyawan.perkiraan_pinjaman, 'kredit': self.nominal}]
        refresh_journal(obj=self, no_jurnal=self.no_register, tanggal=self.tanggal, keterangan=self.keterangan, lines=lines, user=user)
        refresh_cash_advance_status(self.kas_bon_karyawan)
        if old and old.kas_bon_karyawan_id != self.kas_bon_karyawan_id:
            refresh_cash_advance_status(old.kas_bon_karyawan)
        return self

    def delete_with_business_rules(self, user=None):
        ensure_open_period(self.tenant, self.tanggal)
        advance = self.kas_bon_karyawan
        delete_generated_journal(self)
        self.delete()
        refresh_cash_advance_status(advance)


def refresh_cash_advance_status(advance):
    total = advance.payments.filter(is_deleted=False).aggregate(total=Sum('nominal'))['total'] or ZERO
    advance.pelunasan = total
    advance.status_lunas = EmployeeCashAdvance.StatusLunas.LUNAS if advance.nominal <= total else EmployeeCashAdvance.StatusLunas.BELUM
    advance.save(update_fields=['pelunasan', 'status_lunas', 'updated_at'])







