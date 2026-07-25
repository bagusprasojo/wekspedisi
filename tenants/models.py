from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models

from core.models import TimeStampedModel


def logo_dimensions(file_obj):
    current_pos = file_obj.tell()
    file_obj.seek(0)
    header = file_obj.read(32)
    width = height = None
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        width = int.from_bytes(header[16:20], 'big')
        height = int.from_bytes(header[20:24], 'big')
    elif header.startswith(b'\xff\xd8'):
        file_obj.seek(2)
        while True:
            marker_prefix = file_obj.read(1)
            if not marker_prefix:
                break
            if marker_prefix != b'\xff':
                continue
            marker = file_obj.read(1)
            while marker == b'\xff':
                marker = file_obj.read(1)
            if marker in (b'\xc0', b'\xc1', b'\xc2'):
                file_obj.read(3)
                height = int.from_bytes(file_obj.read(2), 'big')
                width = int.from_bytes(file_obj.read(2), 'big')
                break
            length = int.from_bytes(file_obj.read(2), 'big')
            file_obj.seek(length - 2, 1)
    file_obj.seek(current_pos)
    return width, height


def validate_square_logo(file_obj):
    width, height = logo_dimensions(file_obj)
    if not width or not height:
        raise ValidationError('Logo harus berupa file PNG atau JPEG yang valid.')
    if width != height:
        raise ValidationError('Logo harus square: lebar dan tinggi harus sama.')


class Tenant(TimeStampedModel):
    name = models.CharField(max_length=150)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    logo = models.FileField(
        upload_to='tenant_logos/',
        blank=True,
        validators=[FileExtensionValidator(['png', 'jpg', 'jpeg']), validate_square_logo],
        help_text='Gunakan logo square PNG/JPEG. Rekomendasi 512 x 512 px atau 1024 x 1024 px.',
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
