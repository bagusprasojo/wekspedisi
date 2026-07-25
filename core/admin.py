from django.contrib import admin

from .models import DocumentSequence


@admin.register(DocumentSequence)
class DocumentSequenceAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'document_type', 'period', 'last_number', 'updated_at')
    list_filter = ('document_type', 'period')
    search_fields = ('tenant__name', 'document_type', 'period')
