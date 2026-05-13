"""
Модели данных для приложения парсинга прайсов.
"""

import json
import logging

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import CharField

logger = logging.getLogger(__name__)


class UserProfile(models.Model):
    """
    Профиль пользователя с ролью для разграничения прав.
    """
    ROLE_ADMIN = 'admin'
    ROLE_BARTENDER = 'bartender'
    ROLE_USER = 'user'
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Администратор'),
        (ROLE_BARTENDER, 'Бармен'),
        (ROLE_USER, 'Пользователь'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name='Пользователь',
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_USER,
        verbose_name='Роль',
    )

    class Meta:
        verbose_name = 'Профиль пользователя'
        verbose_name_plural = 'Профили пользователей'

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


class Supplier(models.Model):
    """
    Настройки поставщика для точного маппинга колонок.
    Отдельная запись на каждого поставщика (Парадокс, CBD и т.д.).
    Ключевые слова задаются вручную — по ним заголовки колонок сопоставляются с полями парсера.
    """
    name = models.CharField(
        max_length=200,
        unique=True,
        verbose_name='Название поставщика'
    )
    # Маппинг: поле парсера -> список ключевых слов (подстрок заголовков колонок)
    # Пример: {"beer_name": ["Имя", "Название товара"], "price": ["Цена за штуку"]}
    column_mapping = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Ключевые слова для колонок'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )

    class Meta:
        verbose_name = 'Поставщик (настройки маппинга)'
        verbose_name_plural = 'Поставщики (настройки маппинга)'
        ordering = ['name']

    def __str__(self):
        return self.name


class SupplierColumnMapping(models.Model):
    """
    Ручные маппинги колонок для feedback-loop (v2 parser).
    """

    SCOPE_EXACT_FILE = 'exact_file'
    SCOPE_SUPPLIER = 'supplier'
    SCOPE_GLOBAL = 'global'
    SCOPE_CHOICES = [
        (SCOPE_EXACT_FILE, 'Точный файл'),
        (SCOPE_SUPPLIER, 'Поставщик'),
        (SCOPE_GLOBAL, 'Глобально'),
    ]

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name='column_mappings',
        null=True,
        blank=True,
        verbose_name='Поставщик',
    )
    scope = models.CharField(
        max_length=20,
        choices=SCOPE_CHOICES,
        default=SCOPE_SUPPLIER,
        verbose_name='Область действия',
    )
    source_column = models.CharField(max_length=255, verbose_name='Исходная колонка')
    target_field = models.CharField(max_length=100, verbose_name='Целевое поле')
    file_pattern = models.CharField(max_length=255, blank=True, verbose_name='Паттерн файла')
    confidence = models.FloatField(default=1.0, validators=[MinValueValidator(0)], verbose_name='Уверенность')
    meta = models.JSONField(default=dict, blank=True, verbose_name='Метаданные')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Маппинг колонки поставщика'
        verbose_name_plural = 'Маппинги колонок поставщиков'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['scope', 'source_column']),
            models.Index(fields=['target_field']),
        ]

    def __str__(self):
        return f"{self.source_column} -> {self.target_field} ({self.scope})"


class ParseRun(models.Model):
    """
    Аудит одного запуска парсера (legacy/v2/shadow).
    """

    file = models.ForeignKey(
        'File',
        on_delete=models.CASCADE,
        related_name='parse_runs',
        verbose_name='Файл',
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='parse_runs',
        verbose_name='Поставщик',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='parse_runs',
        verbose_name='Пользователь',
    )
    pipeline_version = models.CharField(max_length=50, default='legacy', verbose_name='Версия пайплайна')
    status = models.CharField(max_length=20, verbose_name='Статус')
    items_count = models.IntegerField(default=0, verbose_name='Количество позиций')
    warning_count = models.IntegerField(default=0, verbose_name='Количество предупреждений')
    error_count = models.IntegerField(default=0, verbose_name='Количество ошибок')
    parse_kwargs = models.JSONField(default=dict, blank=True, verbose_name='Параметры запуска')
    summary = models.JSONField(default=dict, blank=True, verbose_name='Сводка запуска')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата запуска')

    class Meta:
        verbose_name = 'Запуск парсинга'
        verbose_name_plural = 'Запуски парсинга'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['pipeline_version', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"ParseRun #{self.id} [{self.pipeline_version}] {self.status}"


class ParsingFeedback(models.Model):
    """
    Обратная связь по спорным сопоставлениям колонок.
    """

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='parsing_feedbacks',
        verbose_name='Поставщик',
    )
    parse_run = models.ForeignKey(
        ParseRun,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='feedback_items',
        verbose_name='Запуск парсинга',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='parsing_feedbacks',
        verbose_name='Пользователь',
    )
    source_column = models.CharField(max_length=255, verbose_name='Исходная колонка')
    suggested_field = models.CharField(max_length=100, verbose_name='Предложенное поле')
    accepted = models.BooleanField(default=True, verbose_name='Принято')
    confidence = models.FloatField(default=0.0, validators=[MinValueValidator(0)], verbose_name='Уверенность')
    note = models.TextField(blank=True, verbose_name='Комментарий')
    context = models.JSONField(default=dict, blank=True, verbose_name='Контекст')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата')

    class Meta:
        verbose_name = 'Обратная связь парсинга'
        verbose_name_plural = 'Обратная связь парсинга'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['accepted', '-created_at']),
            models.Index(fields=['source_column']),
        ]

    def __str__(self):
        verdict = 'ok' if self.accepted else 'reject'
        return f"{self.source_column} -> {self.suggested_field} ({verdict})"


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

    def truncate_varchar_fields(self):
        """Подрезает CharField под max_length (прайсы часто дают длиннее лимита БД)."""
        for field in self._meta.concrete_fields:
            if isinstance(field, CharField) and field.max_length:
                val = getattr(self, field.attname)
                if isinstance(val, str) and len(val) > field.max_length:
                    logger.debug(
                        'Усечение %s с %s до %s символов (file_id=%s)',
                        field.name,
                        len(val),
                        field.max_length,
                        self.file_id,
                    )
                    setattr(self, field.attname, val[: field.max_length])

    def save(self, *args, **kwargs):
        self.truncate_varchar_fields()
        super().save(*args, **kwargs)

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


class TapLocation(models.Model):
    """
    Модель для хранения локаций/заведений с кранами.
    """
    name = models.CharField(
        max_length=255,
        verbose_name='Название локации'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    class Meta:
        verbose_name = 'Локация'
        verbose_name_plural = 'Локации'
        ordering = ['name']

    def __str__(self):
        return self.name


class Tap(models.Model):
    """
    Модель для хранения информации о кране.
    """
    STATUS_CHOICES = [
        ('active', 'Активен'),
        ('free', 'Свободно'),
        ('next', 'След на кран'),      # Светло-синий
        ('fresh', 'Свежее/Новое'),     # Зеленый
    ]
    
    location = models.ForeignKey(
        TapLocation,
        on_delete=models.CASCADE,
        related_name='taps',
        verbose_name='Локация'
    )
    position = models.IntegerField(
        verbose_name='Номер крана'
    )
    # Текущее пиво на кране
    brewery = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Пивоварня'
    )
    beer_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Название пива'
    )
    price_per_liter = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='Цена за литр'
    )
    description = models.TextField(
        blank=True,
        default='',
        verbose_name='Описание кеги'
    )
    # Очередь - следующие позиции
    next_beer_1 = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Следующее пиво 1'
    )
    next_beer_2 = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Следующее пиво 2'
    )
    # Цвета для каждой ячейки
    color_current = models.CharField(
        max_length=20,
        blank=True,
        default='',
        verbose_name='Цвет текущего'
    )
    color_next1 = models.CharField(
        max_length=20,
        blank=True,
        default='',
        verbose_name='Цвет след 1'
    )
    color_next2 = models.CharField(
        max_length=20,
        blank=True,
        default='',
        verbose_name='Цвет след 2'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name='Статус'
    )
    is_visible = models.BooleanField(
        default=True,
        verbose_name='Видимость'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )

    class Meta:
        verbose_name = 'Кран'
        verbose_name_plural = 'Краны'
        ordering = ['location', 'position']
        unique_together = ['location', 'position']

    def __str__(self):
        return f"Кран #{self.position} - {self.brewery} {self.beer_name}"


class AvailableBeer(models.Model):
    """
    Модель для хранения доступных позиций пива для кранов.
    """
    location = models.ForeignKey(
        TapLocation,
        on_delete=models.CASCADE,
        related_name='available_beers',
        verbose_name='Локация'
    )
    brewery = models.CharField(
        max_length=255,
        verbose_name='Пивоварня'
    )
    beer_name = models.CharField(
        max_length=255,
        verbose_name='Название пива'
    )
    price_per_liter = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='Цена за литр'
    )
    description = models.TextField(
        blank=True,
        default='',
        verbose_name='Описание кеги'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата добавления'
    )

    class Meta:
        verbose_name = 'Доступное пиво'
        verbose_name_plural = 'Доступное пиво'
        ordering = ['brewery', 'beer_name']

    def __str__(self):
        return f"{self.brewery} | {self.beer_name}"


class TapChangeHistory(models.Model):
    """
    Модель для хранения истории изменений на кранах.
    
    Фиксирует все изменения пива на кранах: установку нового,
    изменение цены, сдвиг очереди и т.д.
    """
    CHANGE_TYPE_CHOICES = [
        ('installed', 'Установлено'),
        ('removed', 'Убрано'),
        ('price_changed', 'Изменена цена'),
        ('queue_shifted', 'Сдвинута очередь'),
        ('updated', 'Обновлено'),
    ]
    
    tap = models.ForeignKey(
        Tap,
        on_delete=models.CASCADE,
        related_name='change_history',
        verbose_name='Кран'
    )
    change_type = models.CharField(
        max_length=20,
        choices=CHANGE_TYPE_CHOICES,
        verbose_name='Тип изменения'
    )
    # Старые значения
    old_brewery = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Старая пивоварня'
    )
    old_beer_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Старое название'
    )
    old_price_per_liter = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='Старая цена'
    )
    # Новые значения
    new_brewery = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Новая пивоварня'
    )
    new_beer_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Новое название'
    )
    new_price_per_liter = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='Новая цена'
    )
    # Информация об очереди
    old_next_beer_1 = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Старое след 1'
    )
    old_next_beer_2 = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Старое след 2'
    )
    new_next_beer_1 = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Новое след 1'
    )
    new_next_beer_2 = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Новое след 2'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата изменения'
    )
    notes = models.TextField(
        blank=True,
        verbose_name='Примечания'
    )

    class Meta:
        verbose_name = 'История изменения крана'
        verbose_name_plural = 'История изменений кранов'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tap', '-created_at']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"Изменение крана #{self.tap.position} - {self.change_type} ({self.created_at})"
