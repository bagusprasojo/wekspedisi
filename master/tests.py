from django.test import TestCase

from master.forms import ArmadaForm, CustomerForm, KaryawanForm
from master.models import Armada, StakeHolder
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
