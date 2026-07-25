from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import UserProfile
from accounting.forms import JournalLineForm
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
