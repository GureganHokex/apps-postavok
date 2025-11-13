"""
API views для парсинга прайсов и работы с заказами.
"""

import os
import zipfile
import logging
import traceback
from pathlib import Path
from django.conf import settings
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from .models import File, ParsedItem, FileMetadata, Order
from .serializers import (
    FileSerializer, ParsedItemSerializer, FileMetadataSerializer,
    OrderSerializer, OrderCreateSerializer
)
from .parsers.pdf_parser import PDFParser
from .parsers.excel_parser import ExcelParser
from .parsers.google_sheets_parser import GoogleSheetsParser
from .filters import ContactFilter
from .normalizers import DataNormalizer
from .exporters import OrderExporter
from .utils import detect_file_type, extract_zip

logger = logging.getLogger(__name__)


class FileViewSet(viewsets.ModelViewSet):
    """ViewSet для работы с файлами."""
    
    queryset = File.objects.all()
    serializer_class = FileSerializer
    
    @action(detail=True, methods=['post'])
    def parse(self, request, pk=None):
        """
        Запускает парсинг файла.
        
        POST /api/files/<id>/parse/
        """
        file_obj = self.get_object()
        
        # Определяем парсер в зависимости от типа файла
        parser = None
        # Получаем полный путь к файлу
        file_full_path = Path(settings.MEDIA_ROOT) / file_obj.file_path
        if file_obj.file_type == 'pdf':
            parser = PDFParser(str(file_full_path))
        elif file_obj.file_type == 'excel':
            parser = ExcelParser(str(file_full_path))
        elif file_obj.file_type == 'google_sheets':
            parser = GoogleSheetsParser(
                str(file_full_path),
                file_obj.google_sheet_url
            )
        
        if not parser:
            return Response(
                {'error': 'Неизвестный тип файла'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Парсим файл
        try:
            logger.info(f"Начало парсинга файла {file_obj.original_filename} (тип: {file_obj.file_type})")
            raw_items = parser.parse()
            logger.info(f"Парсинг завершен, извлечено {len(raw_items)} позиций")
        except Exception as e:
            error_traceback = traceback.format_exc()
            logger.error(f"Ошибка парсинга файла {file_obj.original_filename}: {str(e)}\n{error_traceback}", exc_info=True)
            return Response(
                {'error': f'Ошибка парсинга: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Фильтруем и нормализуем данные
        contact_filter = ContactFilter()
        normalizer = DataNormalizer()
        
        all_contacts = {
            'phones': [],
            'emails': [],
            'addresses': [],
            'links': []
        }
        extra_texts = []
        product_items = []
        skipped_count = 0
        
        for raw_item in raw_items:
            # Собираем текст строки для фильтрации
            row_text = ' '.join(str(v) for v in raw_item.values() if v)
            
            # Проверяем, является ли строка товарной
            is_product, contacts = contact_filter.filter_row(raw_item, row_text)
            
            if is_product:
                # Нормализуем данные
                normalized_item = normalizer.normalize_item(raw_item)
                normalized_item['file'] = file_obj
                
                # Создаем ParsedItem
                parsed_item = ParsedItem.objects.create(**normalized_item)
                product_items.append(parsed_item)
            else:
                # Сохраняем контакты и служебные тексты
                skipped_count += 1
                for key, values in contacts.items():
                    if values:
                        all_contacts[key].extend(values)
                
                # Извлекаем служебные тексты
                extra = contact_filter.extract_extra_text(row_text)
                extra_texts.extend(extra)
        
        # Создаем или обновляем метаданные
        metadata, created = FileMetadata.objects.get_or_create(file=file_obj)
        metadata.contacts = all_contacts
        metadata.extra_text = list(set(extra_texts))  # Убираем дубликаты
        metadata.summary = {
            'total_items': len(product_items),
            'skipped_rows': skipped_count,
            'contacts_found': {
                'phones': len(all_contacts['phones']),
                'emails': len(all_contacts['emails']),
                'addresses': len(all_contacts['addresses']),
                'links': len(all_contacts['links']),
            }
        }
        metadata.save()
        
        return Response({
            'message': 'Парсинг завершен',
            'items_created': len(product_items),
            'skipped_rows': skipped_count,
            'summary': metadata.summary
        })
    
    @action(detail=True, methods=['get'])
    def items(self, request, pk=None):
        """
        Возвращает список позиций файла.
        
        GET /api/files/<id>/items/
        """
        file_obj = self.get_object()
        items = ParsedItem.objects.filter(file=file_obj)
        
        # Фильтрация по запросу
        brewery = request.query_params.get('brewery')
        if brewery:
            items = items.filter(brewery__icontains=brewery)
        
        beer_name = request.query_params.get('beer_name')
        if beer_name:
            items = items.filter(beer_name__icontains=beer_name)
        
        style = request.query_params.get('style')
        if style:
            items = items.filter(style__icontains=style)
        
        # Фильтрация по листу
        sheet = request.query_params.get('sheet')
        if sheet:
            items = items.filter(raw_source_location__sheet=sheet)
        
        # Ограничиваем количество возвращаемых элементов для производительности
        limit = request.query_params.get('limit')
        if limit:
            try:
                limit = int(limit)
                items = items[:limit]
            except ValueError:
                pass
        else:
            # По умолчанию ограничиваем до 1000 элементов
            items = items[:1000]
        
        serializer = ParsedItemSerializer(items, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def sheets(self, request, pk=None):
        """
        Возвращает список листов файла с количеством позиций в каждом.
        
        GET /api/files/<id>/sheets/
        """
        file_obj = self.get_object()
        
        # Оптимизированный запрос - используем только нужные поля
        from django.db.models import Count
        
        try:
            # Используем values() для оптимизации запроса
            sheets_data = ParsedItem.objects.filter(
                file=file_obj
            ).exclude(
                raw_source_location__sheet__isnull=True
            ).exclude(
                raw_source_location__sheet=''
            ).values('raw_source_location__sheet').annotate(
                count=Count('id')
            ).order_by('raw_source_location__sheet')[:100]  # Ограничиваем до 100 листов
            
            sheets_list = [
                {
                    'name': item['raw_source_location__sheet'],
                    'count': item['count']
                }
                for item in sheets_data
            ]
            
            return Response({'sheets': sheets_list})
        except Exception as e:
            logger.error(f"Ошибка при получении списка листов: {str(e)}", exc_info=True)
            return Response({'sheets': []}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def metadata(self, request, pk=None):
        """
        Возвращает метаданные файла.
        
        GET /api/files/<id>/metadata/
        """
        file_obj = self.get_object()
        try:
            metadata = file_obj.metadata
            serializer = FileMetadataSerializer(metadata)
            return Response(serializer.data)
        except FileMetadata.DoesNotExist:
            return Response(
                {'error': 'Метаданные не найдены. Запустите парсинг файла.'},
                status=status.HTTP_404_NOT_FOUND
            )


class ParsedItemViewSet(viewsets.ModelViewSet):
    """ViewSet для работы с распарсенными позициями."""
    
    queryset = ParsedItem.objects.all()
    serializer_class = ParsedItemSerializer


class OrderViewSet(viewsets.ModelViewSet):
    """ViewSet для работы с заказами."""
    
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    
    def create(self, request):
        """
        Создает новый заказ.
        
        POST /api/orders/
        Body: {
            "items": [{"item_id": 1, "quantity": 5}, ...],
            "export_format": "excel"
        }
        """
        serializer = OrderCreateSerializer(data=request.data)
        if serializer.is_valid():
            order = Order.objects.create(
                items=serializer.validated_data['items'],
                export_format=serializer.validated_data['export_format']
            )
            return Response(
                OrderSerializer(order).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def export(self, request, pk=None):
        """
        Экспортирует заказ и возвращает файл для скачивания.
        
        GET /api/orders/<id>/export/
        """
        order = self.get_object()
        
        # Если файл еще не экспортирован, создаем его
        if not order.export_file_path:
            exporter = OrderExporter(order)
            exporter.export()
        
        # Путь к файлу
        file_path = Path(settings.MEDIA_ROOT) / order.export_file_path
        
        if not file_path.exists():
            return Response(
                {'error': 'Экспортированный файл не найден'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Возвращаем файл для скачивания
        return FileResponse(
            open(file_path, 'rb'),
            as_attachment=True,
            filename=file_path.name
        )


@api_view(['POST'])
def upload_file(request):
    """
    Загружает файл на сервер.
    
    POST /api/upload/
    Body: multipart/form-data с полем 'file'
    """
    if 'file' not in request.FILES:
        return Response(
            {'error': 'Файл не предоставлен'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    uploaded_file = request.FILES['file']
    
    # Определяем тип файла
    file_type = detect_file_type(uploaded_file.name)
    
    if file_type == 'unknown':
        return Response(
            {'error': 'Неподдерживаемый тип файла'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Сохраняем файл
    upload_dir = Path(settings.MEDIA_ROOT) / 'uploads'
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = upload_dir / uploaded_file.name
    with open(file_path, 'wb+') as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)
    
    # Сохраняем относительный путь от MEDIA_ROOT
    relative_path = file_path.relative_to(settings.MEDIA_ROOT)
    
    # Если это ZIP, распаковываем
    if file_type == 'zip':
        extract_dir = upload_dir / f"{uploaded_file.name}_extracted"
        extract_dir.mkdir(exist_ok=True)
        extracted_files = extract_zip(str(file_path), str(extract_dir))
        
        # Создаем записи для каждого файла
        files = []
        for extracted_file in extracted_files:
            extracted_type = detect_file_type(extracted_file)
            if extracted_type != 'unknown':
                extracted_relative = Path(extracted_file).relative_to(settings.MEDIA_ROOT)
                file_obj = File.objects.create(
                    original_filename=Path(extracted_file).name,
                    file_type=extracted_type,
                    file_path=str(extracted_relative)
                )
                files.append(file_obj)
        
        serializer = FileSerializer(files, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    # Создаем запись о файле
    file_obj = File.objects.create(
        original_filename=uploaded_file.name,
        file_type=file_type,
        file_path=str(relative_path)
    )
    
    serializer = FileSerializer(file_obj)
    return Response(serializer.data, status=status.HTTP_201_CREATED)

