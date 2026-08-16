from datetime import date
from decimal import Decimal
from unittest import SkipTest

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import UserProfile
from accounting.models import ClosingBankBalance, ClosingPeriod, Journal
from finance.models import BankTransaction, CashTransaction, EmployeeCashAdvance, EmployeeCashAdvancePayment, FuelPurchase
from invoice.models import CustomerInvoice, CustomerInvoicePayment
from master.models import Armada, BankAccount, ChartOfAccount, StakeHolder, TransactionType
from reports import services
from tenants.models import Tenant

def require_weasyprint():
    try:
        from core.exporters import _weasy_response

        _weasy_response('test.pdf', '<p>x</p>')
    except Exception as exc:
        raise SkipTest(f'WeasyPrint native dependency belum tersedia: {exc}') from exc


class RekeningKoranLegacyMutationTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='CV Test')
        self.user = get_user_model().objects.create_user(username='lia')
        self.bank_account = self.account('101', 'Bank')
        self.offset_account = self.account('601', 'Biaya')
        self.bank = BankAccount.objects.create(tenant=self.tenant, no_rekening='001', nama_bank='Bank A', atas_nama='CV Test', akun=self.bank_account)
        self.other_bank = BankAccount.objects.create(tenant=self.tenant, no_rekening='002', nama_bank='Bank B', atas_nama='CV Test', akun=self.account('102', 'Bank B'))
        self.transaction_type = TransactionType.objects.create(tenant=self.tenant, kode='20', nama='Transfer', akun=self.offset_account)
        self.customer = StakeHolder.objects.create(tenant=self.tenant, nama='Customer A', jenis=StakeHolder.StakeHolderType.CUSTOMER)
        self.employee = StakeHolder.objects.create(tenant=self.tenant, nama='Budi', jenis=StakeHolder.StakeHolderType.KARYAWAN)

    def account(self, kode, nama):
        return ChartOfAccount.objects.create(tenant=self.tenant, kode=kode, nama=nama, saldo_normal=ChartOfAccount.NormalBalance.DEBET)

    def test_rekening_koran_uses_legacy_v_mutasi_bank_sources(self):
        trx = BankTransaction.objects.create(
            tenant=self.tenant,
            no_bukti='BNK-1',
            tanggal=date(2026, 7, 2),
            bank_utama=self.bank,
            jenis_transaksi=self.transaction_type,
            debet=Decimal('10'),
            kredit=Decimal('100'),
            biaya_adm_bank=Decimal('5'),
            uraian='Mutasi bank',
            created_by=self.user,
        )
        BankTransaction.objects.create(
            tenant=self.tenant,
            no_bukti='BNK-2',
            tanggal=date(2026, 7, 3),
            bank_utama=self.other_bank,
            bank_tujuan=self.bank,
            jenis_transaksi=self.transaction_type,
            debet=Decimal('200'),
            kredit=Decimal('0'),
            uraian='Transfer masuk',
            created_by=self.user,
        )
        CashTransaction.objects.create(
            tenant=self.tenant,
            no_bukti='KAS-1',
            tanggal=date(2026, 7, 4),
            akun_kas=self.bank_account,
            akun_transaksi=self.offset_account,
            bank=self.bank,
            nominal_keluar=Decimal('30'),
            created_by=self.user,
        )
        advance = EmployeeCashAdvance.objects.create(
            tenant=self.tenant,
            no_register='BON-1',
            tanggal=date(2026, 7, 5),
            karyawan=self.employee,
            perkiraan_pinjaman=self.offset_account,
            perkiraan_kas=self.bank_account,
            nominal=Decimal('40'),
            bank=self.bank,
            created_by=self.user,
        )
        EmployeeCashAdvancePayment.objects.create(
            tenant=self.tenant,
            no_register='BYR-1',
            tanggal=date(2026, 7, 6),
            kas_bon_karyawan=advance,
            perkiraan_kas=self.bank_account,
            nominal=Decimal('15'),
            bank=self.bank,
            keterangan='Bayar bon',
            created_by=self.user,
        )
        armada = Armada.objects.create(tenant=self.tenant, nopol='AD 1 A', kendaraan='Truck')
        FuelPurchase.objects.create(
            tenant=self.tenant,
            no_bukti='BBM-1',
            tanggal=date(2026, 7, 7),
            armada=armada,
            km_terakhir=0,
            km_sekarang=10,
            nominal_bbm=Decimal('20'),
            bank=self.bank,
            keterangan='Solar',
            created_by=self.user,
        )
        invoice = CustomerInvoice.objects.create(
            tenant=self.tenant,
            no_invoice='INV-1',
            tanggal=date(2026, 7, 8),
            customer=self.customer,
            pekerjaan='Angkut',
            nilai_pekerjaan=Decimal('1000'),
            ppn=Decimal('110'),
            total=Decimal('1110'),
            perkiraan_piutang=self.offset_account,
        )
        CustomerInvoicePayment.objects.create(
            tenant=self.tenant,
            no_register='BKM-1',
            tanggal=date(2026, 7, 9),
            tagihan_customer=invoice,
            nominal_kas=Decimal('111'),
            pph=Decimal('11'),
            ppn=Decimal('12'),
            perkiraan_kas=self.bank_account,
            bank=self.bank,
            created_by=self.user,
        )

        rows = services.rekening_koran(self.tenant, date(2026, 7, 1), date(2026, 7, 31), self.bank)

        self.assertEqual(len(rows), 10)
        self.assertEqual(rows[0]['uraian'], trx.uraian)
        self.assertIn({'kode': '08', 'debet': Decimal('5.00'), 'kredit': 0}, [{'kode': row['kode'], 'debet': row['debet'], 'kredit': row['kredit']} for row in rows])
        self.assertIn('Biaya [Via Mutasi Kas]', [row['uraian'] for row in rows])
        self.assertIn('Kas Bon a.n. Budi [Via Kas Bon]', [row['uraian'] for row in rows])
        self.assertEqual(sum((row['kredit'] - row['debet'] for row in rows), Decimal('0')), Decimal('321.00'))

    def test_rekening_koran_opening_balance_uses_closing_bank_then_mutasi(self):
        closing = ClosingPeriod.objects.create(tenant=self.tenant, tanggal=date(2026, 6, 30))
        ClosingBankBalance.objects.create(tenant=self.tenant, closing=closing, bank=self.bank, tanggal=date(2026, 6, 30), saldo_akhir=Decimal('1000'))
        CashTransaction.objects.create(
            tenant=self.tenant,
            no_bukti='KAS-BEFORE',
            tanggal=date(2026, 7, 10),
            akun_kas=self.bank_account,
            akun_transaksi=self.offset_account,
            bank=self.bank,
            nominal_masuk=Decimal('25'),
            created_by=self.user,
        )

        saldo = services.rekening_koran_saldo_awal(self.tenant, date(2026, 8, 1), self.bank)

        self.assertEqual(saldo, Decimal('1025.00'))

    def test_rekening_koran_pdf_formats_opening_balance(self):
        require_weasyprint()
        UserProfile.objects.create(user=self.user, tenant=self.tenant, role=UserProfile.Role.ADMIN)
        closing = ClosingPeriod.objects.create(tenant=self.tenant, tanggal=date(2026, 6, 30))
        ClosingBankBalance.objects.create(tenant=self.tenant, closing=closing, bank=self.bank, tanggal=date(2026, 6, 30), saldo_akhir=Decimal('1000000'))

        self.client.force_login(self.user)
        response = self.client.get(
            '/reports/rekening-koran/',
            {'bank': self.bank.pk, 'start_date': '2026-07-01', 'end_date': '2026-07-31', 'export': 'pdf'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))

class ReportLayoutTests(TestCase):
    def test_neraca_saldo_formats_money_like_other_reports(self):
        tenant = Tenant.objects.create(name='CV Test')
        user = get_user_model().objects.create_user(username='admin-neraca')
        UserProfile.objects.create(user=user, tenant=tenant, role=UserProfile.Role.ADMIN)
        account = ChartOfAccount.objects.create(
            tenant=tenant,
            kode='501',
            nama='Biaya',
            saldo_normal=ChartOfAccount.NormalBalance.DEBET,
        )
        journal = Journal.objects.create(
            tenant=tenant,
            no_jurnal='JUR-1',
            tanggal=date(2026, 7, 1),
            transaksi='jurnal_memorial',
            keterangan='Biaya',
        )
        journal.lines.create(tenant=tenant, perkiraan=account, debet=Decimal('1250000.00'), kredit=Decimal('0.00'))

        self.client.force_login(user)
        response = self.client.get('/reports/neraca-saldo/', {'end_date': '2026-07-31'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '1.250.000')
        self.assertContains(response, '>0<')
        self.assertNotContains(response, '1.250.000,00')

    def test_neraca_saldo_export_excel_success(self):
        tenant = Tenant.objects.create(name='CV Test')
        user = get_user_model().objects.create_user(username='admin-neraca-excel')
        UserProfile.objects.create(user=user, tenant=tenant, role=UserProfile.Role.ADMIN)
        account = ChartOfAccount.objects.create(
            tenant=tenant,
            kode='501',
            nama='Biaya',
            saldo_normal=ChartOfAccount.NormalBalance.DEBET,
        )
        journal = Journal.objects.create(
            tenant=tenant,
            no_jurnal='JUR-1',
            tanggal=date(2026, 7, 1),
            transaksi='jurnal_memorial',
            keterangan='Biaya',
        )
        journal.lines.create(tenant=tenant, perkiraan=account, debet=Decimal('1250000.00'), kredit=Decimal('0.00'))

        self.client.force_login(user)
        response = self.client.get('/reports/neraca-saldo/', {'start_date': '2026-07-01', 'end_date': '2026-07-31', 'export': 'excel'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    def test_rekap_transaksi_kas_pdf_pc_column_fits_administrator(self):
        require_weasyprint()
        tenant = Tenant.objects.create(name='CV Test')
        user = get_user_model().objects.create_user(username='administrator')
        UserProfile.objects.create(user=user, tenant=tenant, role=UserProfile.Role.ADMIN)
        kas = ChartOfAccount.objects.create(tenant=tenant, kode='101', nama='Kas', saldo_normal=ChartOfAccount.NormalBalance.DEBET)
        biaya = ChartOfAccount.objects.create(tenant=tenant, kode='501', nama='Biaya', saldo_normal=ChartOfAccount.NormalBalance.DEBET)
        bank = BankAccount.objects.create(tenant=tenant, no_rekening='001', nama_bank='Kas', atas_nama='CV Test', akun=kas)
        CashTransaction.objects.create(
            tenant=tenant,
            no_bukti='KAS-1',
            tanggal=date(2026, 7, 1),
            akun_kas=kas,
            akun_transaksi=biaya,
            bank=bank,
            nominal_keluar=Decimal('1000'),
            created_by=user,
        )

        self.client.force_login(user)
        response = self.client.get('/reports/rekap-transaksi-kas/', {'start_date': '2026-07-01', 'end_date': '2026-07-31', 'export': 'pdf'})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_riwayat_pembelian_bbm_pdf_pc_and_distance_columns_have_room(self):
        require_weasyprint()
        tenant = Tenant.objects.create(name='CV Test')
        user = get_user_model().objects.create_user(username='administrator')
        UserProfile.objects.create(user=user, tenant=tenant, role=UserProfile.Role.ADMIN)
        kas = ChartOfAccount.objects.create(tenant=tenant, kode='101', nama='Kas', saldo_normal=ChartOfAccount.NormalBalance.DEBET)
        bbm = ChartOfAccount.objects.create(tenant=tenant, kode='501', nama='BBM', saldo_normal=ChartOfAccount.NormalBalance.DEBET)
        from master.models import TenantConfig

        TenantConfig.objects.create(tenant=tenant, kode='AKUN_BBM_ID', nilai=str(bbm.pk))
        bank = BankAccount.objects.create(tenant=tenant, no_rekening='001', nama_bank='Kas', atas_nama='CV Test', akun=kas)
        armada = Armada.objects.create(tenant=tenant, nopol='AD 1 A', kendaraan='Truck')
        FuelPurchase.objects.create(
            tenant=tenant,
            no_bukti='BBM-1',
            tanggal=date(2026, 7, 1),
            armada=armada,
            km_terakhir=1,
            km_sekarang=123456,
            nominal_bbm=Decimal('1000'),
            bank=bank,
            keterangan='Solar',
            created_by=user,
        )

        self.client.force_login(user)
        response = self.client.get('/reports/riwayat-pembelian-bbm/', {'start_date': '2026-07-01', 'end_date': '2026-07-31', 'export': 'pdf'})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_trial_balance_include_and_exclude_closing_journal(self):
        tenant = Tenant.objects.create(name='CV Test')
        user = get_user_model().objects.create_user(username='admin-tb')
        UserProfile.objects.create(user=user, tenant=tenant, role=UserProfile.Role.ADMIN)
        rev = ChartOfAccount.objects.create(tenant=tenant, kode='401', nama='Pendapatan', saldo_normal=ChartOfAccount.NormalBalance.KREDIT, golongan='LABA/RUGI', kelompok='PENDAPATAN')
        ret = ChartOfAccount.objects.create(tenant=tenant, kode='302', nama='Laba Ditahan', saldo_normal=ChartOfAccount.NormalBalance.KREDIT, golongan='PASIVA', kelompok='EQUITAS')
        from master.models import TenantConfig
        TenantConfig.objects.create(tenant=tenant, kode='AKUN_LABA_DITAHAN_ID', nilai=str(ret.pk))

        from accounting.models import Journal, JournalLine, ClosingPeriod
        j1 = Journal.objects.create(tenant=tenant, no_jurnal='JUR-1', tanggal=date(2026, 12, 1), transaksi='jurnal_memorial')
        JournalLine.objects.create(tenant=tenant, journal=j1, perkiraan=rev, debet=0, kredit=Decimal('1000000'))

        ClosingPeriod(tenant=tenant, tanggal=date(2026, 12, 31)).save_with_business_rules(user=user)

        # Trial balance WITHOUT include_closing (default): rev has mutasi kredit 1.000.000
        tb_default = services.trial_balance(tenant, start_date=date(2026, 12, 1), end_date=date(2026, 12, 31), include_closing=False)
        rev_row_def = next(r for r in tb_default if r['account'] == rev)
        self.assertEqual(rev_row_def['kredit'], Decimal('1000000'))
        self.assertEqual(rev_row_def['akhir_kredit'], Decimal('1000000'))

        # Trial balance WITH include_closing=True: closing journal zeros rev (mutasi debet 1.000.000), ret gets kredit 1.000.000
        tb_closing = services.trial_balance(tenant, start_date=date(2026, 12, 1), end_date=date(2026, 12, 31), include_closing=True)
        rev_row_clo = next(r for r in tb_closing if r['account'] == rev)
        ret_row_clo = next(r for r in tb_closing if r['account'] == ret)
        self.assertEqual(rev_row_clo['debet'], Decimal('1000000'))
        self.assertEqual(rev_row_clo['akhir_kredit'], Decimal('0'))
        self.assertEqual(ret_row_clo['kredit'], Decimal('1000000'))

        self.client.force_login(user)
        res = self.client.get('/reports/neraca-saldo/', {'start_date': '2026-12-01', 'end_date': '2026-12-31', 'include_closing': '1'})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Sertakan Jurnal Tutup Tahun')
