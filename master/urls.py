from django.urls import path

from core.crud import CrudConfig, build_crud_views
from master import views
from master.forms import ArmadaForm, BankAccountForm, ChartOfAccountForm, CustomerForm, KaryawanForm
from master.models import Armada, BankAccount, ChartOfAccount, StakeHolder

CONFIGS = {
    'customer': CrudConfig(model=StakeHolder, form_class=CustomerForm, title='Customer', list_display=['nama', 'alamat', 'kota', 'kode_pos', 'telp', 'no_ktp'], list_labels={'kode_pos': 'Kode Pos', 'no_ktp': 'No KTP'}, search_fields=['nama', 'alamat', 'kota', 'kode_pos', 'telp', 'no_ktp'], success_url_name='master_customer_list', detail_url_name='master_customer_detail', hide_list_edit=True, fixed_filters={'jenis': StakeHolder.StakeHolderType.CUSTOMER}, fixed_values={'jenis': StakeHolder.StakeHolderType.CUSTOMER}),
    'karyawan': CrudConfig(model=StakeHolder, form_class=KaryawanForm, title='Karyawan', list_display=['nama', 'alamat', 'kota', 'kode_pos', 'telp', 'no_ktp', 'lokasi_kerja'], list_labels={'kode_pos': 'Kode Pos', 'no_ktp': 'No KTP', 'lokasi_kerja': 'Lokasi Kerja'}, search_fields=['nama', 'alamat', 'kota', 'kode_pos', 'telp', 'no_ktp', 'lokasi_kerja'], success_url_name='master_karyawan_list', detail_url_name='master_karyawan_detail', hide_list_edit=True, fixed_filters={'jenis': StakeHolder.StakeHolderType.KARYAWAN}, fixed_values={'jenis': StakeHolder.StakeHolderType.KARYAWAN}),
    'armada': CrudConfig(model=Armada, form_class=ArmadaForm, title='Armada', list_display=['nopol', 'kendaraan', 'pemilik', 'driver'], search_fields=['nopol', 'kendaraan', 'pemilik'], success_url_name='master_armada_list', detail_url_name='master_armada_detail', hide_list_edit=True),
    'bank': CrudConfig(model=BankAccount, form_class=BankAccountForm, title='Bank/Kas', list_display=['nama_bank', 'no_rekening', 'atas_nama', 'is_kas'], list_labels={'nama_bank': 'Nama Bank/Kas', 'no_rekening': 'No. Rekening', 'atas_nama': 'Atas Nama', 'is_kas': 'Kas?'}, search_fields=['nama_bank', 'no_rekening', 'atas_nama'], success_url_name='master_bank_list', detail_url_name='master_bank_detail', hide_list_edit=True),
    'akun': CrudConfig(model=ChartOfAccount, form_class=ChartOfAccountForm, title='Perkiraan/Akun', list_display=['display_kode', 'display_nama', 'golongan', 'kelompok', 'level', 'saldo_normal', 'parent', 'is_active'], list_labels={'display_kode': 'Kode', 'display_nama': 'Nama', 'golongan': 'Golongan', 'kelompok': 'Kelompok', 'level': 'Level', 'saldo_normal': 'Saldo Normal', 'parent': 'Akun Parent', 'is_active': 'Aktif?'}, search_fields=['kode', 'nama', 'golongan', 'kelompok'], success_url_name='master_akun_list', detail_url_name='master_akun_detail', hide_list_edit=True),
}

urlpatterns = [
    path('lookup/stakeholder/', views.stakeholder_lookup, name='master_lookup_stakeholder'),
    path('bank/<uuid:uuid>/', views.bank_detail, name='master_bank_detail'),
    path('customer/<uuid:uuid>/', views.customer_detail, name='master_customer_detail'),
    path('karyawan/<uuid:uuid>/', views.karyawan_detail, name='master_karyawan_detail'),
    path('armada/<uuid:uuid>/', views.armada_detail, name='master_armada_detail'),
    path('akun/<uuid:uuid>/', views.account_detail, name='master_akun_detail'),
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


