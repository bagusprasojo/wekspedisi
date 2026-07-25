# Blueprint Django SaaS Ekspedisi

Tanggal: 2026-07-19

Dokumen ini adalah rancangan awal aplikasi web pengganti desktop `ekspedisi`.

## Stack

- Backend: Django
- Database: MySQL
- Auth: Django authentication standar
- UI: Django templates
- Interaksi ringan: Alpine.js
- Styling: Tailwind CSS
- Bahasa UI: Bahasa Indonesia
- Tenant model: satu user hanya bisa satu tenant

## Prinsip Desain

- Menyalin perilaku bisnis, istilah, menu, laporan, dan alur kerja desktop.
- Tidak menyalin kode Java/Swing.
- Django monolith dulu, supaya modul bisnis dan akuntansi mudah dijaga.
- Semua model bisnis tenant-scoped.
- Semua operasi transaksi penting lewat service layer, bukan langsung dari view.
- Semua create/update/delete bisnis diaudit.
- Perubahan transaksi dan jurnal harus atomic.

## Struktur App Django Awal

Usulan app:

- `core`
  - middleware tenant aktif
  - base model
  - helper nomor dokumen
  - helper tanggal/format rupiah/terbilang
- `accounts`
  - profil user
  - tenant membership satu user satu tenant
  - role sederhana
- `tenants`
  - data perusahaan
  - setting tenant
  - konfigurasi akun tenant
- `audit`
  - audit trail generik
  - diff before/after
- `master`
  - customer
  - karyawan
  - armada
  - bank/kas
  - perkiraan/akun
  - jenis transaksi
- `finance`
  - transaksi kas
  - transaksi bank
  - pembelian BBM
  - kas bon karyawan
  - pembayaran kas bon
- `invoice`
  - invoice customer
  - pembayaran invoice customer
- `accounting`
  - jurnal
  - jurnal detail
  - buku besar
  - neraca saldo
  - closing
- `reports`
  - PDF
  - Excel export

## Model Fondasi

### Tenant

Pengganti `company` lama.

Field awal:

- `name`
- `address`
- `city`
- `province`
- `postal_code`
- `phone`
- `email`
- `is_active`
- `created_at`
- `updated_at`

### UserProfile

Django `User` tetap dipakai untuk autentikasi.

Field awal:

- `user`
- `tenant`
- `role`
- `created_at`
- `updated_at`

Karena satu user hanya bisa satu tenant, cukup `OneToOneField` ke user dan `ForeignKey` ke tenant.

Role awal:

- `owner`
- `admin`
- `finance`
- `operasional`
- `viewer`

### TenantScopedModel

Abstract base untuk model bisnis:

- `tenant`
- `created_at`
- `updated_at`
- `created_by`
- `updated_by`
- `is_deleted`
- `deleted_at`
- `deleted_by`

Catatan:

- Hard delete menjadi default; data yang sudah direferensikan tabel lain wajib ditahan oleh foreign key PROTECT.
- Unique constraint harus tenant-aware, misalnya `(tenant, no_bukti)`.

## Model Bisnis Awal

### Master

- `StakeHolder`
  - gabungan customer/karyawan/driver seperti tabel lama `stake_holder`
  - field tipe: customer, karyawan, driver, atau kombinasi bila perlu
- `Armada`
  - nopol unik per tenant
  - driver default optional ke `StakeHolder`
- `BankAccount`
  - menggantikan `bank`
  - bisa berupa bank atau kas lewat `is_kas`
  - relasi ke akun/perkiraan
- `ChartOfAccount`
  - menggantikan `perkiraan`
  - parent-child
  - saldo normal DEBET/KREDIT
  - leaf account validation
- `TransactionType`
  - menggantikan `jenis_transaksi`
  - kode unik per tenant
  - relasi ke akun/perkiraan
- `TenantConfig`
  - konfigurasi umum per tenant berbasis key-value
  - `nilai` bertipe string; untuk config akun dapat berisi ID/kode akun seperti `AKUN_BBM_ID`, `AKUN_PPH_ID`, `AKUN_PENDAPATAN_JASA`, `AKUN_PPN_ID`

### Finance

- `CashTransaction`
  - menggantikan `transaksi_kas`
  - menghasilkan jurnal otomatis
- `BankTransaction`
  - menggantikan `transaksi_bank`
  - kode jenis transaksi `20` punya handling transfer antar bank
- `FuelPurchase`
  - menggantikan `transaksi_pembelian_bbm`
  - menghasilkan jurnal BBM
  - menyimpan km terakhir dan km sekarang
- `EmployeeCashAdvance`
  - menggantikan `kas_bon_karyawan`
  - tidak boleh diubah jika sudah ada pelunasan
- `EmployeeCashAdvancePayment`
  - menggantikan `pembayaran_kas_bon`
  - update pelunasan dan status kas bon

### Invoice

- `CustomerInvoice`
  - menggantikan `tagihan_customer`
  - menghasilkan jurnal piutang/pendapatan/PPN
  - tidak boleh diubah jika sudah ada pelunasan
- `CustomerInvoicePayment`
  - menggantikan `pembayaran_tagihan_customer`
  - update pelunasan dan status invoice

### Accounting

- `Journal`
  - jurnal otomatis dan jurnal memorial
- `JournalLine`
  - detail debet/kredit
- `ClosingPeriod`
  - menggantikan `closing`
- `ClosingBankBalance`
  - menggantikan `closing_bank`
- `ClosingAccountBalance`
  - menggantikan `closing_perkiraan`

## Service Layer Wajib

Setiap modul transaksi perlu service eksplisit:

- `create_cash_transaction`
- `update_cash_transaction`
- `delete_cash_transaction`
- `create_bank_transaction`
- `update_bank_transaction`
- `delete_bank_transaction`
- `create_fuel_purchase`
- `update_fuel_purchase`
- `delete_fuel_purchase`
- `create_customer_invoice`
- `update_customer_invoice`
- `delete_customer_invoice`
- `create_customer_invoice_payment`
- `update_customer_invoice_payment`
- `delete_customer_invoice_payment`
- `create_cash_advance`
- `update_cash_advance`
- `delete_cash_advance`
- `create_cash_advance_payment`
- `update_cash_advance_payment`
- `delete_cash_advance_payment`
- `close_period`
- `delete_last_closing`

Setiap service wajib:

- memastikan tenant sesuai user
- validasi closing
- generate nomor dokumen bila insert
- validasi akun leaf untuk jurnal
- simpan data utama
- simpan atau refresh jurnal otomatis
- update status pelunasan bila relevan
- tulis audit trail
- berjalan dalam `transaction.atomic()`

## Audit Trail

Model `AuditLog`:

- `tenant`
- `actor`
- `action`: create, update, delete, restore, login, logout, close_period, generate_journal
- `app_label`
- `model_name`
- `object_id`
- `object_repr`
- `before`
- `after`
- `changes`
- `request_path`
- `ip_address`
- `user_agent`
- `created_at`

Aturan:

- Semua model bisnis diaudit.
- Untuk perubahan penting, simpan before/after lengkap.
- Untuk transaksi yang memicu jurnal, audit transaksi dan jurnalnya.
- Untuk update pelunasan otomatis, audit perubahan status invoice/kas bon.

## Tenant Isolation

Karena satu user hanya satu tenant:

- Tenant aktif diambil dari `request.user.userprofile.tenant`.
- Middleware menolak akses bila user belum punya tenant.
- Semua QuerySet view harus filter `tenant=request.tenant`.
- Semua create harus assign `tenant=request.tenant`.
- Semua FK antar model bisnis harus tenant-consistent.
- Admin Django perlu dibatasi tenant atau hanya dipakai superuser internal.

## Nomor Dokumen

Gunakan model `DocumentSequence`:

- `tenant`
- `document_type`
- `period`
- `last_number`

Contoh `document_type`:

- `KAS`
- `BNK`
- `BBM`
- `BON`
- `BYR`
- `BKM`
- `JUR`
- `INV`

Nomor dibuat dalam transaksi database dengan lock row agar aman secara paralel.

Format default:

- `KAS-YYYYMM0001`
- `BNK-YYYYMM0001`
- `BBM-YYYYMM0001`
- `BON-YYYYMM0001`
- `BYR-YYYYMM0001`
- `BKM-YYYYMM0001`
- `JUR-YYYYMM0001`
- `001/ROMAWI/INV_TBL/YYYY`

## UI Web

Layout:

- sidebar kiri
- topbar ringkas
- halaman list dengan filter tanggal, search, pagination 20
- halaman create/edit
- modal lookup untuk customer, karyawan, armada, bank, akun
- tombol aksi konsisten: tambah, edit, hapus, cetak, refresh

Tailwind:

- desain admin SaaS yang padat dan efisien
- tidak menggunakan landing page sebagai layar utama
- fokus pada tabel, form, filter, dan laporan

Alpine.js:

- dropdown/menu
- modal lookup
- confirm dialog
- dynamic rows untuk jurnal detail
- perhitungan nilai invoice/PPN/PPH di browser sebelum submit

## Urutan Implementasi Disarankan

1. Scaffold Django project di root `wekspedisi`.
2. Setup MySQL, env, settings split, Tailwind pipeline.
3. Implement `tenants`, `accounts`, `core`, `audit`.
4. Implement master data: tenant, stakeholder, armada, bank/kas, akun, jenis transaksi, config.
5. Implement accounting base: jurnal dan validasi akun leaf.
6. Implement transaksi kas dan jurnal otomatis.
7. Implement transaksi bank dan jurnal otomatis.
8. Implement pembelian BBM.
9. Implement invoice dan pembayaran invoice.
10. Implement kas bon dan pembayaran kas bon.
11. Implement closing.
12. Implement laporan PDF/Excel.
13. Implement migrasi data dari `ekspedisi.sql` untuk tenant pertama.

## Test Minimum

Test wajib untuk tahap awal:

- user hanya melihat data tenant sendiri
- nomor dokumen unik per tenant dan periode
- transaksi sebelum/saat closing ditolak
- update transaksi lama yang sudah closing ditolak
- transaksi kas menghasilkan jurnal benar
- transaksi bank transfer antar bank menghasilkan jurnal benar
- invoice menghasilkan jurnal piutang/pendapatan/PPN
- pembayaran invoice update pelunasan dan status
- kas bon tidak bisa diubah setelah dibayar
- pembayaran kas bon update pelunasan dan status
- audit trail tercatat untuk create/update/delete


## Platform Superadmin

Superadmin platform memakai Django `User.is_superuser` dan tidak terikat ke tenant. User superadmin boleh tidak memiliki `UserProfile`.

Route awal:

- `/platform/tenants/`: daftar tenant dan user tenant
- `/platform/tenants/admission/`: admission tenant baru sekaligus pembuatan owner/admin tenant pertama
- `/platform/tenants/users/new/`: pembuatan user untuk tenant yang sudah ada

Batasan awal:

- Superadmin mengelola onboarding tenant dan user tenant.
- User tenant tetap hanya boleh punya satu tenant melalui `UserProfile`.
- Akses data transaksi tenant oleh superadmin belum dibuat sebagai mode support; ini perlu desain khusus agar audit dan privasi tenant tetap jelas.

