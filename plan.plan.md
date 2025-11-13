<!-- f2577bee-447c-4532-82d7-bfcdf332dcf5 da2acf06-1130-4c3a-a6f5-a8d5df20b6f7 -->
# План реализации MVP "Пивной импортер"

## Структура проекта

```
apps-postavok/
├── backend/                    # Django приложение
│   ├── manage.py
│   ├── beer_app/              # Основной проект Django
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   ├── parser_app/            # Основное приложение
│   │   ├── models.py          # File, ParsedItem, FileMetadata, Order
│   │   ├── views.py           # API endpoints
│   │   ├── serializers.py     # DRF serializers
│   │   ├── parsers/
│   │   │   ├── __init__.py
│   │   │   ├── base_parser.py # Базовый класс парсера
│   │   │   ├── pdf_parser.py  # PDF парсинг (pdfplumber, OCR)
│   │   │   ├── excel_parser.py # Excel парсинг (pandas)
│   │   │   └── google_sheets_parser.py # Google Sheets API
│   │   ├── normalizers.py     # Нормализация данных
│   │   ├── filters.py         # Фильтрация контактов/служебных данных
│   │   ├── exporters.py       # Экспорт заказов (PDF/Excel)
│   │   └── utils.py           # Вспомогательные функции
│   ├── requirements.txt
│   └── media/                 # Загруженные файлы
├── frontend/                  # React приложение
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   │   ├── FileUpload.jsx # Drag&drop загрузка
│   │   │   ├── ParsedTable.jsx # Таблица результатов
│   │   │   ├── MetadataTab.jsx # Вкладка метаданных
│   │   │   ├── OrderForm.jsx  # Формирование заказа
│   │   │   └── ExportButton.jsx # Экспорт заказа
│   │   ├── App.jsx
│   │   ├── index.js
│   │   └── api.js             # API клиент
│   └── package.json
└── README.md
```

## Модели данных (SQLite)

### File

- `id`, `original_filename`, `file_type` (pdf/excel/google_sheets), `uploaded_at`, `file_path`, `google_sheet_url` (опционально)

### ParsedItem

- `id`, `file` (FK), `brewery`, `beer_name`, `style`, `abv`, `ibu`, `price`, `currency`, `volume`, `format_type`, `stock`, `supplier_name`, `raw_source_location` (JSON), `is_selected` (для заказа)

### FileMetadata

- `id`, `file` (FK), `contacts` (JSON: phones, emails, addresses, links), `extra_text` (JSON: список служебных текстов), `summary` (JSON: статистика парсинга)

### Order

- `id`, `created_at`, `items` (JSON: список {item_id, quantity}), `export_format` (pdf/excel)

## API Endpoints

- `POST /api/upload/` - загрузка файла (multipart/form-data)
- `POST /api/parse/<file_id>/` - запуск парсинга файла
- `GET /api/files/<file_id>/items/` - список позиций с фильтрацией
- `GET /api/files/<file_id>/metadata/` - метаданные файла
- `PATCH /api/items/<item_id>/` - редактирование позиции
- `POST /api/orders/` - создание заказа
- `GET /api/orders/<order_id>/export/` - скачивание экспортированного заказа

## Парсеры

### PDF Parser

- Использовать `pdfplumber` для структурированных PDF
- Для сканов: `pytesseract` + поиск таблиц по координатам
- Извлечение таблиц и текста с координатами

### Excel Parser

- `pandas` для чтения .xls/.xlsx
- Поиск заголовков по вариантам названий ("производитель"/"brewery", "название"/"beer_name", etc.)
- Обработка нескольких листов

### Google Sheets Parser

- `google-api-python-client` для подключения к API
- Экспорт в pandas DataFrame, парсинг аналогично Excel

### Base Parser

- Общий интерфейс: `parse()` возвращает список словарей
- Поддержка ZIP архивов (распаковка и обработка каждого файла)

## Фильтрация и нормализация

### filters.py

- Функции определения контактов (регулярные выражения для телефонов, email, URL)
- Определение служебных строк ("прайс-лист", "менеджер:", "телефон:", "акция", "новинка")
- Отделение товарных строк от служебных

### normalizers.py

- Нормализация единиц измерения (мл → л, унции → мл)
- Нормализация валют (руб/рублей → RUB, usd → USD)
- Парсинг цен из строк типа "150 руб (0,5 л)" → price: 150, volume: 0.5
- Нормализация крепости (5,4% → 5.4, "5.4%" → 5.4)
- Нормализация формата (банка/кега/бутылка → standardized format_type)

## Экспорт заказов

### exporters.py

- `export_to_excel(order, format_type)` - создание Excel с позициями заказа
- `export_to_pdf(order)` - создание PDF заказа (reportlab или weasyprint)
- Сохранение в `media/exports/`, возврат URL для скачивания

## Frontend (React)

### Компоненты

1. **FileUpload**: drag&drop, мультифайл, прогресс загрузки
2. **ParsedTable**: таблица с результатами, редактирование inline, фильтры, выбор позиций
3. **MetadataTab**: отображение контактов, служебных текстов, статистики
4. **OrderForm**: выбор количества для каждой позиции, предпросмотр заказа
5. **ExportButton**: выбор формата экспорта, скачивание

### API Client

- Аксиос для HTTP запросов
- Обработка ошибок, индикаторы загрузки

## Зависимости

### Backend (requirements.txt)

- Django==4.2+
- djangorestframework
- django-cors-headers
- pdfplumber
- pytesseract
- pandas
- openpyxl (для Excel)
- google-api-python-client
- Pillow (для OCR)
- reportlab или weasyprint (для PDF экспорта)

### Frontend (package.json)

- react, react-dom
- react-router-dom
- axios
- react-dropzone (для drag&drop)
- react-table или ag-grid (для таблиц)

## Этапы реализации

1. Настройка Django проекта и базовых моделей
2. Реализация парсеров (PDF → Excel → Google Sheets)
3. Фильтрация и нормализация данных
4. API endpoints для парсинга и работы с данными
5. Экспорт заказов (Excel → PDF)
6. React frontend: загрузка и отображение данных
7. Редактирование и формирование заказов
8. Тестирование и отладка