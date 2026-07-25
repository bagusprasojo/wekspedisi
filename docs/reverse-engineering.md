# Reverse Engineering Aplikasi Ekspedisi Desktop

Tanggal: 2026-07-19

Dokumen ini merangkum perilaku bisnis, struktur menu, istilah, laporan, dan alur kerja dari aplikasi desktop Java Swing `ekspedisi`. Tujuan dokumen ini adalah menjadi spesifikasi awal untuk implementasi ulang berbasis web di folder `wekspedisi` menggunakan Django, Alpine.js, Tailwind, dan MySQL.

## Keputusan Produk Baru

- Project web baru memakai folder `wekspedisi` sebagai root.
- Database tetap MySQL.
- Aplikasi bersifat multi-tenant.
- Satu user hanya bisa tergabung ke satu tenant.
- UI memakai Bahasa Indonesia.
- Autentikasi memakai autentikasi standar Django.
- Semua model bisnis diaudit, dengan detail before/after untuk perubahan penting.
- Target migrasi bukan menyalin kode Java, tetapi menyalin perilaku bisnis, struktur menu, istilah, laporan, dan alur kerja.

## Sumber yang Dibaca

- `../pom.xml`
- `../ekspedisi.sql`
- `../src/main/java/com/bprasojo/ekspedisi/MainForm.java`
- DAO utama:
  - `TransaksiKasDAO`
  - `TransaksiBankDAO`
  - `TagihanCustomerDAO`
  - `PembayaranTagihanCustomerDAO`
  - `KasBonKaryawanDAO`
  - `PembayaranKasBonDAO`
  - `TransaksiPembelianBBMDAO`
  - `ClosingDAO`
  - `JurnalDAO`
  - `ParentDAO`
- Report Jasper di `../src/main/resources/reports`

## Gambaran Aplikasi Lama

Aplikasi lama adalah aplikasi desktop Java Swing berbasis Maven dengan entry point `com.bprasojo.ekspedisi.MainForm`. Database lama hardcoded ke MySQL lokal:

- database: `ekspedisi`
- user: `root`
- password kosong

Aplikasi berfokus pada operasional dan keuangan ekspedisi:

- master customer, karyawan, armada, bank, akun/perkiraan
- transaksi kas
- transaksi bank
- pembelian BBM armada
- kas bon karyawan
- invoice customer
- pembayaran invoice
- jurnal, buku besar, neraca saldo
- closing bulanan
- laporan PDF/Jasper

## Struktur Menu Lama

Menu utama dari `MainForm`:

- File
  - Login
  - Exit
- Master Data
  - Customer
  - Armada
  - Karyawan
- Keuangan
  - Mutasi Kas
    - Transaksi Kas
    - Pembelian BBM
    - Rekap Transaksi Kas
    - Riwayat Pembelian BBM
  - Transaksi Bank
    - Transaksi Bank
    - Rekening Koran
    - Rekap Transaksi
    - Rekap Saldo Bank
  - Kas Bon Karyawan
    - Input Kas Bon
    - Pembayaran Kas Bon
    - Rekap Transaksi
    - Rekap Saldo Kasbon
  - Invoice Customer
    - Buat Invoice
    - Pembayaran Invoice
    - Rekap Invoice Customer
    - Rekap Pembayaran Invoice Customer
  - Closing
    - Closing
- Akuntansi
  - Jurnal Penyesuaian
  - Perkiraan / Akun
  - Jenis Transaksi
  - Laporan
    - Daftar Jurnal
    - Buku Besar
    - Neraca Saldo
  - Perkiraan
- Setting
  - Back Up Database

Menu web baru sebaiknya mempertahankan istilah dan pengelompokan ini agar transisi user lama mudah.

## Tabel Database Lama

Tabel fisik yang ditemukan di `ekspedisi.sql`:

- `armada`
- `bank`
- `closing`
- `closing_bank`
- `closing_perkiraan`
- `company`
- `config`
- `jenis_transaksi`
- `jurnal`
- `jurnal_detail`
- `kas_bon_karyawan`
- `pembayaran_kas_bon`
- `pembayaran_tagihan_customer`
- `perkiraan`
- `stake_holder`
- `tagihan_customer`
- `transaksi_bank`
- `transaksi_kas`
- `transaksi_pembelian_bbm`
- `users`

View database lama:

- `v_akun_transaksi`
- `v_mutasi_bank`
- `v_mutasi_kas`

Catatan web:

- View lama dapat diganti dengan Django QuerySet/service/report query.
- Semua tabel bisnis baru perlu `tenant_id`.
- User lama `users` tidak perlu disalin strukturnya karena aplikasi baru memakai Django auth.
- `company` lama menjadi kandidat awal model `Tenant`.

## Konfigurasi Akun Lama

Config yang ditemukan:

- `PIUTANG_JASA_ID = 12`
- `KAS_ID_ = 3`
- `AKUN_BBM_ID = 85`
- `AKUN_PPH_ID = 107`
- `AKUN_PENDAPATAN_JASA = 62`
- `AKUN_PPN_ID = 36`

Catatan:

- Ada potensi typo/historis pada key `KAS_ID_`, sementara kode form juga mencari `KAS_ID`.
- Di aplikasi web, konfigurasi akun harus dibuat per tenant, bukan global.
- Nama key perlu distandarkan, tetapi migrasi harus tetap bisa membaca key lama.

## Jenis Transaksi Bank Lama

Data awal `jenis_transaksi`:

- `01` Setoran Tunai
- `02` Penarikan
- `03` Bagi Hasil/Bunga
- `04` Koreksi
- `06` Tutup Buku
- `08` Administrasi Bank
- `20` Transfer Antar Bank

Kode `20` memiliki perlakuan khusus pada jurnal transaksi bank.

## Pola Nomor Dokumen

Nomor dokumen lama dibuat dari prefix + tahun bulan + nomor urut 4 digit, kecuali invoice.

- Transaksi kas: `KAS-yyyyMM0001`
- Transaksi bank: `BNK-yyyyMM0001`
- Pembelian BBM: `BBM-yyyyMM0001`
- Kas bon karyawan: `BON-yyyyMM0001`
- Pembayaran kas bon: `BYR-yyyyMM0001`
- Pembayaran invoice: `BKM-yyyyMM0001`
- Jurnal memorial: `JUR-yyyyMM0001`
- Invoice customer: `001/ROMAWI/INV_TBL/yyyy`, contoh bulan memakai angka Romawi.

Catatan SaaS:

- Nomor dokumen harus unik per tenant.
- Generate nomor harus atomic agar aman saat ada beberapa user input bersamaan.
- Format lama perlu dipertahankan sebagai default agar laporan dan kebiasaan user tetap sama.

## Aturan Closing

Aturan umum dari `ParentDAO.validasiClosing` dan `ClosingDAO`:

- Transaksi dengan tanggal <= tanggal closing terakhir tidak boleh disimpan, diubah, dijurnal, atau dihapus.
- Saat update, tanggal transaksi lama juga dicek. Jika transaksi lama sudah masuk periode closing, update ditolak.
- Closing harus dilakukan pada akhir bulan.
- Closing harus berurutan per bulan dari closing terakhir.
- Hanya closing terakhir yang boleh dihapus.
- Closing menyimpan saldo bank ke `closing_bank`.
- Closing menyimpan saldo akun/perkiraan ke `closing_perkiraan`.

Catatan web:

- Validasi closing harus ditempatkan di service layer, bukan hanya form.
- Semua transaksi yang membuat jurnal harus berada dalam satu database transaction.
- Closing harus tenant-scoped.

## Jurnal Otomatis

Setiap transaksi utama membuat jurnal otomatis dengan pola:

- hapus jurnal lama berdasarkan `transaksi_id` dan nama transaksi
- simpan jurnal header
- simpan jurnal detail baru
- lakukan semua dalam transaksi database

`JurnalDAO` juga menolak akun yang masih punya anak. Artinya jurnal detail hanya boleh memakai akun leaf.

### Transaksi Kas

Jika `nominal_masuk > 0`:

- Debet: akun kas
- Kredit: akun transaksi

Jika `nominal_keluar > 0`:

- Debet: akun transaksi
- Kredit: akun kas

### Transaksi Bank

Jika jenis transaksi kode `20` atau Transfer Antar Bank:

- Debet: akun bank tujuan sebesar `debet`
- Kredit: akun bank utama sebesar `debet + biaya_adm_bank`
- Debet: akun jenis transaksi sebesar `biaya_adm_bank`

Selain kode `20`:

- Jika `kredit > 0`:
  - Debet: akun bank utama
  - Kredit: akun jenis transaksi
- Jika `debet > 0`:
  - Debet: akun jenis transaksi
  - Kredit: akun bank utama

Catatan: nama field `debet`/`kredit` di transaksi bank lama merepresentasikan arah mutasi bank berdasarkan kode lama. Perlu diuji ulang saat implementasi UI.

### Invoice Customer

Saat invoice dibuat:

- Debet: akun piutang invoice sebesar nilai pekerjaan + PPN
- Kredit: akun pendapatan jasa sebesar nilai pekerjaan
- Kredit: akun PPN sebesar PPN

Invoice tidak boleh diubah atau dihapus jika sudah ada pelunasan.

### Pembayaran Invoice Customer

Saat pembayaran invoice:

- Debet: akun bank/kas sebesar `nominal_kas`
- Debet: akun PPH sebesar `pph`
- Kredit: akun piutang invoice sebesar total pembayaran

Setelah simpan/hapus pembayaran, sistem menghitung ulang pelunasan invoice:

- total pelunasan = sum(`nominal_kas + pph`)
- status `Lunas` jika total invoice <= total pelunasan
- selain itu `Belum`

### Kas Bon Karyawan

Saat kas bon dibuat:

- Debet: akun pinjaman karyawan
- Kredit: akun kas/bank

Kas bon tidak boleh diubah/dihapus jika sudah ada pelunasan.

### Pembayaran Kas Bon

Saat pembayaran kas bon:

- Debet: akun bank/kas
- Kredit: akun pinjaman karyawan dari kas bon

Setelah simpan/hapus pembayaran, sistem menghitung ulang pelunasan kas bon:

- total pelunasan = sum(`nominal`)
- status `Lunas` jika nominal kas bon <= total pelunasan
- selain itu `Belum`

### Pembelian BBM

Saat pembelian BBM:

- Debet: akun BBM dari config
- Kredit: akun bank/kas

Sistem juga mengambil KM terakhir armada dari transaksi BBM sebelumnya berdasarkan nopol.

## Pola List dan Filter

Mayoritas list lama memakai pola:

- filter tanggal awal dan tanggal akhir
- filter teks bebas
- pagination 20 baris
- sort `tanggal desc, id desc`

Pola ini perlu jadi standar UI web untuk semua modul transaksi.

## Laporan Lama

Report Jasper yang ditemukan:

- `Invoice`
- `SlipInvoice`
- `Kwitansi`
- `KwitansiInvoice`
- `DaftarInvoice`
- `DaftarPembayaranInvoice`
- `RekapTransaksiKas`
- `RekapTransaksiBank`
- `RekapTramsaksiKasBon`
- `RiwayatPembelianBBM`
- `RekeningKoran`
- `SaldoBank`
- `SaldoKasBon`
- `DaftarJurnal`
- `BukuBesar`
- `NeracaSaldo`
- `Company`
- `Blank_A4`

Catatan web:

- Layout visual laporan perlu ditiru dari `.jrxml`, tetapi engine web bisa memakai HTML-to-PDF.
- Font DejaVu lama disertakan untuk PDF. Web perlu menentukan font PDF yang stabil.

## Risiko dan Catatan Migrasi

- Kode lama memakai delete fisik untuk transaksi. Web SaaS memakai hard delete dengan proteksi foreign key untuk data yang sudah dipakai.
- Beberapa nama field lama tidak konsisten kapitalisasinya, misalnya `akun_Kas_Id`, `nominal_BBM`.
- Key config `KAS_ID_` dan referensi `KAS_ID` perlu dikonfirmasi saat migrasi.
- Beberapa relasi foreign key tidak lengkap di SQL lama. Django model harus menegakkan relasi secara eksplisit.
- Semua query lama belum tenant-aware. Implementasi baru wajib menyaring semua data berdasarkan tenant user.
- Semua nomor dokumen lama global. Implementasi baru harus per tenant.
- Audit trail perlu merekam perubahan status otomatis juga, bukan hanya perubahan form manual.


