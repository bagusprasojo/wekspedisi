from datetime import date, datetime
from decimal import Decimal

from django.forms.models import model_to_dict
from django.utils import timezone

from audit.models import AuditLog


SYSTEM_FIELDS = {'created_at', 'updated_at'}


def serialize_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if hasattr(value, 'pk'):
        return value.pk
    return value


def snapshot(instance):
    if not instance or not instance.pk:
        return None
    data = model_to_dict(instance)
    return {key: serialize_value(value) for key, value in data.items()}


def diff(before, after):
    before = before or {}
    after = after or {}
    changes = {}
    for key in sorted(set(before) | set(after)):
        if key in SYSTEM_FIELDS:
            continue
        if before.get(key) != after.get(key):
            changes[key] = {'before': before.get(key), 'after': after.get(key)}
    return changes


def write_audit(*, actor, tenant, action, instance, before=None, after=None):
    AuditLog.objects.create(
        tenant=tenant,
        actor=actor,
        action=action,
        app_label=instance._meta.app_label,
        model_name=instance._meta.model_name,
        object_id=str(instance.pk),
        object_repr=str(instance),
        before=before,
        after=after,
        changes=diff(before, after),
    )
