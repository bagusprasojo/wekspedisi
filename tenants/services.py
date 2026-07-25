from django.contrib.auth import get_user_model
from django.db import transaction

from accounts.models import UserProfile
from audit.models import AuditLog
from tenants.models import Tenant


@transaction.atomic
def admit_tenant(*, actor, tenant_data, admin_data):
    tenant = Tenant.objects.create(**tenant_data)
    user = _create_user(admin_data)
    UserProfile.objects.create(user=user, tenant=tenant, role=admin_data['role'])
    _audit(actor=actor, tenant=tenant, action=AuditLog.Action.CREATE, obj=tenant)
    _audit(actor=actor, tenant=tenant, action=AuditLog.Action.CREATE, obj=user, object_repr=f'User tenant {user.username}')
    return tenant, user


@transaction.atomic
def create_tenant_user(*, actor, tenant, user_data):
    user = _create_user(user_data)
    user.is_staff = user_data.get('is_staff', False)
    user.save(update_fields=['is_staff'])
    UserProfile.objects.create(user=user, tenant=tenant, role=user_data['role'])
    _audit(actor=actor, tenant=tenant, action=AuditLog.Action.CREATE, obj=user, object_repr=f'User tenant {user.username}')
    return user


def _create_user(data):
    User = get_user_model()
    user = User.objects.create_user(
        username=data['username'],
        email=data.get('email', ''),
        password=data['password'],
        first_name=data.get('first_name', ''),
        last_name=data.get('last_name', ''),
    )
    return user


def _audit(*, actor, tenant, action, obj, object_repr=None):
    AuditLog.objects.create(
        tenant=tenant,
        actor=actor,
        action=action,
        app_label=obj._meta.app_label,
        model_name=obj._meta.model_name,
        object_id=str(obj.pk),
        object_repr=object_repr or str(obj),
        after={'id': obj.pk, 'repr': object_repr or str(obj)},
    )
