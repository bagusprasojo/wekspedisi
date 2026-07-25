from django.urls import path

from reports import views

urlpatterns = [
    path('', views.index, name='reports_index'),
    path('daftar-jurnal/', views.daftar_jurnal, name='reports_daftar_jurnal'),
    path('daftar-jurnal/<uuid:uuid>/', views.daftar_jurnal_detail, name='reports_daftar_jurnal_detail'),
    path('buku-besar/', views.buku_besar, name='reports_buku_besar'),
    path('neraca-saldo/', views.neraca_saldo, name='reports_neraca_saldo'),
    path('saldo-bank/', views.saldo_bank, name='reports_saldo_bank'),
    path('rekap-transaksi-kas/', views.rekap_transaksi_kas, name='reports_rekap_transaksi_kas'),
    path('riwayat-pembelian-bbm/', views.riwayat_pembelian_bbm, name='reports_riwayat_pembelian_bbm'),
    path('rekening-koran/', views.rekening_koran, name='reports_rekening_koran'),
    path('rekap-transaksi-bank/', views.rekap_transaksi_bank, name='reports_rekap_transaksi_bank'),
    path('rekap-transaksi-kas-bon/', views.rekap_transaksi_kas_bon, name='reports_rekap_transaksi_kas_bon'),
    path('saldo-kas-bon/', views.saldo_kas_bon, name='reports_saldo_kas_bon'),
    path('rekap-invoice-customer/', views.rekap_invoice_customer, name='reports_rekap_invoice_customer'),
    path('rekap-pembayaran-invoice-customer/', views.rekap_pembayaran_invoice_customer, name='reports_rekap_pembayaran_invoice_customer'),
]
