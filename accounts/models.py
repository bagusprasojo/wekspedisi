from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class UserProfile(TimeStampedModel):
    class Role(models.TextChoices):
        OWNER = 'owner', 'Owner'
        ADMIN = 'admin', 'Admin'
        FINANCE = 'finance', 'Finance'
        OPERATIONAL = 'operasional', 'Operasional'
        VIEWER = 'viewer', 'Viewer'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name='profile', on_delete=models.CASCADE)
    tenant = models.ForeignKey('tenants.Tenant', related_name='user_profiles', on_delete=models.PROTECT)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.VIEWER)

    class Meta:
        ordering = ['user__username']

    def __str__(self):
        return f'{self.user} - {self.tenant}'
