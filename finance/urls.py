from django.urls import path

from core.crud import CrudConfig, build_crud_views
from finance import views
from finance.forms import BankTransactionForm, CashTransactionForm, EmployeeCashAdvanceForm, EmployeeCashAdvancePaymentForm, FuelPurchaseForm
from finance.models import BankTransaction, CashTransaction, EmployeeCashAdvance, EmployeeCashAdvancePayment, FuelPurchase

CONFIGS = {
    # 'transaksi-kas': CrudConfig(model=CashTransaction, form_class=CashTransactionForm, title='Transaksi Kas', list_display=['no_bukti', 'tanggal', 'akun_transaksi', 'keterangan', 'bank', 'armada', 'nominal_keluar', 'nominal_masuk', 'created_by'], list_labels={'no_bukti': 'No Bukti', 'akun_transaksi': 'Akun Biaya/Pendapatan', 'nominal_keluar': 'Pengeluaran', 'nominal_masuk': 'Penerimaan', 'created_by': 'Pc'}, search_fields=['no_bukti', 'keterangan', 'akun_transaksi__kode', 'akun_transaksi__nama', 'bank__no_rekening', 'armada__nopol'], success_url_name='finance_transaksi_kas_list', detail_url_name='finance_transaksi_kas_detail', hide_list_edit=True),
    'transaksi-kas': CrudConfig(
                        model=CashTransaction, 
                        form_class=CashTransactionForm, 
                        title='Transaksi Kas', 
                        list_display   =['no_bukti', 'tanggal', 'akun_transaksi', 'keterangan', 'bank', 'armada', 'nominal_keluar', 'nominal_masuk', 'created_by'],                         
                        list_pdf_widths=[0.9       , 0.7     , 1.4             , 1.5         , 1.0   , 0.75     , 0.75             , 0.75            , 0.75],  # <-- TAMBAHKAN INI (0.75 mengecilkan kolom Tanggal)
                        list_labels={'no_bukti': 'No Bukti', 'akun_transaksi': 'Akun Biaya/Pendapatan', 'nominal_keluar': 'Pengeluaran', 'nominal_masuk': 'Penerimaan', 'created_by': 'Pc'}, 
                        search_fields=['no_bukti', 'keterangan', 'akun_transaksi__kode', 'akun_transaksi__nama', 'bank__no_rekening', 'armada__nopol'], 
                        success_url_name='finance_transaksi_kas_list', 
                        detail_url_name='finance_transaksi_kas_detail', 
                        hide_list_edit=True
                    ),
    'transaksi-bank': CrudConfig(
                        model=BankTransaction, 
                        form_class=BankTransactionForm, 
                        title='Transaksi Bank', 
                        list_display=['no_bukti', 'tanggal', 'bank_utama.no_rekening', 'bank_utama.nama_bank', 'jenis_transaksi.nama', 'debet', 'kredit', 'biaya_adm_bank', 'uraian', 'created_by'], 
                        list_pdf_widths=[1.1    , 0.75     , 1.05                    , 1.05                  , 1.05                  , 0.82   , 0.82    , 0.82            , 1.85    , 0.75], 
                        list_labels={'no_bukti': 'No Bukti', 'bank_utama.no_rekening': 'No Rek', 'bank_utama.nama_bank': 'Nama Bank', 'jenis_transaksi.nama': 'Transaksi', 'biaya_adm_bank': 'Adm. Bank', 'created_by': 'User'}, 
                        search_fields=['no_bukti', 'uraian', 'bank_utama__no_rekening', 'bank_utama__nama_bank', 'bank_utama__atas_nama', 'jenis_transaksi__kode', 'jenis_transaksi__nama'], 
                        success_url_name='finance_transaksi_bank_list', 
                        detail_url_name='finance_transaksi_bank_detail', 
                        hide_list_edit=True
                    ),
    'pembelian-bbm': CrudConfig(model=FuelPurchase, form_class=FuelPurchaseForm, title='Pembelian BBM', list_display=['no_bukti', 'tanggal', 'armada', 'km_terakhir', 'km_sekarang', 'nominal_bbm'], list_labels={'km_terakhir': 'KM Terakhir', 'km_sekarang': 'KM Sekarang', 'nominal_bbm': 'Nominal BBM'}, search_fields=['no_bukti', 'keterangan'], success_url_name='finance_pembelian_bbm_list', detail_url_name='finance_pembelian_bbm_detail', hide_list_edit=True),
    'kas-bon': CrudConfig(model=EmployeeCashAdvance, form_class=EmployeeCashAdvanceForm, title='Kas Bon Karyawan', list_display=['no_register', 'tanggal', 'perkiraan_pinjaman', 'karyawan.nama', 'sumber_dana', 'nominal', 'pelunasan', 'saldo', 'status_lunas', 'keterangan', 'created_by'], list_labels={'no_register': 'No Register', 'perkiraan_pinjaman': 'Jenis Kas Bon', 'karyawan.nama': 'Nama', 'sumber_dana': 'Sumber Dana', 'status_lunas': 'Status Lunas', 'created_by': 'Pc'}, search_fields=['no_register', 'status_lunas', 'karyawan__nama', 'karyawan__alamat', 'sumber_dana', 'keterangan', 'perkiraan_pinjaman__kode', 'perkiraan_pinjaman__nama'], success_url_name='finance_kas_bon_list', detail_url_name='finance_kas_bon_detail', hide_list_edit=True),
    'pembayaran-kas-bon': CrudConfig(model=EmployeeCashAdvancePayment, form_class=EmployeeCashAdvancePaymentForm, title='Pembayaran Kas Bon', list_display=['no_register', 'kas_bon_karyawan.no_register', 'kas_bon_karyawan.karyawan.nama', 'kas_bon_karyawan.karyawan.alamat', 'tanggal', 'sumber_dana', 'hutang', 'nominal', 'saldo_hutang', 'keterangan', 'created_by'], list_labels={'no_register': 'No Register', 'kas_bon_karyawan.no_register': 'No Kas Bon', 'kas_bon_karyawan.karyawan.nama': 'Nama', 'kas_bon_karyawan.karyawan.alamat': 'Alamat', 'sumber_dana': 'Sumber Dana', 'hutang': 'Hutang', 'nominal': 'Pembayaran', 'saldo_hutang': 'Saldo Hutang', 'created_by': 'Pc'}, search_fields=['no_register', 'kas_bon_karyawan__karyawan__nama', 'kas_bon_karyawan__karyawan__alamat', 'kas_bon_karyawan__sumber_dana', 'kas_bon_karyawan__keterangan', 'kas_bon_karyawan__no_register'], success_url_name='finance_pembayaran_kas_bon_list', detail_url_name='finance_pembayaran_kas_bon_detail', hide_list_edit=True),
}

urlpatterns = [
    path('pembelian-bbm/last-km/', views.fuel_purchase_last_km, name='finance_pembelian_bbm_last_km'),
    path('pembelian-bbm/<uuid:uuid>/', views.fuel_purchase_detail, name='finance_pembelian_bbm_detail'),
    path('transaksi-kas/account-lookup/', views.cash_transaction_account_lookup, name='finance_transaksi_kas_account_lookup'),
    path('transaksi-kas/<uuid:uuid>/', views.cash_transaction_detail, name='finance_transaksi_kas_detail'),
    path('transaksi-bank/<uuid:uuid>/', views.bank_transaction_detail, name='finance_transaksi_bank_detail'),
    path('kas-bon/lookup/', views.cash_advance_lookup, name='finance_kas_bon_lookup'),
    path('kas-bon/<uuid:uuid>/', views.cash_advance_detail, name='finance_kas_bon_detail'),
    path('pembayaran-kas-bon/<uuid:uuid>/', views.cash_advance_payment_detail, name='finance_pembayaran_kas_bon_detail'),
]
for slug, config in CONFIGS.items():
    list_view, create_view, update_view, delete_view = build_crud_views(config)
    prefix = slug.replace('-', '_')
    urlpatterns += [
        path(f'{slug}/', list_view.as_view(), name=f'finance_{prefix}_list'),
        path(f'{slug}/new/', create_view.as_view(), name=f'finance_{prefix}_create'),
        path(f'{slug}/<uuid:uuid>/edit/', update_view.as_view(), name=f'finance_{prefix}_update'),
        path(f'{slug}/<uuid:uuid>/delete/', delete_view.as_view(), name=f'finance_{prefix}_delete'),
    ]

