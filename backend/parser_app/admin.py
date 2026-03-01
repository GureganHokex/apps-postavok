"""
Админ-панель для моделей приложения.
"""

from django.contrib import admin
from .models import File, ParsedItem, FileMetadata, Order, Supplier, UserProfile


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


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    """Админка для настроек поставщиков (маппинг колонок)."""
    list_display = ('id', 'name', 'updated_at')
    search_fields = ('name',)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Роли пользователей. Пользователей можно создавать в Django Admin (Users), затем задать роль здесь."""
    list_display = ('user', 'role')
    list_filter = ('role',)
    search_fields = ('user__username',)

