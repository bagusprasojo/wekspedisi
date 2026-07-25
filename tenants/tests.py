from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from tenants.models import validate_square_logo


def png_header(width, height):
    return b'\x89PNG\r\n\x1a\n' + b'\x00\x00\x00\rIHDR' + width.to_bytes(4, 'big') + height.to_bytes(4, 'big') + b'\x08\x02\x00\x00\x00' + b'\x00\x00\x00\x00'


class TenantLogoValidationTests(TestCase):
    def test_logo_must_be_square_png_or_jpeg(self):
        validate_square_logo(SimpleUploadedFile('logo.png', png_header(512, 512), content_type='image/png'))

        with self.assertRaisesMessage(ValidationError, 'Logo harus square'):
            validate_square_logo(SimpleUploadedFile('logo.png', png_header(512, 256), content_type='image/png'))

        with self.assertRaisesMessage(ValidationError, 'Logo harus berupa file PNG atau JPEG yang valid.'):
            validate_square_logo(SimpleUploadedFile('logo.png', b'not image', content_type='image/png'))
