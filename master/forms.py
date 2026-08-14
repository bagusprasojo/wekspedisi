from django import forms

from .models import Armada, BankAccount, ChartOfAccount, StakeHolder, TenantConfig, TransactionType

COMMON_EXCLUDE = ['tenant', 'created_by', 'updated_by', 'is_deleted', 'deleted_at', 'deleted_by']


class StakeHolderForm(forms.ModelForm):
    class Meta:
        model = StakeHolder
        exclude = COMMON_EXCLUDE


class CustomerForm(forms.ModelForm):
    class Meta:
        model = StakeHolder
        fields = ['nama', 'alamat', 'kota', 'kode_pos', 'telp', 'no_ktp', 'email', 'keterangan']


class KaryawanForm(forms.ModelForm):
    class Meta:
        model = StakeHolder
        fields = ['nama', 'alamat', 'kota', 'kode_pos', 'telp', 'no_ktp', 'lokasi_kerja', 'email', 'keterangan']


class ArmadaForm(forms.ModelForm):
    driver = forms.ModelChoiceField(queryset=StakeHolder.objects.all(), required=False, widget=forms.HiddenInput)
    driver_text = forms.CharField(label='Driver', required=False)

    class Meta:
        model = Armada
        fields = ['nopol', 'kendaraan', 'pemilik', 'alamat', 'kota', 'telp', 'driver', 'driver_text']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant = getattr(self.instance, 'tenant', None)
        if tenant:
            self.fields['driver'].queryset = StakeHolder.objects.filter(
                tenant=tenant,
                is_deleted=False,
                jenis=StakeHolder.StakeHolderType.KARYAWAN,
            )
        if self.instance and self.instance.pk and self.instance.driver:
            self.fields['driver_text'].initial = str(self.instance.driver)

    def clean(self):
        cleaned = super().clean()
        driver_text = (cleaned.get('driver_text') or '').strip()
        driver = cleaned.get('driver')
        if driver_text and not driver:
            candidates = list(self.fields['driver'].queryset)
            driver = next((item for item in candidates if str(item) == driver_text), None)
            if not driver and ' - ' in driver_text:
                kode = driver_text.split(' - ', 1)[0].strip()
                driver = next((item for item in candidates if item.kode == kode), None)
            if driver:
                cleaned['driver'] = driver
            else:
                self.add_error('driver_text', 'Driver harus dipilih dari daftar autocomplete.')
        return cleaned


class BankAccountForm(forms.ModelForm):
    class Meta:
        model = BankAccount
        exclude = COMMON_EXCLUDE


class ChartOfAccountForm(forms.ModelForm):
    GOLONGAN_CHOICES = [
        ('AKTIVA', 'AKTIVA'),
        ('PASIVA', 'PASIVA'),
        ('LABA/RUGI', 'LABA/RUGI'),
    ]
    KELOMPOK_CHOICES = [
        ('AKTIVA', 'AKTIVA'),
        ('PASIVA', 'PASIVA'),
        ('KEWAJIBAN', 'KEWAJIBAN'),
        ('EQUITAS', 'EQUITAS'),
        ('PENDAPATAN', 'PENDAPATAN'),
        ('BIAYA', 'BIAYA'),
    ]

    golongan = forms.ChoiceField(choices=GOLONGAN_CHOICES, label='Golongan')
    kelompok = forms.ChoiceField(choices=KELOMPOK_CHOICES, label='Kelompok')

    class Meta:
        model = ChartOfAccount
        fields = ['kode', 'nama', 'parent', 'golongan', 'kelompok', 'saldo_normal', 'is_active']
        labels = {
            'kode': 'Kode',
            'nama': 'Nama',
            'parent': 'Akun Parent',
            'golongan': 'Golongan',
            'kelompok': 'Kelompok',
            'saldo_normal': 'Saldo Normal',
            'is_active': 'Aktif?',
        }

    def clean_parent(self):
        parent = self.cleaned_data.get('parent')
        if not parent or not self.instance.pk:
            return parent
        if parent.pk == self.instance.pk:
            raise forms.ValidationError('Akun parent tidak boleh sama dengan akun yang sedang diedit.')
        current_parent = parent.parent
        while current_parent:
            if current_parent.pk == self.instance.pk:
                raise forms.ValidationError('Akun parent tidak boleh memakai akun anak dari akun yang sedang diedit.')
            current_parent = current_parent.parent
        return parent


class TransactionTypeForm(forms.ModelForm):
    class Meta:
        model = TransactionType
        fields = ['kode', 'nama', 'akun']
        labels = {
            'kode': 'Kode',
            'nama': 'Nama',
            'akun': 'Akun',
        }


class TenantConfigForm(forms.ModelForm):
    class Meta:
        model = TenantConfig
        exclude = COMMON_EXCLUDE

