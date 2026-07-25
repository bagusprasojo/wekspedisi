from django import forms

from .models import CustomerInvoice, CustomerInvoicePayment

COMMON_EXCLUDE = ['tenant', 'created_by', 'updated_by', 'is_deleted', 'deleted_at', 'deleted_by']


class CustomerInvoiceForm(forms.ModelForm):
    class Meta:
        model = CustomerInvoice
        fields = ['customer', 'tanggal', 'pekerjaan', 'nilai_pekerjaan', 'keterangan']
        labels = {
            'nilai_pekerjaan': 'Nilai Pekerjaan',
        }


class CustomerInvoicePaymentForm(forms.ModelForm):
    class Meta:
        model = CustomerInvoicePayment
        fields = ['tagihan_customer', 'tanggal', 'bank', 'nominal_kas', 'pph_persen', 'pph', 'keterangan']
        labels = {
            'tagihan_customer': 'Invoice',
            'bank': 'Kas/Bank',
            'nominal_kas': 'Nominal Kas/Bank',
            'pph_persen': 'PPH %',
            'pph': 'PPH Rp',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['pph_persen'].required = False
        self.fields['pph'].required = False

    def clean_pph_persen(self):
        return self.cleaned_data.get('pph_persen') or 0

    def clean_pph(self):
        return self.cleaned_data.get('pph') or 0
