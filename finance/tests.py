from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from accounting.models import ClosingPeriod, Journal
from accounting.services import generated_transaction_key
from accounts.models import UserProfile
from finance.models import BankTransaction, CashTransaction, EmployeeCashAdvance, EmployeeCashAdvancePayment, FuelPurchase
from finance.urls import CONFIGS
from core.templatetags.crud_extras import is_money_field
from master.models import Armada, BankAccount, ChartOfAccount, StakeHolder, TransactionType
from tenants.models import Tenant


class BankTransactionLegacyRuleTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='CV Test')
        self.user = get_user_model().objects.create_user(username='admin')
        self.bank_account = self.account('101', 'Bank Utama')
        self.target_account = self.account('102', 'Bank Tujuan')
        self.transaction_account = self.account('601', 'Setoran')
        self.bank = BankAccount.objects.create(
            tenant=self.tenant,
            no_rekening='001',
            nama_bank='Bank A',
            atas_nama='CV Test',
            akun=self.bank_account,
        )
        self.bank_tujuan = BankAccount.objects.create(
            tenant=self.tenant,
            no_rekening='002',
            nama_bank='Bank B',
            atas_nama='CV Test',
            akun=self.target_account,
        )

    def account(self, kode, nama):
        return ChartOfAccount.objects.create(
            tenant=self.tenant,
            kode=kode,
            nama=nama,
            saldo_normal=ChartOfAccount.NormalBalance.DEBET,
        )

    def transaction_type(self, kode):
        return TransactionType.objects.create(
            tenant=self.tenant,
            kode=kode,
            nama=f'Transaksi {kode}',
            akun=self.transaction_account,
        )

    def test_setoran_tunai_uses_kredit_and_clears_debet_like_desktop(self):
        trx = BankTransaction(
            tenant=self.tenant,
            tanggal=date(2026, 7, 23),
            bank_utama=self.bank,
            jenis_transaksi=self.transaction_type('01'),
            debet=Decimal('5000'),
            kredit=Decimal('10000'),
        )

        trx.save_with_business_rules(user=self.user)

        trx.refresh_from_db()
        self.assertEqual(trx.debet, Decimal('0.00'))
        self.assertEqual(trx.kredit, Decimal('10000.00'))
        journal = Journal.objects.get(tenant=self.tenant, transaksi_id=trx.pk, transaksi=generated_transaction_key(trx))
        lines = list(journal.lines.order_by('id').values_list('perkiraan_id', 'debet', 'kredit'))
        self.assertEqual(lines, [(self.bank_account.pk, Decimal('10000.00'), Decimal('0.00')), (self.transaction_account.pk, Decimal('0.00'), Decimal('10000.00'))])

    def test_transfer_antar_bank_requires_admin_fee_and_writes_three_journal_lines(self):
        trx = BankTransaction(
            tenant=self.tenant,
            tanggal=date(2026, 7, 23),
            bank_utama=self.bank,
            jenis_transaksi=self.transaction_type('20'),
            debet=Decimal('10000'),
            bank_tujuan=self.bank_tujuan,
            biaya_adm_bank=Decimal('0'),
        )
        with self.assertRaisesMessage(ValidationError, 'Biaya adm bank tujuan belum diisi.'):
            trx.save_with_business_rules(user=self.user)

        trx.biaya_adm_bank = Decimal('2500')
        trx.kredit = Decimal('100')
        trx.save_with_business_rules(user=self.user)

        trx.refresh_from_db()
        self.assertEqual(trx.kredit, Decimal('0.00'))
        journal = Journal.objects.get(tenant=self.tenant, transaksi_id=trx.pk, transaksi=generated_transaction_key(trx))
        lines = list(journal.lines.order_by('id').values_list('perkiraan_id', 'debet', 'kredit'))
        self.assertEqual(lines, [
            (self.target_account.pk, Decimal('10000.00'), Decimal('0.00')),
            (self.bank_account.pk, Decimal('0.00'), Decimal('12500.00')),
            (self.transaction_account.pk, Decimal('2500.00'), Decimal('0.00')),
        ])


class EmployeeCashAdvanceLegacyRuleTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='CV Test')
        self.user = get_user_model().objects.create_user(username='admin')
        self.cash_account = self.account('101', 'Kas')
        self.loan_account = self.account('1030100', 'Piutang Karyawan')
        self.bank = BankAccount.objects.create(
            tenant=self.tenant,
            no_rekening='0001',
            nama_bank='Kas',
            atas_nama='CV Test',
            akun=self.cash_account,
        )
        self.karyawan = StakeHolder.objects.create(
            tenant=self.tenant,
            kode='K001',
            nama='Budi',
            jenis=StakeHolder.StakeHolderType.KARYAWAN,
        )

    def account(self, kode, nama):
        return ChartOfAccount.objects.create(
            tenant=self.tenant,
            kode=kode,
            nama=nama,
            saldo_normal=ChartOfAccount.NormalBalance.DEBET,
        )

    def test_cash_advance_uses_bank_account_and_source_like_desktop(self):
        trx = EmployeeCashAdvance(
            tenant=self.tenant,
            tanggal=date(2026, 7, 23),
            karyawan=self.karyawan,
            perkiraan_pinjaman=self.loan_account,
            nominal=Decimal('15000'),
            bank=self.bank,
            keterangan='Kas bon',
        )

        trx.save_with_business_rules(user=self.user)

        trx.refresh_from_db()
        self.assertEqual(trx.no_register[:11], 'BON-2026070')
        self.assertEqual(trx.perkiraan_kas, self.cash_account)
        self.assertEqual(trx.sumber_dana, str(self.bank))
        self.assertEqual(trx.saldo, Decimal('15000.00'))
        journal = Journal.objects.get(tenant=self.tenant, transaksi_id=trx.pk, transaksi=generated_transaction_key(trx))
        lines = list(journal.lines.order_by('id').values_list('perkiraan_id', 'debet', 'kredit'))
        self.assertEqual(lines, [
            (self.loan_account.pk, Decimal('15000.00'), Decimal('0.00')),
            (self.cash_account.pk, Decimal('0.00'), Decimal('15000.00')),
        ])

    def test_cash_advance_requires_bank_and_positive_nominal(self):
        trx = EmployeeCashAdvance(
            tenant=self.tenant,
            tanggal=date(2026, 7, 23),
            karyawan=self.karyawan,
            perkiraan_pinjaman=self.loan_account,
            nominal=Decimal('0'),
        )

        with self.assertRaisesMessage(ValidationError, 'Bank belum dipilih.'):
            trx.save_with_business_rules(user=self.user)

        trx.bank = self.bank
        with self.assertRaisesMessage(ValidationError, 'Nominal belum diisi.'):
            trx.save_with_business_rules(user=self.user)

    def test_cash_advance_payment_uses_bank_account_and_rejects_overpayment(self):
        advance = EmployeeCashAdvance.objects.create(
            tenant=self.tenant,
            tanggal=date(2026, 7, 23),
            karyawan=self.karyawan,
            perkiraan_pinjaman=self.loan_account,
            perkiraan_kas=self.cash_account,
            nominal=Decimal('15000'),
            bank=self.bank,
        )
        payment = EmployeeCashAdvancePayment(
            tenant=self.tenant,
            tanggal=date(2026, 7, 23),
            kas_bon_karyawan=advance,
            nominal=Decimal('16000'),
            bank=self.bank,
        )
        with self.assertRaisesMessage(ValidationError, 'Pembayaran melebihi saldo hutang.'):
            payment.save_with_business_rules(user=self.user)

        payment.nominal = Decimal('10000')
        payment.save_with_business_rules(user=self.user)

        payment.refresh_from_db()
        advance.refresh_from_db()
        self.assertEqual(payment.perkiraan_kas, self.cash_account)
        self.assertEqual(payment.sumber_dana, str(self.bank))
        self.assertEqual(payment.hutang, Decimal('15000.00'))
        self.assertEqual(payment.saldo_hutang, Decimal('5000.00'))
        self.assertEqual(advance.pelunasan, Decimal('10000.00'))
        self.assertEqual(advance.status_lunas, EmployeeCashAdvance.StatusLunas.BELUM)
        journal = Journal.objects.get(tenant=self.tenant, transaksi_id=payment.pk, transaksi=generated_transaction_key(payment))
        lines = list(journal.lines.order_by('id').values_list('perkiraan_id', 'debet', 'kredit'))
        self.assertEqual(lines, [
            (self.cash_account.pk, Decimal('10000.00'), Decimal('0.00')),
            (self.loan_account.pk, Decimal('0.00'), Decimal('10000.00')),
        ])

class FuelPurchaseLastKmTests(TestCase):
    def test_last_km_endpoint_returns_latest_km_sekarang_for_armada(self):
        tenant = Tenant.objects.create(name='CV Test')
        user = get_user_model().objects.create_user(username='admin', password='secret')
        UserProfile.objects.create(user=user, tenant=tenant, role=UserProfile.Role.ADMIN)
        armada = Armada.objects.create(tenant=tenant, nopol='AD 1 A', kendaraan='Truck')
        cash = ChartOfAccount.objects.create(tenant=tenant, kode='101', nama='Kas', saldo_normal=ChartOfAccount.NormalBalance.DEBET)
        bank = BankAccount.objects.create(tenant=tenant, no_rekening='001', nama_bank='Kas', atas_nama='CV Test', akun=cash)
        FuelPurchase.objects.create(tenant=tenant, no_bukti='BBM-1', armada=armada, tanggal=date(2026, 7, 1), km_terakhir=100, km_sekarang=150, nominal_bbm=1000, bank=bank)
        FuelPurchase.objects.create(tenant=tenant, no_bukti='BBM-2', armada=armada, tanggal=date(2026, 7, 2), km_terakhir=150, km_sekarang=225, nominal_bbm=1000, bank=bank)

        self.client.login(username='admin', password='secret')
        response = self.client.get('/finance/pembelian-bbm/last-km/', {'armada': armada.pk})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'km_terakhir': 225})

class FuelPurchaseListConfigTests(TestCase):
    def test_fuel_purchase_list_labels_and_nominal_alignment(self):
        labels = dict(CONFIGS['pembelian-bbm'].get_list_headers())

        self.assertEqual(labels['km_terakhir'], 'KM Terakhir')
        self.assertEqual(labels['km_sekarang'], 'KM Sekarang')
        self.assertEqual(labels['nominal_bbm'], 'Nominal BBM')
        self.assertTrue(is_money_field('nominal_bbm'))

class BankTransactionListConfigTests(TestCase):
    def test_bank_transaction_pdf_widths_widen_no_bukti_and_narrow_money_columns(self):
        config = CONFIGS['transaksi-bank']
        fields = config.list_display
        widths = dict(zip(fields, config.list_pdf_widths))

        self.assertGreater(widths['no_bukti'], widths['debet'])
        self.assertGreater(widths['bank_utama.no_rekening'], 0.9)
        self.assertEqual(widths['debet'], widths['kredit'])
        self.assertEqual(widths['debet'], widths['biaya_adm_bank'])

class CashTransactionAccountLookupTests(TestCase):
    def test_lookup_returns_only_active_leaf_tenant_accounts(self):
        tenant = Tenant.objects.create(name='CV Test')
        other_tenant = Tenant.objects.create(name='CV Lain')
        user = get_user_model().objects.create_user(username='admin', password='secret')
        UserProfile.objects.create(user=user, tenant=tenant, role=UserProfile.Role.ADMIN)
        parent = ChartOfAccount.objects.create(
            tenant=tenant,
            kode='600',
            nama='Biaya',
            saldo_normal=ChartOfAccount.NormalBalance.DEBET,
        )
        leaf = ChartOfAccount.objects.create(
            tenant=tenant,
            kode='601',
            nama='Biaya Operasional',
            parent=parent,
            saldo_normal=ChartOfAccount.NormalBalance.DEBET,
        )
        ChartOfAccount.objects.create(
            tenant=tenant,
            kode='602',
            nama='Biaya Nonaktif',
            saldo_normal=ChartOfAccount.NormalBalance.DEBET,
            is_active=False,
        )
        ChartOfAccount.objects.create(
            tenant=other_tenant,
            kode='603',
            nama='Biaya Tenant Lain',
            saldo_normal=ChartOfAccount.NormalBalance.DEBET,
        )

        self.client.login(username='admin', password='secret')
        response = self.client.get('/finance/transaksi-kas/account-lookup/', {'q': 'Biaya'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'results': [{'id': leaf.pk, 'label': str(leaf)}]})

class TransactionClosingActionVisibilityTests(TestCase):
    def test_cash_transaction_list_hides_edit_and_closed_delete_actions(self):
        tenant = Tenant.objects.create(name='CV Test')
        user = get_user_model().objects.create_user(username='admin', password='secret')
        UserProfile.objects.create(user=user, tenant=tenant, role=UserProfile.Role.ADMIN)
        cash_account = ChartOfAccount.objects.create(
            tenant=tenant,
            kode='101',
            nama='Kas',
            saldo_normal=ChartOfAccount.NormalBalance.DEBET,
        )
        expense_account = ChartOfAccount.objects.create(
            tenant=tenant,
            kode='601',
            nama='Biaya Operasional',
            saldo_normal=ChartOfAccount.NormalBalance.DEBET,
        )
        bank = BankAccount.objects.create(
            tenant=tenant,
            no_rekening='001',
            nama_bank='Kas',
            atas_nama='CV Test',
            akun=cash_account,
        )
        transaction = CashTransaction.objects.create(
            tenant=tenant,
            no_bukti='KAS-1',
            tanggal=date(2026, 7, 15),
            akun_kas=cash_account,
            akun_transaksi=expense_account,
            bank=bank,
            nominal_keluar=Decimal('1000'),
        )
        ClosingPeriod.objects.create(tenant=tenant, tanggal=date(2026, 7, 31))

        self.client.login(username='admin', password='secret')
        response = self.client.get('/finance/transaksi-kas/')

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, f'{transaction.uuid}/edit/')
        self.assertNotContains(response, f'{transaction.uuid}/delete/')
        self.assertNotContains(response, '>Edit<')
        self.assertNotContains(response, '>Hapus<')

    def test_cash_transaction_list_warns_on_different_year_period(self):
        tenant = Tenant.objects.create(name='CV Test Warn')
        user = get_user_model().objects.create_user(username='admin-warn', password='secret')
        UserProfile.objects.create(user=user, tenant=tenant, role=UserProfile.Role.ADMIN)
        self.client.login(username='admin-warn', password='secret')
        response = self.client.get('/finance/transaksi-kas/', {'start_date': '2025-06-01', 'end_date': '2026-06-30'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Periode filter Transaksi Kas harus berada pada tahun yang sama.')
