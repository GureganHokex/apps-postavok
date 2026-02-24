"""
Сервис для оркестрации процесса парсинга файлов.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from django.conf import settings
from django.core.cache import cache

from parser_app.models import File, FileMetadata
from parser_app.infrastructure.parsers.pdf_parser import PDFParser
from parser_app.infrastructure.parsers.excel_parser import ExcelParser
from parser_app.infrastructure.parsers.google_sheets_parser import GoogleSheetsParser
from parser_app.application.use_cases.item_processing_service import ItemProcessingService
from parser_app.shared.constants import CACHE_TIMEOUT_PARSE_PROGRESS, CACHE_TIMEOUT_COMPLETED

logger = logging.getLogger(__name__)


class ParsingService:
    """
    Сервис для оркестрации процесса парсинга файлов.
    
    Отвечает за:
    - Выбор подходящего парсера
    - Координацию процесса парсинга
    - Обновление прогресса
    - Создание метаданных
    """
    
    def __init__(self):
        self.item_processor = ItemProcessingService()
    
    def parse_file(
        self,
        file_obj: File,
        supplier_type: Optional[str] = None,
        brewery_name: Optional[str] = None,
        progress_key: Optional[str] = None
    ) -> Tuple[List, Dict]:
        """
        Парсит файл и обрабатывает результаты.
        
        Args:
            file_obj: Объект File для парсинга
            supplier_type: Тип поставщика ('distributor' или 'brewery')
            brewery_name: Название пивоварни (для типа 'brewery')
            progress_key: Ключ для обновления прогресса в кэше
            
        Returns:
            Tuple (product_items, metadata_summary)
        """
        # Получаем парсер
        parser = self._get_parser(file_obj)
        if not parser:
            raise ValueError(f'Неизвестный тип файла: {file_obj.file_type}')
        
        # Обновляем прогресс - парсинг начался
        self._update_progress(
            progress_key,
            status='parsing',
            progress=10,
            message='Парсинг файла...'
        )
        
        # Парсим файл
        logger.info(
            f"Начало парсинга файла {file_obj.original_filename} "
            f"(тип: {file_obj.file_type}, supplier_type: {supplier_type}, "
            f"brewery_name: {brewery_name})"
        )
        
        parse_kwargs = {}
        if supplier_type:
            parse_kwargs['supplier_type'] = supplier_type
        if brewery_name:
            parse_kwargs['brewery_name'] = brewery_name
        
        raw_items = parser.parse(**parse_kwargs)
        logger.info(f"Парсинг завершен, извлечено {len(raw_items)} позиций")
        
        parse_report = getattr(parser, 'parse_report', None) or {}
        
        # Обновляем прогресс - парсинг завершен, начинаем обработку
        self._update_progress(
            progress_key,
            status='processing',
            progress=30,
            message=f'Обработка {len(raw_items)} позиций...',
            total_items=len(raw_items),
            processed_items=0
        )
        
        # Обрабатываем позиции
        def progress_callback(processed: int, total: int):
            progress = 30 + int((processed / total * 60)) if total > 0 else 30
            self._update_progress(
                progress_key,
                status='processing',
                progress=progress,
                message=f'Обработка позиций: {processed} из {total}',
                total_items=total,
                processed_items=processed
            )
        
        product_items, all_contacts, extra_texts, validation_stats, skipped_count = \
            self.item_processor.process_raw_items(
                raw_items,
                file_obj,
                progress_key=progress_key,
                progress_callback=progress_callback
            )
        
        # Создаем метаданные
        metadata_summary = self._create_metadata(
            file_obj,
            product_items,
            all_contacts,
            extra_texts,
            validation_stats,
            skipped_count,
            parser
        )
        if parse_report:
            metadata_summary['parse_report'] = parse_report
        
        # Завершаем прогресс
        self._update_progress(
            progress_key,
            status='completed',
            progress=100,
            message=f'Парсинг завершен! Обработано {len(product_items)} позиций',
            total_items=len(product_items),
            processed_items=len(product_items)
        )
        
        return product_items, metadata_summary
    
    def _get_parser(self, file_obj: File):
        """
        Возвращает подходящий парсер для файла.
        
        Args:
            file_obj: Объект File
            
        Returns:
            Экземпляр парсера или None
        """
        file_full_path = Path(settings.MEDIA_ROOT) / file_obj.file_path
        
        if file_obj.file_type == 'pdf':
            return PDFParser(str(file_full_path))
        elif file_obj.file_type == 'excel':
            return ExcelParser(str(file_full_path))
        elif file_obj.file_type == 'google_sheets':
            return GoogleSheetsParser(
                str(file_full_path),
                file_obj.google_sheet_url
            )
        
        return None
    
    def _create_metadata(
        self,
        file_obj: File,
        product_items: List,
        all_contacts: Dict,
        extra_texts: List[str],
        validation_stats: Dict,
        skipped_count: int,
        parser
    ) -> Dict:
        """
        Создает или обновляет метаданные файла.
        
        Args:
            file_obj: Объект File
            product_items: Список созданных позиций
            all_contacts: Словарь с контактами
            extra_texts: Список служебных текстов
            validation_stats: Статистика валидации
            skipped_count: Количество пропущенных строк
            parser: Экземпляр парсера
            
        Returns:
            Словарь с метаданными
        """
        metadata, created = FileMetadata.objects.get_or_create(file=file_obj)
        metadata.contacts = all_contacts
        metadata.extra_text = list(set(extra_texts))  # Убираем дубликаты
        
        metadata.summary = {
            'total_items': len(product_items),
            'skipped_rows': skipped_count,
            'contacts_found': {
                'phones': len(all_contacts.get('phones', [])),
                'emails': len(all_contacts.get('emails', [])),
                'addresses': len(all_contacts.get('addresses', [])),
                'links': len(all_contacts.get('links', [])),
            },
            'validation': {
                'valid': validation_stats.get('valid', 0),
                'invalid': validation_stats.get('invalid', 0),
                'total_errors': validation_stats.get('total_errors', 0),
                'total_warnings': validation_stats.get('total_warnings', 0),
            },
            'parser_stats': getattr(parser, 'stats', {}),
        }
        metadata.save()
        
        return metadata.summary
    
    def _update_progress(
        self,
        progress_key: Optional[str],
        status: str,
        progress: int,
        message: str,
        total_items: int = 0,
        processed_items: int = 0
    ):
        """
        Обновляет прогресс парсинга в кэше.
        
        Args:
            progress_key: Ключ для кэша
            status: Статус парсинга
            progress: Процент выполнения (0-100)
            message: Сообщение о прогрессе
            total_items: Общее количество позиций
            processed_items: Обработанное количество позиций
        """
        if not progress_key:
            return
        
        try:
            cache.set(
                progress_key,
                {
                    'status': status,
                    'progress': progress,
                    'message': message,
                    'total_items': total_items,
                    'processed_items': processed_items,
                },
                timeout=CACHE_TIMEOUT_PARSE_PROGRESS if status != 'completed' else CACHE_TIMEOUT_COMPLETED
            )
        except Exception as e:
            logger.warning(f"Ошибка обновления прогресса в кэше: {e}")
