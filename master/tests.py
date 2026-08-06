from django.test import TestCase
from django.contrib.auth import get_user_model

from accounts.models import UserProfile
from master.forms import ArmadaForm, CustomerForm, KaryawanForm
from master.models import Armada, BankAccount, ChartOfAccount, StakeHolder
from master.urls import CONFIGS
from tenants.models import Tenant

class StakeHolderLegacyShapeTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='CV Test')

    def test_stakeholder_auto_code_uses_customer_or_karyawan_prefix(self):
        customer = StakeHolder.objects.create(
            tenant=self.tenant,
            nama='Customer A',
            jenis=StakeHolder.StakeHolderType.CUSTOMER,
        )
        karyawan = StakeHolder.objects.create(
            tenant=self.tenant,
            nama='Karyawan A',
            jenis=StakeHolder.StakeHolderType.KARYAWAN,
        )

        self.assertTrue(customer.kode.startswith('CUS-'))
        self.assertTrue(karyawan.kode.startswith('KAR-'))
        self.assertEqual(str(customer), 'Customer A')
        self.assertEqual(str(karyawan), 'Karyawan A')
        self.assertNotIn('kode', CustomerForm().fields)
        self.assertNotIn('kode', KaryawanForm().fields)

    def test_armada_driver_choices_use_karyawan_not_driver_type(self):
        karyawan = StakeHolder.objects.create(
            tenant=self.tenant,
            kode='K001',
            nama='Driver Karyawan',
            jenis=StakeHolder.StakeHolderType.KARYAWAN,
        )
        customer = StakeHolder.objects.create(
            tenant=self.tenant,
            kode='C001',
            nama='Customer A',
            jenis=StakeHolder.StakeHolderType.CUSTOMER,
        )
        armada = Armada(tenant=self.tenant)

        form = ArmadaForm(instance=armada)

        self.assertIn(karyawan, form.fields['driver'].queryset)
        self.assertNotIn(customer, form.fields['driver'].queryset)

class BankAccountDetailUxTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='CV Test')
        self.user = get_user_model().objects.create_user(username='admin')
        UserProfile.objects.create(user=self.user, tenant=self.tenant, role=UserProfile.Role.ADMIN)
        akun = ChartOfAccount.objects.create(tenant=self.tenant, kode='101', nama='Bank', saldo_normal=ChartOfAccount.NormalBalance.DEBET)
        self.bank = BankAccount.objects.create(tenant=self.tenant, nama_bank='Bank A', no_rekening='001', atas_nama='CV Test', akun=akun)

    def test_bank_list_uses_detail_before_edit(self):
        config = CONFIGS['bank']

        self.assertEqual(config.detail_url_name, 'master_bank_detail')
        self.assertTrue(config.hide_list_edit)

    def test_bank_detail_page_has_edit_button(self):
        self.client.force_login(self.user)
        response = self.client.get(f'/master/bank/{self.bank.uuid}/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Detail Bank/Kas Bank A')
        self.assertContains(response, f'/master/bank/{self.bank.uuid}/edit/')

class CustomerDetailUxTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='CV Test')
        self.user = get_user_model().objects.create_user(username='admin-customer')
        UserProfile.objects.create(user=self.user, tenant=self.tenant, role=UserProfile.Role.ADMIN)
        self.customer = StakeHolder.objects.create(
            tenant=self.tenant,
            nama='Customer A',
            alamat='Jl Customer',
            kota='Sukoharjo',
            jenis=StakeHolder.StakeHolderType.CUSTOMER,
        )

    def test_customer_list_uses_detail_before_edit(self):
        config = CONFIGS['customer']

        self.assertEqual(config.detail_url_name, 'master_customer_detail')
        self.assertTrue(config.hide_list_edit)

    def test_customer_detail_page_has_edit_button(self):
        self.client.force_login(self.user)
        response = self.client.get(f'/master/customer/{self.customer.uuid}/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Detail Customer Customer A')
        self.assertContains(response, f'/master/customer/{self.customer.uuid}/edit/')

class KaryawanDetailUxTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='CV Test')
        self.user = get_user_model().objects.create_user(username='admin-karyawan')
        UserProfile.objects.create(user=self.user, tenant=self.tenant, role=UserProfile.Role.ADMIN)
        self.karyawan = StakeHolder.objects.create(
            tenant=self.tenant,
            nama='Karyawan A',
            alamat='Jl Karyawan',
            kota='Sukoharjo',
            lokasi_kerja='Kantor',
            jenis=StakeHolder.StakeHolderType.KARYAWAN,
        )

    def test_karyawan_list_uses_detail_before_edit(self):
        config = CONFIGS['karyawan']

        self.assertEqual(config.detail_url_name, 'master_karyawan_detail')
        self.assertTrue(config.hide_list_edit)

    def test_karyawan_detail_page_has_edit_button(self):
        self.client.force_login(self.user)
        response = self.client.get(f'/master/karyawan/{self.karyawan.uuid}/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Detail Karyawan Karyawan A')
        self.assertContains(response, f'/master/karyawan/{self.karyawan.uuid}/edit/')

class ArmadaDetailUxTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='CV Test')
        self.user = get_user_model().objects.create_user(username='admin-armada')
        UserProfile.objects.create(user=self.user, tenant=self.tenant, role=UserProfile.Role.ADMIN)
        self.driver = StakeHolder.objects.create(
            tenant=self.tenant,
            nama='Driver A',
            jenis=StakeHolder.StakeHolderType.KARYAWAN,
        )
        self.armada = Armada.objects.create(
            tenant=self.tenant,
            nopol='AD 1234 AB',
            kendaraan='Truk Box',
            pemilik='CV Test',
            driver=self.driver,
        )

    def test_armada_list_uses_detail_before_edit(self):
        config = CONFIGS['armada']

        self.assertEqual(config.detail_url_name, 'master_armada_detail')
        self.assertTrue(config.hide_list_edit)

    def test_armada_detail_page_has_edit_button(self):
        self.client.force_login(self.user)
        response = self.client.get(f'/master/armada/{self.armada.uuid}/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Detail Armada AD 1234 AB')
        self.assertContains(response, f'/master/armada/{self.armada.uuid}/edit/')

class AccountDetailUxTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='CV Test')
        self.user = get_user_model().objects.create_user(username='admin-akun')
        UserProfile.objects.create(user=self.user, tenant=self.tenant, role=UserProfile.Role.ADMIN)
        self.account = ChartOfAccount.objects.create(
            tenant=self.tenant,
            kode='501',
            nama='Biaya Operasional',
            golongan='Biaya',
            kelompok='Operasional',
            saldo_normal=ChartOfAccount.NormalBalance.DEBET,
        )

    def test_account_list_uses_detail_before_edit(self):
        config = CONFIGS['akun']

        self.assertEqual(config.detail_url_name, 'master_akun_detail')
        self.assertTrue(config.hide_list_edit)

    def test_account_detail_page_has_edit_button(self):
        self.client.force_login(self.user)
        response = self.client.get(f'/master/akun/{self.account.uuid}/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Detail Perkiraan/Akun 501')
        self.assertContains(response, f'/master/akun/{self.account.uuid}/edit/')
