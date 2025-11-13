"""
Модели данных для приложения парсинга прайсов.
"""

from django.db import models
from django.core.validators import MinValueValidator
import json


class File(models.Model):
    """
    Модель для хранения информации о загруженных файлах.

    Хранит метаданные файла: имя, тип, путь к файлу,
    опциональную ссылку на Google Sheets.
    """
    FILE_TYPE_CHOICES = [
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('google_sheets', 'Google Sheets'),
        ('zip', 'ZIP Archive'),
    ]

    original_filename = models.CharField(
        max_length=255,
        verbose_name='Исходное имя файла'
    )
    file_type = models.CharField(
        max_length=20,
        choices=FILE_TYPE_CHOICES,
        verbose_name='Тип файла'
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата загрузки'
    )
    file_path = models.CharField(
        max_length=500,
        verbose_name='Путь к файлу'
    )
    google_sheet_url = models.URLField(
        blank=True,
        null=True,
        verbose_name='Ссылка на Google Sheets'
    )

    class Meta:
        verbose_name = 'Файл'
        verbose_name_plural = 'Файлы'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.original_filename} ({self.file_type})"


class ParsedItem(models.Model):
    """
    Модель для хранения распарсенных позиций пива.
    
    Содержит все основные поля товара: пивоварня, название,
    стиль, крепость, цена, объём, формат и т.д.
    """
    file = models.ForeignKey(
        File,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Файл'
    )
    brewery = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Пивоварня'
    )
    beer_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Название пива'
    )
    style = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Стиль пива'
    )
    abv = models.FloatField(
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
        verbose_name='Крепость (%)'
    )
    ibu = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Горечь (IBU)'
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='Цена'
    )
    currency = models.CharField(
        max_length=10,
        default='RUB',
        verbose_name='Валюта'
    )
    volume = models.FloatField(
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
        verbose_name='Объём (л)'
    )
    format_type = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Формат'
    )
    stock = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Остатки'
    )
    supplier_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Поставщик'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание пива'
    )
    raw_source_location = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Источник данных'
    )
    is_selected = models.BooleanField(
        default=False,
        verbose_name='Выбрано для заказа'
    )

    class Meta:
        verbose_name = 'Распарсенная позиция'
        verbose_name_plural = 'Распарсенные позиции'
        ordering = ['file', 'brewery', 'beer_name']

    def __str__(self):
        return f"{self.brewery} - {self.beer_name}"


class FileMetadata(models.Model):
    """
    Модель для хранения метаданных файла.

    Содержит контакты, служебные тексты и статистику парсинга.
    Все данные хранятся в JSON формате для гибкости.
    """
    file = models.OneToOneField(
        File,
        on_delete=models.CASCADE,
        related_name='metadata',
        verbose_name='Файл'
    )
    contacts = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Контакты'
    )
    extra_text = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Служебные тексты'
    )
    summary = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Статистика парсинга'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    class Meta:
        verbose_name = 'Метаданные файла'
        verbose_name_plural = 'Метаданные файлов'

    def __str__(self):
        return f"Метаданные для {self.file.original_filename}"
    
    def get_phones(self):
        """Возвращает список телефонов из contacts."""
        return self.contacts.get('phones', [])
    
    def get_emails(self):
        """Возвращает список email из contacts."""
        return self.contacts.get('emails', [])
    
    def get_addresses(self):
        """Возвращает список адресов из contacts."""
        return self.contacts.get('addresses', [])
    
    def get_links(self):
        """Возвращает список ссылок из contacts."""
        return self.contacts.get('links', [])


class Order(models.Model):
    """
    Модель для хранения сформированных заказов.

    Содержит список позиций с количествами и формат экспорта.
    """
    EXPORT_FORMAT_CHOICES = [
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
    ]

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    items = models.JSONField(
        default=list,
        verbose_name='Позиции заказа'
    )
    export_format = models.CharField(
        max_length=10,
        choices=EXPORT_FORMAT_CHOICES,
        default='excel',
        verbose_name='Формат экспорта'
    )
    export_file_path = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name='Путь к экспортированному файлу'
    )

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-created_at']

    def __str__(self):
        return f"Заказ #{self.id} от {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    def get_items_count(self):
        """Возвращает общее количество позиций в заказе."""
        return len(self.items)
