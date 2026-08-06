from django import forms
from django.contrib.auth import get_user_model

from accounts.models import UserProfile
from master.models import ChartOfAccount, TenantConfig, TransactionType
from tenants.models import Tenant

FIELD_CLASS = 'w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm file:mr-3 file:rounded file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-sm hover:border-slate-400 focus:border-slate-900 focus:outline-none focus:ring-1 focus:ring-slate-900'
CHECKBOX_CLASS = 'h-4 w-4 rounded border-slate-300 text-slate-900'


def style_fields(form):
    for field in form.fields.values():
        css = CHECKBOX_CLASS if isinstance(field.widget, forms.CheckboxInput) else FIELD_CLASS
        field.widget.attrs.setdefault('class', css)


class TenantForm(forms.ModelForm):
    class Meta:
        model = Tenant
        fields = ['name', 'email', 'phone', 'city', 'province', 'postal_code', 'address', 'logo', 'is_active']
        labels = {
            'name': 'Nama perusahaan',
            'email': 'Email perusahaan',
            'phone': 'Telepon',
            'city': 'Kota',
            'province': 'Provinsi',
            'postal_code': 'Kode pos',
            'address': 'Alamat',
            'logo': 'Logo perusahaan (PNG/JPEG square)',
            'is_active': 'Aktif',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)


class TenantAdmissionForm(forms.Form):
    name = forms.CharField(label='Nama perusahaan', max_length=150)
    address = forms.CharField(label='Alamat', required=False, widget=forms.Textarea(attrs={'rows': 3}))
    city = forms.CharField(label='Kota', max_length=100, required=False)
    province = forms.CharField(label='Provinsi', max_length=100, required=False)
    postal_code = forms.CharField(label='Kode pos', max_length=20, required=False)
    phone = forms.CharField(label='Telepon', max_length=50, required=False)
    email = forms.EmailField(label='Email perusahaan', required=False)
    logo = forms.FileField(label='Logo perusahaan (PNG/JPEG square)', required=False, help_text='Rekomendasi 512 x 512 px atau 1024 x 1024 px.')

    admin_username = forms.CharField(label='Username admin tenant', max_length=150)
    admin_email = forms.EmailField(label='Email admin tenant', required=False)
    admin_first_name = forms.CharField(label='Nama depan admin', max_length=150, required=False)
    admin_last_name = forms.CharField(label='Nama belakang admin', max_length=150, required=False)
    admin_password = forms.CharField(label='Password awal', widget=forms.PasswordInput)
    admin_role = forms.ChoiceField(
        label='Role admin tenant',
        choices=[
            (UserProfile.Role.OWNER, 'Owner'),
            (UserProfile.Role.ADMIN, 'Admin'),
        ],
        initial=UserProfile.Role.OWNER,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)

    def clean_admin_username(self):
        username = self.cleaned_data['admin_username']
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Username sudah digunakan.')
        return username


class TenantUserCreateForm(forms.Form):
    tenant = forms.ModelChoiceField(label='Tenant', queryset=Tenant.objects.filter(is_active=True))
    username = forms.CharField(label='Username', max_length=150)
    email = forms.EmailField(label='Email', required=False)
    first_name = forms.CharField(label='Nama depan', max_length=150, required=False)
    last_name = forms.CharField(label='Nama belakang', max_length=150, required=False)
    password = forms.CharField(label='Password awal', widget=forms.PasswordInput)
    role = forms.ChoiceField(label='Role', choices=UserProfile.Role.choices, initial=UserProfile.Role.ADMIN)
    is_staff = forms.BooleanField(label='Boleh akses Django admin', required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)

    def clean_username(self):
        username = self.cleaned_data['username']
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Username sudah digunakan.')
        return username

class PlatformTenantConfigForm(forms.ModelForm):
    class Meta:
        model = TenantConfig
        fields = ['tenant', 'kode', 'nilai', 'keterangan']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tenant'].queryset = Tenant.objects.order_by('name')
        style_fields(self)

    def clean(self):
        cleaned = super().clean()
        tenant = cleaned.get('tenant')
        kode = cleaned.get('kode')
        if tenant and kode:
            exists = TenantConfig.objects.filter(tenant=tenant, kode=kode, is_deleted=False)
            if self.instance.pk:
                exists = exists.exclude(pk=self.instance.pk)
            if exists.exists():
                raise forms.ValidationError('Config dengan kode ini sudah ada untuk tenant tersebut.')
        return cleaned

class PlatformTransactionTypeForm(forms.ModelForm):
    class Meta:
        model = TransactionType
        fields = ['tenant', 'kode', 'nama', 'akun']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant = self._selected_tenant()
        self.fields['tenant'].queryset = Tenant.objects.order_by('name')
        self.fields['akun'].queryset = ChartOfAccount.objects.none()
        if tenant:
            self.fields['akun'].queryset = ChartOfAccount.objects.filter(
                tenant=tenant,
                is_deleted=False,
                is_active=True,
            ).exclude(children__is_deleted=False).order_by('kode')
        self.fields['akun'].help_text = 'Pilih tenant dulu agar akun tenant tersebut tampil.'
        style_fields(self)

    def _selected_tenant(self):
        tenant_id = self.data.get('tenant') or self.initial.get('tenant') or getattr(self.instance, 'tenant_id', None)
        if not tenant_id:
            return None
        return Tenant.objects.filter(pk=tenant_id).first()

    def clean(self):
        cleaned = super().clean()
        tenant = cleaned.get('tenant')
        kode = cleaned.get('kode')
        account = cleaned.get('akun')
        if tenant and kode:
            exists = TransactionType.objects.filter(tenant=tenant, kode=kode, is_deleted=False)
            if self.instance.pk:
                exists = exists.exclude(pk=self.instance.pk)
            if exists.exists():
                raise forms.ValidationError('Jenis transaksi dengan kode ini sudah ada untuk tenant tersebut.')
        if tenant and account and account.tenant_id != tenant.pk:
            self.add_error('akun', 'Akun harus milik tenant yang dipilih.')
        return cleaned
