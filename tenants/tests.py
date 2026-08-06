from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import UserProfile
from master.models import ChartOfAccount, TenantConfig, TransactionType
from tenants.models import validate_square_logo
from tenants.models import Tenant


def png_header(width, height):
    return b'\x89PNG\r\n\x1a\n' + b'\x00\x00\x00\rIHDR' + width.to_bytes(4, 'big') + height.to_bytes(4, 'big') + b'\x08\x02\x00\x00\x00' + b'\x00\x00\x00\x00'


class TenantLogoValidationTests(TestCase):
    def test_logo_must_be_square_png_or_jpeg(self):
        validate_square_logo(SimpleUploadedFile('logo.png', png_header(512, 512), content_type='image/png'))

        with self.assertRaisesMessage(ValidationError, 'Logo harus square'):
            validate_square_logo(SimpleUploadedFile('logo.png', png_header(512, 256), content_type='image/png'))

        with self.assertRaisesMessage(ValidationError, 'Logo harus berupa file PNG atau JPEG yang valid.'):
            validate_square_logo(SimpleUploadedFile('logo.png', b'not image', content_type='image/png'))

class PlatformSettingUxTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='CV Test')
        self.other_tenant = Tenant.objects.create(name='CV Lain')
        self.superuser = get_user_model().objects.create_superuser(username='root', password='secret')
        self.user = get_user_model().objects.create_user(username='tenant-user', password='secret')
        UserProfile.objects.create(user=self.user, tenant=self.tenant, role=UserProfile.Role.ADMIN)
        self.account = ChartOfAccount.objects.create(
            tenant=self.tenant,
            kode='501',
            nama='Biaya',
            saldo_normal=ChartOfAccount.NormalBalance.DEBET,
        )
        self.other_account = ChartOfAccount.objects.create(
            tenant=self.other_tenant,
            kode='501',
            nama='Biaya Lain',
            saldo_normal=ChartOfAccount.NormalBalance.DEBET,
        )

    def test_tenant_setting_routes_are_removed(self):
        self.client.force_login(self.user)

        self.assertEqual(self.client.get('/master/config/').status_code, 404)
        self.assertEqual(self.client.get('/master/jenis-transaksi/').status_code, 404)

    def test_platform_settings_require_superadmin(self):
        self.client.force_login(self.user)

        self.assertEqual(self.client.get('/platform/config/').status_code, 302)
        self.assertEqual(self.client.get('/platform/jenis-transaksi/').status_code, 302)

    def test_superadmin_can_create_tenant_config(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            '/platform/config/new/',
            {'tenant': self.tenant.pk, 'kode': 'INVOICE_CODE', 'nilai': 'INV_TBL', 'keterangan': 'Kode invoice'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(TenantConfig.objects.filter(tenant=self.tenant, kode='INVOICE_CODE', nilai='INV_TBL').exists())

    def test_superadmin_transaction_type_account_must_match_selected_tenant(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            '/platform/jenis-transaksi/new/',
            {'tenant': self.tenant.pk, 'kode': '01', 'nama': 'Keluar', 'akun': self.other_account.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Masukkan pilihan yang valid')
        self.assertFalse(TransactionType.objects.filter(tenant=self.tenant, kode='01').exists())

    def test_superadmin_can_create_transaction_type_for_selected_tenant(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            '/platform/jenis-transaksi/new/',
            {'tenant': self.tenant.pk, 'kode': '01', 'nama': 'Keluar', 'akun': self.account.pk},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(TransactionType.objects.filter(tenant=self.tenant, kode='01', akun=self.account).exists())
