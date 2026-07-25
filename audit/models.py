from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class AuditLog(TimeStampedModel):
    class Action(models.TextChoices):
        CREATE = 'create', 'Create'
        UPDATE = 'update', 'Update'
        DELETE = 'delete', 'Delete'
        RESTORE = 'restore', 'Restore'
        LOGIN = 'login', 'Login'
        LOGOUT = 'logout', 'Logout'
        CLOSE_PERIOD = 'close_period', 'Close Period'
        GENERATE_JOURNAL = 'generate_journal', 'Generate Journal'

    tenant = models.ForeignKey('tenants.Tenant', null=True, blank=True, on_delete=models.SET_NULL)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=30, choices=Action.choices)
    app_label = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=64)
    object_repr = models.CharField(max_length=255, blank=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    changes = models.JSONField(null=True, blank=True)
    request_path = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['app_label', 'model_name', 'object_id']),
        ]

    def __str__(self):
        return f'{self.action} {self.model_name}#{self.object_id}'
