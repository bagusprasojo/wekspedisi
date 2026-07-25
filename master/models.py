from django.db import models

from core.models import TenantScopedModel


class StakeHolder(TenantScopedModel):
    class StakeHolderType(models.TextChoices):
        CUSTOMER = 'customer', 'Customer'
        KARYAWAN = 'karyawan', 'Karyawan'

    kode = models.CharField(max_length=30)
    nama = models.CharField(max_length=150)
    jenis = models.CharField(max_length=20, choices=StakeHolderType.choices)
    alamat = models.TextField(blank=True)
    no_ktp = models.CharField(max_length=50, blank=True)
    lokasi_kerja = models.CharField(max_length=150, blank=True)
    kota = models.CharField(max_length=100, blank=True)
    kode_pos = models.CharField(max_length=20, blank=True)
    telp = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    keterangan = models.TextField(blank=True)

    class Meta:
        ordering = ['nama']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'kode'], name='uniq_stakeholder_tenant_kode'),
        ]

    def __str__(self):
        return self.nama

    def save(self, *args, **kwargs):
        if not self.kode:
            prefix = 'CUS' if self.jenis == self.StakeHolderType.CUSTOMER else 'KAR'
            self.kode = f'{prefix}-{__import__("time").time_ns()}'
        super().save(*args, **kwargs)


class ChartOfAccount(TenantScopedModel):
    class NormalBalance(models.TextChoices):
        DEBET = 'DEBET', 'Debet'
        KREDIT = 'KREDIT', 'Kredit'

    kode = models.CharField(max_length=30)
    nama = models.CharField(max_length=150)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children', on_delete=models.PROTECT)
    golongan = models.CharField(max_length=100, blank=True)
    kelompok = models.CharField(max_length=100, blank=True)
    level = models.PositiveSmallIntegerField(default=1, editable=False)
    saldo_normal = models.CharField(max_length=10, choices=NormalBalance.choices)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['kode']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'kode'], name='uniq_chartofaccount_tenant_kode'),
        ]

    @property
    def is_leaf(self):
        if not self.pk:
            return True
        return not self.children.filter(is_deleted=False).exists()

    @property
    def display_kode(self):
        return f'{" " * (self.level * 4)}{self.kode}'

    @property
    def display_nama(self):
        return f'{" " * (self.level * 4)}{self.nama}'

    def save(self, *args, **kwargs):
        self.level = self.parent.level + 1 if self.parent_id else 1
        super().save(*args, **kwargs)
        self.sync_descendant_levels()

    def sync_descendant_levels(self):
        for child in self.children.filter(is_deleted=False):
            expected_level = self.level + 1
            if child.level != expected_level:
                child.level = expected_level
                type(self).objects.filter(pk=child.pk).update(level=expected_level)
            child.sync_descendant_levels()

    def __str__(self):
        return f'{self.kode} - {self.nama}'


class Armada(TenantScopedModel):
    nopol = models.CharField(max_length=60)
    kendaraan = models.CharField(max_length=100)
    pemilik = models.CharField(max_length=100, blank=True)
    alamat = models.TextField(blank=True)
    kota = models.CharField(max_length=100, blank=True)
    telp = models.CharField(max_length=50, blank=True)
    driver = models.ForeignKey(StakeHolder, null=True, blank=True, related_name='armada_set', on_delete=models.PROTECT)

    class Meta:
        ordering = ['nopol']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'nopol'], name='uniq_armada_tenant_nopol'),
        ]

    def __str__(self):
        return self.nopol


class BankAccount(TenantScopedModel):
    no_rekening = models.CharField(max_length=50)
    nama_bank = models.CharField(max_length=100)
    atas_nama = models.CharField(max_length=100)
    keterangan = models.TextField(blank=True)
    akun = models.ForeignKey(ChartOfAccount, null=True, blank=True, related_name='bank_accounts', on_delete=models.PROTECT)
    is_kas = models.BooleanField(default=False)

    class Meta:
        ordering = ['nama_bank', 'no_rekening']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'no_rekening'], name='uniq_bankaccount_tenant_no_rekening'),
        ]

    def __str__(self):
        return f'{self.nama_bank} - {self.no_rekening}'


class TransactionType(TenantScopedModel):
    kode = models.CharField(max_length=10)
    nama = models.CharField(max_length=100)
    akun = models.ForeignKey(ChartOfAccount, related_name='transaction_types', on_delete=models.PROTECT)

    class Meta:
        ordering = ['kode']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'kode'], name='uniq_transactiontype_tenant_kode'),
        ]

    def __str__(self):
        return f'{self.kode} - {self.nama}'


class TenantConfig(TenantScopedModel):
    kode = models.CharField(max_length=60)
    nilai = models.CharField(max_length=100, blank=True)
    keterangan = models.TextField(blank=True)

    class Meta:
        ordering = ['kode']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'kode'], name='uniq_tenantconfig_tenant_kode'),
        ]

    def __str__(self):
        return self.kode
