import uuid
from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantScopedModel(TimeStampedModel):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.PROTECT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name='created_%(class)s_set',
        on_delete=models.SET_NULL,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name='updated_%(class)s_set',
        on_delete=models.SET_NULL,
    )
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name='deleted_%(class)s_set',
        on_delete=models.SET_NULL,
    )

    class Meta:
        abstract = True


class DocumentSequence(TimeStampedModel):
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE)
    document_type = models.CharField(max_length=20)
    period = models.CharField(max_length=12)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'document_type', 'period'],
                name='uniq_document_sequence_tenant_type_period',
            )
        ]

    def __str__(self):
        return f'{self.tenant} {self.document_type}-{self.period}: {self.last_number}'
