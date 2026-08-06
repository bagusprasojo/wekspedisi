from django import forms
from django.forms import inlineformset_factory

from master.models import BankAccount
from .models import ClosingPeriod, Journal, JournalLine

COMMON_EXCLUDE = ['tenant', 'created_by', 'updated_by', 'is_deleted', 'deleted_at', 'deleted_by']
FIELD_CLASS = 'w-full rounded border px-3 py-2 text-sm'


def style_form_fields(form):
    for field in form.fields.values():
        if isinstance(field, forms.DateField):
            field.widget = forms.DateInput(format='%Y-%m-%d', attrs=field.widget.attrs)
            field.widget.input_type = 'date'
        field.widget.attrs.setdefault('class', FIELD_CLASS)


class JournalForm(forms.ModelForm):
    class Meta:
        model = Journal
        exclude = COMMON_EXCLUDE + ['no_jurnal', 'transaksi_id', 'transaksi']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form_fields(self)


class JournalLineForm(forms.ModelForm):
    class Meta:
        model = JournalLine
        fields = ['perkiraan', 'debet', 'kredit']

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        self.tenant = tenant
        super().__init__(*args, **kwargs)
        if tenant:
            self.fields['perkiraan'].queryset = self.fields['perkiraan'].queryset.filter(
                tenant=tenant,
                is_deleted=False,
                is_active=True,
            ).exclude(
                children__is_deleted=False,
            ).exclude(
                bank_accounts__tenant=tenant,
                bank_accounts__is_deleted=False,
            ).distinct()
        for field in self.fields.values():
            field.required = False
            field.widget.attrs.setdefault('class', FIELD_CLASS)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('DELETE'):
            return cleaned
        account = cleaned.get('perkiraan')
        debet = cleaned.get('debet') or 0
        kredit = cleaned.get('kredit') or 0
        if not account and not debet and not kredit:
            return cleaned
        if not account:
            raise forms.ValidationError('Akun wajib diisi pada baris jurnal.')
        if debet and kredit:
            raise forms.ValidationError('Satu baris hanya boleh berisi debet atau kredit.')
        if not debet and not kredit:
            raise forms.ValidationError('Nilai debet atau kredit wajib diisi.')
        if not account.is_leaf:
            raise forms.ValidationError('Akun yang punya anak tidak bisa dipakai transaksi.')
        if self.tenant and BankAccount.objects.filter(tenant=self.tenant, is_deleted=False, akun=account).exists():
            raise forms.ValidationError('Akun kas/bank tidak bisa dipakai di jurnal penyesuaian.')
        return cleaned


class BaseJournalLineFormSet(forms.BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs['tenant'] = self.tenant
        return super()._construct_form(i, **kwargs)


JournalLineFormSet = inlineformset_factory(
    Journal,
    JournalLine,
    form=JournalLineForm,
    formset=BaseJournalLineFormSet,
    extra=2,
    can_delete=True,
)

JournalLineEditFormSet = inlineformset_factory(
    Journal,
    JournalLine,
    form=JournalLineForm,
    formset=BaseJournalLineFormSet,
    extra=0,
    can_delete=True,
)


class ClosingPeriodForm(forms.ModelForm):
    class Meta:
        model = ClosingPeriod
        exclude = COMMON_EXCLUDE

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form_fields(self)
