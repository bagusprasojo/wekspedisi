from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'tenant', 'actor', 'action', 'model_name', 'object_id')
    list_filter = ('action', 'app_label', 'model_name', 'tenant')
    search_fields = ('object_repr', 'object_id', 'actor__username')
    readonly_fields = [field.name for field in AuditLog._meta.fields]
