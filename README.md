# Wekspedisi

Project web SaaS pengganti aplikasi desktop Java Swing `ekspedisi`.

Keputusan awal:

- Backend: Django 5.2 LTS
- Database: MySQL
- Frontend: Django templates, Alpine.js, Tailwind CSS
- Bahasa UI: Bahasa Indonesia
- Multi-tenant: ya
- Relasi user-tenant: satu user hanya bisa satu tenant
- Auth: Django auth standar
- Superadmin platform: Django `is_superuser`, tidak terikat tenant
- Audit trail: semua model bisnis
- Delete policy: hard delete; data yang sudah dipakai relasi lain dilindungi foreign key `PROTECT`

Fitur fondasi yang sudah ada:

- Tenant dan user profile per tenant
- Platform administration untuk superadmin di `/platform/tenants/`
- Admission tenant + pembuatan owner/admin tenant pertama
- Pembuatan user untuk tenant yang sudah ada
- Audit log untuk CRUD tenant dan admission platform
- Master data, finance, invoice, dan accounting model awal
- Sidebar menu tenant mengikuti struktur desktop
- CRUD list/tambah/edit/hapus hard-delete untuk menu awal
- Dropdown ForeignKey di form difilter per tenant aktif

Menu/form yang sudah tersedia:

- Master Data
  - Customer/Karyawan
  - Armada
  - Bank/Kas
- Keuangan
  - Transaksi Kas
  - Pembelian BBM
  - Transaksi Bank
  - Kas Bon Karyawan
  - Pembayaran Kas Bon
  - Invoice Customer
  - Pembayaran Invoice
- Akuntansi
  - Jurnal Penyesuaian
  - Perkiraan/Akun
  - Jenis Transaksi
  - Closing
- Setting
  - Config

Aturan bisnis yang sudah diimplementasikan:

- Nomor dokumen otomatis per tenant dan periode:
  - `KAS`, `BNK`, `BBM`, `BON`, `BYR`, `BKM`, `JUR`
  - invoice format `001/VII/INV_TBL/2026`
- Validasi transaksi tidak boleh masuk periode yang sudah closing
- Validasi closing harus akhir bulan dan berurutan
- Jurnal otomatis untuk:
  - Transaksi Kas
  - Transaksi Bank
  - Pembelian BBM
  - Invoice Customer
  - Pembayaran Invoice
  - Kas Bon Karyawan
  - Pembayaran Kas Bon
- Update pelunasan dan status lunas untuk invoice dan kas bon
- Proteksi invoice/kas bon agar tidak bisa diubah/dihapus jika sudah dibayar
- Validasi akun jurnal harus akun leaf
- Jurnal Penyesuaian manual dengan detail baris debet/kredit, validasi balance, dan audit trail
- Closing otomatis membentuk snapshot saldo bank/kas dan saldo perkiraan dari jurnal sampai tanggal closing
- Laporan HTML dan export CSV awal untuk Daftar Jurnal, Buku Besar, Neraca Saldo, dan Saldo Bank/Kas
- Filter tanggal standar pada list transaksi berbasis field tanggal
- Lookup searchable berbasis Alpine untuk field relasi di form CRUD dan Jurnal Penyesuaian
- Autocomplete driver Armada memakai satu input text dengan hidden foreign key dan endpoint lookup tenant-aware
- Preview perhitungan Invoice Customer: PPN dan total invoice
- Preview dan kalkulasi Pembayaran Invoice: PPH persen dan total pembayaran
- UX Transaksi Bank untuk transfer antar bank, hide/show field relevan, preview jurnal, dan validasi backend tambahan
- Hard delete untuk CRUD/transaksi dengan proteksi foreign key; data yang tidak dipakai bisa dihapus fisik dan kode bisa dipakai ulang

Catatan batasan tahap ini:

- Export PDF dan XLSX native belum diimplementasikan; laporan awal tersedia sebagai HTML dan CSV.
- UI transaksi sudah punya lookup searchable awal; modal lookup penuh seperti desktop belum diimplementasikan.

Dokumen awal:

- [Reverse Engineering](docs/reverse-engineering.md)
- [Blueprint Django](docs/django-blueprint.md)











"# wekspedisi" 
