# Инструкция по запуску

## Предварительные требования

- Python 3.10+
- Node.js 16+
- npm или yarn

## Быстрый старт

### 1. Backend (Django)

```bash
cd backend

# Создайте виртуальное окружение
python3 -m venv venv
source venv/bin/activate  # На Windows: venv\Scripts\activate

# Установите зависимости
pip install -r requirements.txt

# Выполните миграции
python manage.py makemigrations
python manage.py migrate

# Создайте суперпользователя (опционально)
python manage.py createsuperuser

# Запустите сервер
python manage.py runserver
```

Backend будет доступен по адресу: http://localhost:8000

### 2. Frontend (React)

```bash
cd frontend

# Установите зависимости
npm install

# Запустите сервер разработки
npm start
```

Frontend будет доступен по адресу: http://localhost:3000

## Использование

1. Откройте браузер и перейдите на http://localhost:3000
2. Загрузите файл с прайсом (PDF, Excel или ZIP архив)
3. Нажмите кнопку "Парсить" для запуска парсинга
4. Просмотрите результаты в таблице позиций
5. При необходимости отредактируйте позиции
6. Выберите позиции для заказа и укажите количество
7. Создайте заказ и экспортируйте его в нужном формате

## API Endpoints

- `POST /api/upload/` - загрузка файла
- `POST /api/files/<id>/parse/` - запуск парсинга
- `GET /api/files/<id>/items/` - список позиций
- `GET /api/files/<id>/metadata/` - метаданные файла
- `PATCH /api/items/<id>/` - редактирование позиции
- `POST /api/orders/` - создание заказа
- `GET /api/orders/<id>/export/` - скачивание заказа

## Заметки

- Для работы с Google Sheets требуется настройка API ключа (опционально)
- OCR для сканов PDF требует установки Tesseract: https://github.com/tesseract-ocr/tesseract
- Файлы сохраняются в `backend/media/uploads/`
- Экспортированные заказы сохраняются в `backend/media/exports/`

