from django.urls import path

from core.crud import CrudConfig, build_crud_views
from master import views
from master.forms import ArmadaForm, BankAccountForm, ChartOfAccountForm, CustomerForm, KaryawanForm, TenantConfigForm, TransactionTypeForm
from master.models import Armada, BankAccount, ChartOfAccount, StakeHolder, TenantConfig, TransactionType

CONFIGS = {
    'customer': CrudConfig(model=StakeHolder, form_class=CustomerForm, title='Customer', list_display=['nama', 'alamat', 'kota', 'kode_pos', 'telp', 'no_ktp'], list_labels={'kode_pos': 'Kode Pos', 'no_ktp': 'No KTP'}, search_fields=['nama', 'alamat', 'kota', 'kode_pos', 'telp', 'no_ktp'], success_url_name='master_customer_list', fixed_filters={'jenis': StakeHolder.StakeHolderType.CUSTOMER}, fixed_values={'jenis': StakeHolder.StakeHolderType.CUSTOMER}),
    'karyawan': CrudConfig(model=StakeHolder, form_class=KaryawanForm, title='Karyawan', list_display=['nama', 'alamat', 'kota', 'kode_pos', 'telp', 'no_ktp', 'lokasi_kerja'], list_labels={'kode_pos': 'Kode Pos', 'no_ktp': 'No KTP', 'lokasi_kerja': 'Lokasi Kerja'}, search_fields=['nama', 'alamat', 'kota', 'kode_pos', 'telp', 'no_ktp', 'lokasi_kerja'], success_url_name='master_karyawan_list', fixed_filters={'jenis': StakeHolder.StakeHolderType.KARYAWAN}, fixed_values={'jenis': StakeHolder.StakeHolderType.KARYAWAN}),
    'armada': CrudConfig(model=Armada, form_class=ArmadaForm, title='Armada', list_display=['nopol', 'kendaraan', 'pemilik', 'driver'], search_fields=['nopol', 'kendaraan', 'pemilik'], success_url_name='master_armada_list'),
    'bank': CrudConfig(model=BankAccount, form_class=BankAccountForm, title='Bank/Kas', list_display=['nama_bank', 'no_rekening', 'atas_nama', 'is_kas'], list_labels={'nama_bank': 'Nama Bank/Kas', 'no_rekening': 'No. Rekening', 'atas_nama': 'Atas Nama', 'is_kas': 'Kas?'}, search_fields=['nama_bank', 'no_rekening', 'atas_nama'], success_url_name='master_bank_list'),
    'akun': CrudConfig(model=ChartOfAccount, form_class=ChartOfAccountForm, title='Perkiraan/Akun', list_display=['display_kode', 'display_nama', 'golongan', 'kelompok', 'level', 'saldo_normal', 'parent', 'is_active'], list_labels={'display_kode': 'Kode', 'display_nama': 'Nama', 'golongan': 'Golongan', 'kelompok': 'Kelompok', 'level': 'Level', 'saldo_normal': 'Saldo Normal', 'parent': 'Akun Parent', 'is_active': 'Aktif?'}, search_fields=['kode', 'nama', 'golongan', 'kelompok'], success_url_name='master_akun_list'),
    'jenis-transaksi': CrudConfig(model=TransactionType, form_class=TransactionTypeForm, title='Jenis Transaksi', list_display=['kode', 'nama', 'akun.kode', 'akun.nama'], list_labels={'kode': 'Kode', 'nama': 'Nama', 'akun.kode': 'Kode Akun', 'akun.nama': 'Nama Akun'}, search_fields=['kode', 'nama', 'akun__kode', 'akun__nama'], success_url_name='master_jenis_transaksi_list'),
    'config': CrudConfig(model=TenantConfig, form_class=TenantConfigForm, title='Config', list_display=['kode', 'nilai', 'keterangan'], search_fields=['kode', 'nilai', 'keterangan'], success_url_name='master_config_list'),
}

urlpatterns = [
    path('lookup/stakeholder/', views.stakeholder_lookup, name='master_lookup_stakeholder'),
]
for slug, config in CONFIGS.items():
    list_view, create_view, update_view, delete_view = build_crud_views(config)
    prefix = slug.replace('-', '_')
    urlpatterns += [
        path(f'{slug}/', list_view.as_view(), name=f'master_{prefix}_list'),
        path(f'{slug}/new/', create_view.as_view(), name=f'master_{prefix}_create'),
        path(f'{slug}/<uuid:uuid>/edit/', update_view.as_view(), name=f'master_{prefix}_update'),
        path(f'{slug}/<uuid:uuid>/delete/', delete_view.as_view(), name=f'master_{prefix}_delete'),
    ]


