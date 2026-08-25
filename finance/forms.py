from django import forms

from .models import BankTransaction, CashTransaction, EmployeeCashAdvance, EmployeeCashAdvancePayment, FuelPurchase, LoanDebt, LoanDebtPayment

COMMON_EXCLUDE = ['tenant', 'created_by', 'updated_by', 'is_deleted', 'deleted_at', 'deleted_by']


class CashTransactionForm(forms.ModelForm):
    class Meta:
        model = CashTransaction
        fields = ['akun_transaksi', 'bank', 'armada', 'tanggal', 'nominal_keluar', 'nominal_masuk', 'keterangan']
        labels = {
            'akun_transaksi': 'Akun Biaya/Pendapatan',
            'bank': 'Kas/Bank',
            'armada': 'Untuk Armada',
            'nominal_keluar': 'Uang Keluar',
            'nominal_masuk': 'Uang Masuk',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nominal_keluar'].required = False
        self.fields['nominal_masuk'].required = False

    def clean_nominal_keluar(self):
        return self.cleaned_data.get('nominal_keluar') or 0

    def clean_nominal_masuk(self):
        return self.cleaned_data.get('nominal_masuk') or 0


class BankTransactionForm(forms.ModelForm):
    class Meta:
        model = BankTransaction
        exclude = COMMON_EXCLUDE + ['no_bukti', 'akun_utama', 'akun_tujuan']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['debet'].required = False
        self.fields['kredit'].required = False

    def clean_debet(self):
        return self.cleaned_data.get('debet') or 0

    def clean_kredit(self):
        return self.cleaned_data.get('kredit') or 0


class FuelPurchaseForm(forms.ModelForm):
    class Meta:
        model = FuelPurchase
        exclude = COMMON_EXCLUDE + ['no_bukti']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'armada' in self.fields:
            self.fields['armada'].label_from_instance = lambda obj: (
                f"{obj.nopol} - {obj.kendaraan} (Supir: {obj.driver.nama})" if getattr(obj, 'kendaraan', None) and getattr(obj, 'driver', None)
                else f"{obj.nopol} - {obj.kendaraan}" if getattr(obj, 'kendaraan', None)
                else f"{obj.nopol} (Supir: {obj.driver.nama})" if getattr(obj, 'driver', None)
                else obj.nopol
            )


class EmployeeCashAdvanceForm(forms.ModelForm):
    class Meta:
        model = EmployeeCashAdvance
        fields = ['perkiraan_pinjaman', 'karyawan', 'tanggal', 'bank', 'nominal', 'keterangan']
        labels = {
            'perkiraan_pinjaman': 'Jenis Kas Bon',
            'bank': 'Kas/Bank',
        }


class EmployeeCashAdvancePaymentForm(forms.ModelForm):
    class Meta:
        model = EmployeeCashAdvancePayment
        fields = ['kas_bon_karyawan', 'tanggal', 'bank', 'nominal', 'keterangan']
        labels = {
            'kas_bon_karyawan': 'Kas Bon',
            'bank': 'Kas/Bank',
        }




class LoanDebtForm(forms.ModelForm):
    class Meta:
        model = LoanDebt
        fields = ['perkiraan_hutang', 'pemberi_pinjaman', 'tanggal', 'bank', 'nominal', 'keterangan']
        labels = {
            'perkiraan_hutang': 'Akun Hutang',
            'pemberi_pinjaman': 'Pemberi Pinjaman',
            'bank': 'Kas/Bank Penerima Uang',
        }


class LoanDebtPaymentForm(forms.ModelForm):
    class Meta:
        model = LoanDebtPayment
        fields = ['hutang_pinjaman', 'tanggal', 'bank', 'nominal', 'keterangan']
        labels = {
            'hutang_pinjaman': 'Hutang Pinjaman',
            'bank': 'Kas/Bank Sumber Uang',
            'nominal': 'Nominal Pembayaran',
        }
