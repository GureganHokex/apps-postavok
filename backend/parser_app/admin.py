"""
Админ-панель для моделей приложения.
"""

from django.contrib import admin
from .models import File, ParsedItem, FileMetadata, Order


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    """Админка для модели File."""
    list_display = ('id', 'original_filename', 'file_type', 'uploaded_at')
    list_filter = ('file_type', 'uploaded_at')
    search_fields = ('original_filename',)


@admin.register(ParsedItem)
class ParsedItemAdmin(admin.ModelAdmin):
    """Админка для модели ParsedItem."""
    list_display = ('id', 'file', 'brewery', 'beer_name', 'price', 'currency')
    list_filter = ('file', 'format_type', 'currency')
    search_fields = ('brewery', 'beer_name', 'supplier_name')


@admin.register(FileMetadata)
class FileMetadataAdmin(admin.ModelAdmin):
    """Админка для модели FileMetadata."""
    list_display = ('id', 'file', 'created_at')
    search_fields = ('file__original_filename',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Админка для модели Order."""
    list_display = ('id', 'created_at', 'export_format')
    list_filter = ('created_at', 'export_format')

