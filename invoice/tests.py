from datetime import date
from decimal import Decimal
from unittest import SkipTest

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import UserProfile
from accounting.models import Journal
from accounting.services import generated_transaction_key
from invoice.models import CustomerInvoice, CustomerInvoicePayment
from master.models import BankAccount, ChartOfAccount, StakeHolder, TenantConfig
from tenants.models import Tenant

def require_weasyprint():
    try:
        from core.exporters import _weasy_response

        _weasy_response('test.pdf', '<p>x</p>')
    except Exception as exc:
        raise SkipTest(f'WeasyPrint native dependency belum tersedia: {exc}') from exc


class CustomerInvoiceLegacyRuleTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='CV Test')
        self.user = get_user_model().objects.create_user(username='admin')
        self.piutang = self.account('103', 'Piutang Jasa')
        self.pendapatan = self.account('401', 'Pendapatan Jasa', ChartOfAccount.NormalBalance.KREDIT)
        self.ppn = self.account('205', 'PPN Keluaran', ChartOfAccount.NormalBalance.KREDIT)
        self.bank_account = self.account('101', 'Bank')
        self.pph_account = self.account('107', 'PPH')
        TenantConfig.objects.create(tenant=self.tenant, kode='PIUTANG_JASA_ID', nilai=str(self.piutang.pk))
        TenantConfig.objects.create(tenant=self.tenant, kode='AKUN_PENDAPATAN_JASA', nilai=str(self.pendapatan.pk))
        TenantConfig.objects.create(tenant=self.tenant, kode='AKUN_PPN_ID', nilai=str(self.ppn.pk))
        TenantConfig.objects.create(tenant=self.tenant, kode='AKUN_PPH_ID', nilai=str(self.pph_account.pk))
        TenantConfig.objects.create(tenant=self.tenant, kode='INVOICE_CODE', nilai='INV_TBL')
        TenantConfig.objects.create(tenant=self.tenant, kode='INVOICE_ADMIN_NAME', nilai='Admin Tenant')
        TenantConfig.objects.create(tenant=self.tenant, kode='INVOICE_PAYMENT_TEXT', nilai='Transfer Bank Test\nCV Test')
        self.bank = BankAccount.objects.create(
            tenant=self.tenant,
            no_rekening='001',
            nama_bank='Bank A',
            atas_nama='CV Test',
            akun=self.bank_account,
        )
        self.customer = StakeHolder.objects.create(
            tenant=self.tenant,
            kode='C001',
            nama='Customer A',
            jenis=StakeHolder.StakeHolderType.CUSTOMER,
        )

    def account(self, kode, nama, saldo_normal=ChartOfAccount.NormalBalance.DEBET):
        return ChartOfAccount.objects.create(
            tenant=self.tenant,
            kode=kode,
            nama=nama,
            saldo_normal=saldo_normal,
        )

    def test_invoice_uses_configured_receivable_and_automatic_ppn_like_desktop(self):
        invoice = CustomerInvoice(
            tenant=self.tenant,
            customer=self.customer,
            tanggal=date(2026, 7, 24),
            pekerjaan='Ongkos kirim',
            nilai_pekerjaan=Decimal('1000000'),
        )

        invoice.save_with_business_rules(user=self.user)

        invoice.refresh_from_db()
        self.assertEqual(invoice.perkiraan_piutang, self.piutang)
        self.assertEqual(invoice.ppn_persen, Decimal('12.00'))
        self.assertEqual(invoice.ppn, Decimal('110000.00'))
        self.assertEqual(invoice.total, Decimal('1110000.00'))
        self.assertEqual(invoice.terbilang, 'Satu Juta Seratus Sepuluh Ribu Rupiah')
        self.assertEqual(invoice.saldo, Decimal('1110000.00'))
        journal = Journal.objects.get(tenant=self.tenant, transaksi_id=invoice.pk, transaksi=generated_transaction_key(invoice))
        lines = list(journal.lines.order_by('id').values_list('perkiraan_id', 'debet', 'kredit'))
        self.assertEqual(lines, [
            (self.piutang.pk, Decimal('1110000.00'), Decimal('0.00')),
            (self.pendapatan.pk, Decimal('0.00'), Decimal('1000000.00')),
            (self.ppn.pk, Decimal('0.00'), Decimal('110000.00')),
        ])

    def test_invoice_requires_customer_job_and_positive_amount(self):
        invoice = CustomerInvoice(
            tenant=self.tenant,
            customer=self.customer,
            tanggal=date(2026, 7, 24),
            pekerjaan='',
            nilai_pekerjaan=Decimal('1000000'),
        )
        with self.assertRaisesMessage(ValidationError, 'Nama pekerjaan belum diisi.'):
            invoice.save_with_business_rules(user=self.user)

        invoice.pekerjaan = 'Ongkos kirim'
        invoice.nilai_pekerjaan = Decimal('0')
        with self.assertRaisesMessage(ValidationError, 'Nilai pekerjaan belum diisi.'):
            invoice.save_with_business_rules(user=self.user)

    def test_invoice_payment_uses_bank_account_ppn_bayar_and_updates_invoice_like_desktop(self):
        invoice = CustomerInvoice(
            tenant=self.tenant,
            customer=self.customer,
            tanggal=date(2026, 7, 24),
            pekerjaan='Ongkos kirim',
            nilai_pekerjaan=Decimal('1000000'),
        ).save_with_business_rules(user=self.user)
        payment = CustomerInvoicePayment(
            tenant=self.tenant,
            tagihan_customer=invoice,
            tanggal=date(2026, 7, 25),
            bank=self.bank,
            nominal_kas=Decimal('1000000'),
            pph_persen=Decimal('2'),
            pph=Decimal('20000'),
            keterangan='Pembayaran invoice',
        )

        payment.save_with_business_rules(user=self.user)

        payment.refresh_from_db()
        invoice.refresh_from_db()
        self.assertEqual(payment.perkiraan_kas, self.bank_account)
        self.assertEqual(payment.sumber_dana, str(self.bank))
        self.assertEqual(payment.pph, Decimal('20000.00'))
        self.assertEqual(payment.ppn, Decimal('101081.00'))
        self.assertEqual(payment.terbilang, 'Satu Juta Rupiah')
        self.assertEqual(invoice.pelunasan, Decimal('1020000.00'))
        self.assertEqual(invoice.status_lunas, CustomerInvoice.StatusLunas.BELUM)
        journal = Journal.objects.get(tenant=self.tenant, transaksi_id=payment.pk, transaksi=generated_transaction_key(payment))
        lines = list(journal.lines.order_by('id').values_list('perkiraan_id', 'debet', 'kredit'))
        self.assertEqual(lines, [
            (self.bank_account.pk, Decimal('1000000.00'), Decimal('0.00')),
            (self.pph_account.pk, Decimal('20000.00'), Decimal('0.00')),
            (self.piutang.pk, Decimal('0.00'), Decimal('1020000.00')),
        ])

    def test_invoice_payment_rejects_overpayment(self):
        invoice = CustomerInvoice(
            tenant=self.tenant,
            customer=self.customer,
            tanggal=date(2026, 7, 24),
            pekerjaan='Ongkos kirim',
            nilai_pekerjaan=Decimal('1000000'),
        ).save_with_business_rules(user=self.user)
        payment = CustomerInvoicePayment(
            tenant=self.tenant,
            tagihan_customer=invoice,
            tanggal=date(2026, 7, 25),
            bank=self.bank,
            nominal_kas=Decimal('1200000'),
        )

        with self.assertRaisesMessage(ValidationError, 'Pembayaran melebihi saldo piutang.'):
            payment.save_with_business_rules(user=self.user)

    def test_invoice_and_receipt_endpoints_return_html(self):
        UserProfile.objects.create(user=self.user, tenant=self.tenant, role=UserProfile.Role.ADMIN)
        invoice = CustomerInvoice(
            tenant=self.tenant,
            customer=self.customer,
            tanggal=date(2026, 7, 24),
            pekerjaan='Ongkos kirim',
            nilai_pekerjaan=Decimal('1000000'),
        ).save_with_business_rules(user=self.user)

        self.client.force_login(self.user)
        invoice_response = self.client.get(f'/invoice/invoice-customer/{invoice.uuid}/slip/')
        receipt_response = self.client.get(f'/invoice/invoice-customer/{invoice.uuid}/kwitansi/')

        self.assertEqual(invoice_response.status_code, 200)
        self.assertIn('text/html', invoice_response['Content-Type'])
        self.assertIn(b'window.print()', invoice_response.content)
        self.assertEqual(receipt_response.status_code, 200)
        self.assertIn('text/html', receipt_response['Content-Type'])
        self.assertIn(b'window.print()', receipt_response.content)

    def test_invoice_number_resets_yearly_and_uses_tenant_config_code(self):
        TenantConfig.objects.filter(tenant=self.tenant, kode='INVOICE_CODE').update(nilai='INV_CUSTOM')
        first = CustomerInvoice(
            tenant=self.tenant,
            customer=self.customer,
            tanggal=date(2026, 7, 1),
            pekerjaan='Ongkos kirim',
            nilai_pekerjaan=Decimal('1000000'),
        ).save_with_business_rules(user=self.user)
        second = CustomerInvoice(
            tenant=self.tenant,
            customer=self.customer,
            tanggal=date(2026, 8, 1),
            pekerjaan='Ongkos kirim',
            nilai_pekerjaan=Decimal('1000000'),
        ).save_with_business_rules(user=self.user)
        third = CustomerInvoice(
            tenant=self.tenant,
            customer=self.customer,
            tanggal=date(2027, 1, 15),
            pekerjaan='Ongkos kirim',
            nilai_pekerjaan=Decimal('1000000'),
        ).save_with_business_rules(user=self.user)

        self.assertEqual(first.no_invoice, '001/VII/INV_CUSTOM/2026')
        self.assertEqual(second.no_invoice, '002/VIII/INV_CUSTOM/2026')
        self.assertEqual(third.no_invoice, '001/I/INV_CUSTOM/2027')

    def test_invoice_save_requires_invoice_tenant_configs(self):
        TenantConfig.objects.filter(tenant=self.tenant, kode='INVOICE_CODE').delete()
        invoice = CustomerInvoice(
            tenant=self.tenant,
            customer=self.customer,
            tanggal=date(2026, 7, 24),
            pekerjaan='Ongkos kirim',
            nilai_pekerjaan=Decimal('1000000'),
        )

        with self.assertRaisesMessage(ValidationError, 'Konfigurasi invoice belum lengkap. Hubungi superadmin untuk melengkapi config tenant: INVOICE_CODE.'):
            invoice.save_with_business_rules(user=self.user)

    def test_invoice_pdf_requires_invoice_tenant_configs(self):
        UserProfile.objects.create(user=self.user, tenant=self.tenant, role=UserProfile.Role.ADMIN)
        invoice = CustomerInvoice(
            tenant=self.tenant,
            customer=self.customer,
            tanggal=date(2026, 7, 24),
            pekerjaan='Ongkos kirim',
            nilai_pekerjaan=Decimal('1000000'),
        ).save_with_business_rules(user=self.user)
        TenantConfig.objects.filter(tenant=self.tenant, kode='INVOICE_PAYMENT_TEXT').delete()

        self.client.force_login(self.user)
        response = self.client.get(f'/invoice/invoice-customer/{invoice.uuid}/slip/')

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'Konfigurasi invoice belum lengkap. Hubungi superadmin untuk melengkapi config tenant: INVOICE_PAYMENT_TEXT.', status_code=400)
