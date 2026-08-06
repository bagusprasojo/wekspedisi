from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import UserProfile
from accounting.forms import JournalLineForm
from accounting.models import ClosingPeriod, Journal, JournalLine
from master.models import BankAccount, ChartOfAccount
from tenants.models import Tenant

class JournalAdjustmentFormTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='CV Test')
        self.parent = self.account('100', 'Aktiva')
        self.cash = self.account('101', 'Kas')
        self.expense = self.account('601', 'Biaya Operasional')
        self.revenue = self.account('401', 'Pendapatan', ChartOfAccount.NormalBalance.KREDIT)
        self.child = self.account('1001', 'Anak Aktiva', parent=self.parent)
        BankAccount.objects.create(
            tenant=self.tenant,
            no_rekening='001',
            nama_bank='Kas',
            atas_nama='CV Test',
            akun=self.cash,
        )
        self.user = get_user_model().objects.create_user(username='admin', password='secret')
        UserProfile.objects.create(user=self.user, tenant=self.tenant, role=UserProfile.Role.ADMIN)

    def account(self, kode, nama, saldo_normal=ChartOfAccount.NormalBalance.DEBET, parent=None):
        return ChartOfAccount.objects.create(
            tenant=self.tenant,
            kode=kode,
            nama=nama,
            saldo_normal=saldo_normal,
            parent=parent,
        )

    def test_journal_adjustment_account_choices_only_leaf_non_cash_accounts(self):
        form = JournalLineForm(tenant=self.tenant)

        self.assertQuerySetEqual(
            form.fields['perkiraan'].queryset.order_by('kode'),
            [self.child, self.revenue, self.expense],
            transform=lambda account: account,
        )

    def test_journal_adjustment_rejects_cash_account_and_invalid_debet_kredit_row(self):
        form = JournalLineForm(
            data={'perkiraan': self.cash.pk, 'debet': Decimal('100'), 'kredit': ''},
            tenant=self.tenant,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('Masukkan pilihan yang valid', str(form.errors))

        form = JournalLineForm(
            data={'perkiraan': self.expense.pk, 'debet': Decimal('100'), 'kredit': Decimal('100')},
            tenant=self.tenant,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('Satu baris hanya boleh berisi debet atau kredit.', str(form.errors))

    def test_journal_adjustment_account_lookup_uses_same_valid_account_filter(self):
        self.client.login(username='admin', password='secret')

        response = self.client.get('/accounting/jurnal/account-lookup/', {'q': 'a'})

        self.assertEqual(response.status_code, 200)
        labels = [row['label'] for row in response.json()['results']]
        self.assertIn('1001 - Anak Aktiva', labels)
        self.assertIn('601 - Biaya Operasional', labels)
        self.assertNotIn('100 - Aktiva', labels)
        self.assertNotIn('101 - Kas', labels)

    def test_journal_list_uses_detail_before_edit(self):
        self.client.login(username='admin', password='secret')
        journal = Journal.objects.create(
            tenant=self.tenant,
            no_jurnal='JUR-1',
            tanggal=date(2026, 8, 1),
            transaksi='jurnal_memorial',
            keterangan='Penyesuaian',
        )

        response = self.client.get('/accounting/jurnal/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'/accounting/jurnal/{journal.uuid}/')
        self.assertNotContains(response, f'/accounting/jurnal/{journal.uuid}/edit/')

    def test_journal_detail_page_has_edit_button(self):
        self.client.login(username='admin', password='secret')
        journal = Journal.objects.create(
            tenant=self.tenant,
            no_jurnal='JUR-1',
            tanggal=date(2026, 8, 1),
            transaksi='jurnal_memorial',
            keterangan='Penyesuaian',
        )
        JournalLine.objects.create(tenant=self.tenant, journal=journal, perkiraan=self.expense, debet=Decimal('100'), kredit=0)

        response = self.client.get(f'/accounting/jurnal/{journal.uuid}/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Detail Jurnal Penyesuaian JUR-1')
        self.assertContains(response, f'/accounting/jurnal/{journal.uuid}/edit/')

    def test_journal_edit_loads_date_and_no_empty_extra_detail_rows(self):
        self.client.login(username='admin', password='secret')
        journal = Journal.objects.create(
            tenant=self.tenant,
            no_jurnal='JUR-1',
            tanggal=date(2026, 8, 1),
            transaksi='jurnal_memorial',
            keterangan='Penyesuaian',
        )
        JournalLine.objects.create(tenant=self.tenant, journal=journal, perkiraan=self.expense, debet=Decimal('100'), kredit=0)
        JournalLine.objects.create(tenant=self.tenant, journal=journal, perkiraan=self.revenue, debet=0, kredit=Decimal('100'))

        response = self.client.get(f'/accounting/jurnal/{journal.uuid}/edit/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="2026-08-01"')
        self.assertContains(response, 'name="lines-TOTAL_FORMS" value="2"')

    def test_closing_list_uses_year_default_and_no_edit_link(self):
        self.client.login(username='admin', password='secret')
        closing = ClosingPeriod.objects.create(tenant=self.tenant, tanggal=date(2026, 8, 31), keterangan='Agustus')
        today = timezone.localdate()

        response = self.client.get('/accounting/closing/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'value="{today.replace(month=1, day=1).isoformat()}"')
        self.assertContains(response, f'value="{today.replace(month=12, day=31).isoformat()}"')
        self.assertContains(response, f'/accounting/closing/{closing.uuid}/')
        self.assertNotContains(response, f'/accounting/closing/{closing.uuid}/edit/')

    def test_closing_edit_route_removed(self):
        self.client.login(username='admin', password='secret')
        closing = ClosingPeriod.objects.create(tenant=self.tenant, tanggal=date(2026, 8, 31), keterangan='Agustus')

        response = self.client.get(f'/accounting/closing/{closing.uuid}/edit/')

        self.assertEqual(response.status_code, 404)

    def test_first_closing_default_uses_oldest_transaction_month_end(self):
        self.client.login(username='admin', password='secret')
        Journal.objects.create(
            tenant=self.tenant,
            no_jurnal='JUR-OLD',
            tanggal=date(2026, 3, 10),
            transaksi='jurnal_memorial',
            keterangan='Transaksi tertua',
        )

        response = self.client.get('/accounting/closing/new/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="2026-03-31"')

    def test_next_closing_default_uses_next_month_end(self):
        self.client.login(username='admin', password='secret')
        ClosingPeriod.objects.create(tenant=self.tenant, tanggal=date(2026, 3, 31), keterangan='Maret')

        response = self.client.get('/accounting/closing/new/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="2026-04-30"')

    def test_first_closing_must_match_oldest_transaction_month_end(self):
        self.client.login(username='admin', password='secret')
        Journal.objects.create(
            tenant=self.tenant,
            no_jurnal='JUR-OLD',
            tanggal=date(2026, 3, 10),
            transaksi='jurnal_memorial',
            keterangan='Transaksi tertua',
        )

        response = self.client.post('/accounting/closing/new/', {'tanggal': '2026-04-30', 'keterangan': 'April'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tanggal closing berikutnya harus 31/03/2026.')

    def test_first_closing_can_be_saved_on_oldest_transaction_month_end(self):
        self.client.login(username='admin', password='secret')
        Journal.objects.create(
            tenant=self.tenant,
            no_jurnal='JUR-OLD',
            tanggal=date(2026, 3, 10),
            transaksi='jurnal_memorial',
            keterangan='Transaksi tertua',
        )

        response = self.client.post('/accounting/closing/new/', {'tanggal': '2026-03-31', 'keterangan': 'Maret'})

        self.assertEqual(response.status_code, 302)
        self.assertTrue(ClosingPeriod.objects.filter(tenant=self.tenant, tanggal=date(2026, 3, 31)).exists())

    def test_closing_detail_formats_money_without_zero_decimal(self):
        self.client.login(username='admin', password='secret')
        closing = ClosingPeriod.objects.create(tenant=self.tenant, tanggal=date(2026, 8, 31), keterangan='Agustus')
        bank = BankAccount.objects.create(
            tenant=self.tenant,
            no_rekening='002',
            nama_bank='Bank',
            atas_nama='CV Test',
            akun=self.cash,
        )
        closing.bank_balances.create(tenant=self.tenant, bank=bank, tanggal=closing.tanggal, saldo_akhir=Decimal('1250000.00'))
        closing.account_balances.create(
            tenant=self.tenant,
            perkiraan=self.expense,
            saldo_normal=ChartOfAccount.NormalBalance.DEBET,
            tanggal=closing.tanggal,
            debet=Decimal('1250000.50'),
            kredit=Decimal('0.00'),
        )

        response = self.client.get(f'/accounting/closing/{closing.uuid}/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '1.250.000')
        self.assertContains(response, '1.250.000,50')
        self.assertContains(response, '>0<')
        self.assertNotContains(response, '1.250.000,00')
