# Пивной импортер - MVP веб-приложение

Веб-приложение для баров, которое принимает прайсы от поставщиков (PDF, Excel, Google Sheets), автоматически извлекает данные о пиве, позволяет формировать заказ и экспортировать его обратно в исходный формат.

## Структура проекта

- `backend/` - Django REST API приложение
- `frontend/` - React SPA приложение

## Установка и запуск

### Backend

1. Перейдите в директорию backend:
```bash
cd backend
```

2. Создайте виртуальное окружение:
```bash
python3 -m venv venv
source venv/bin/activate  # На Windows: venv\Scripts\activate
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Выполните миграции:
```bash
python manage.py makemigrations
python manage.py migrate
```

5. Создайте суперпользователя (опционально):
```bash
python manage.py createsuperuser
```

6. Запустите сервер разработки:
```bash
python manage.py runserver
```

Backend будет доступен по адресу: http://localhost:8000

### Frontend

1. Перейдите в директорию frontend:
```bash
cd frontend
```

2. Установите зависимости:
```bash
npm install
```

3. Запустите сервер разработки:
```bash
npm start
```

Frontend будет доступен по адресу: http://localhost:3000

## Использование

1. Откройте приложение в браузере (http://localhost:3000)
2. Загрузите файл с прайсом (PDF, Excel или ZIP архив)
3. Запустите парсинг файла
4. Просмотрите распарсенные позиции в таблице
5. При необходимости отредактируйте позиции
6. Выберите позиции для заказа и укажите количество
7. Создайте заказ и экспортируйте его в нужном формате

## API Endpoints

- `POST /api/upload/` - загрузка файла
- `POST /api/files/<id>/parse/` - запуск парсинга файла
- `GET /api/files/<id>/items/` - список позиций файла
- `GET /api/files/<id>/metadata/` - метаданные файла
- `PATCH /api/items/<id>/` - редактирование позиции
- `POST /api/orders/` - создание заказа
- `GET /api/orders/<id>/export/` - скачивание экспортированного заказа

## Особенности

- Парсинг PDF файлов (включая сканы с OCR)
- Парсинг Excel файлов (.xls, .xlsx)
- Поддержка Google Sheets (через CSV экспорт)
- Автоматическая фильтрация контактов и служебных данных
- Нормализация данных (единицы измерения, валюты, форматы)
- Редактирование позиций в интерфейсе
- Экспорт заказов в PDF и Excel

## Технологии

### Backend
- Django 4.2+
- Django REST Framework
- SQLite (для MVP)
- pdfplumber (парсинг PDF)
- pandas (работа с Excel)
- reportlab (экспорт PDF)

### Frontend
- React 18
- React Router
- Axios
- React Dropzone

## Лицензия

MVP версия для внутреннего использования.

