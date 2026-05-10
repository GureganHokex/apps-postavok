# Apps Postavok / Пивной импортёр

Веб-приложение для баров: загружает прайсы поставщиков, парсит позиции из PDF/Excel/Google Sheets, помогает собрать заказ, вести историю заказов и управлять кранами.

Проект состоит из Django REST API и React SPA. Авторизация сессионная, роли разграничивают доступ к админским действиям, работе бармена и публичному управлению видимостью кранов.

## Возможности

- Загрузка прайсов: PDF, Excel (`.xls`, `.xlsx`), ZIP с файлами, Google Sheets через CSV-экспорт.
- Парсинг и нормализация позиций: пивоварня, название, формат, объём, цена, остатки, поставщик, источник строки/листа.
- Ручное редактирование распарсенных позиций, bulk update и bulk delete.
- Создание заказов и экспорт в Excel/PDF.
- История заказов и статистика.
- Управление поставщиками и маппингом колонок.
- Управление кранами: локации, текущие позиции, очередь `след 1/след 2`, цветовые метки, доступные позиции, история изменений.
- Админ-панель для пользователей и ролей.

## Архитектура

```text
apps-postavok/
├── backend/                 # Django + DRF API
│   ├── beer_app/            # настройки Django-проекта
│   ├── parser_app/          # доменная логика, API, парсеры, экспорт
│   ├── media/               # загруженные и сгенерированные файлы
│   ├── requirements.txt
│   └── entrypoint.sh
├── frontend/                # React SPA
│   ├── public/
│   ├── src/
│   ├── package.json
│   └── vercel.json
├── docker-compose.backend.yml
├── render.yaml
└── README.md
```

Основной backend-роутинг подключён через `backend/parser_app/urls.py`. Legacy-код в `backend/parser_app/presentation/` сейчас не подключён к URL и не является активным API.

## Технологии

Backend:

- Python 3.12, Django 4.2, Django REST Framework
- SQLite для локального MVP или PostgreSQL через `DB_ENGINE=postgresql`
- `pandas`, `openpyxl`, `pdfplumber`, `pypdf`, `pytesseract`, `Pillow`
- `reportlab` для экспорта
- `gunicorn` в production

Frontend:

- React 18, React Router
- Axios с `withCredentials`
- TanStack Query
- React Dropzone, React Hook Form, Zod
- Framer Motion, Recharts

## Локальный запуск

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
```

Создайте администратора:

```bash
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=ваш_пароль
python manage.py create_admin_user
```

Запустите API:

```bash
python manage.py runserver
```

Backend будет доступен на `http://localhost:8000`.

### Frontend

```bash
cd frontend
npm install
npm start
```

Frontend будет доступен на `http://localhost:3000`.

В dev-режиме `frontend/package.json` проксирует запросы на `http://localhost:8000`.

## Запуск backend через Docker/PostgreSQL

```bash
docker compose -f docker-compose.backend.yml up --build
```

Compose поднимает:

- `postgres` на PostgreSQL 16
- `backend` на `http://localhost:8000`
- volume для PostgreSQL и bind mount `backend/media`

Перед production-запуском не используйте секреты из `backend/env.example` как реальные значения.

## Переменные окружения

Пример backend-конфига лежит в `backend/env.example`.

Основные переменные:

- `DJANGO_SECRET_KEY` — секрет Django, обязателен для production.
- `DJANGO_DEBUG` — `true` только локально.
- `DJANGO_ALLOWED_HOSTS` — список доменов backend.
- `DJANGO_CSRF_TRUSTED_ORIGINS` — доверенные origins для Django.
- `CORS_ALLOWED_ORIGINS` — origins frontend-приложения.
- `DB_ENGINE` — `sqlite3` или `postgresql`.
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_SSLMODE` — параметры БД.
- `ADMIN_USERNAME`, `ADMIN_PASSWORD` — создание/обновление администратора командой `create_admin_user`.
- `EXCEL_PARSER_PIPELINE_V2`, `PARSER_LEGACY_FORCE`, `PARSER_SHADOW_MODE` — флаги переключения parser pipeline.

Для frontend:

- `REACT_APP_API_URL` — базовый URL API. Если не задан, используется `http://localhost:8000/api`.

## Авторизация и роли

Все рабочие API-запросы требуют сессионной авторизации, кроме login.

- `admin` — полный доступ: файлы, парсинг, позиции, заказы, поставщики, краны, пользователи, статистика.
- `bartender` — работа с кранами и просмотр истории заказов в интерфейсе.
- `user` — просмотр кранов и переключение видимости.

Создать первого администратора:

```bash
cd backend
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=ваш_пароль
python manage.py create_admin_user
```

Остальных пользователей можно создать через админ-панель приложения или Django Admin.

## Страницы приложения

- `/` — основное приложение.
- `/admin` — управление пользователями, доступно только администратору.
- `/?page=admin` — альтернативный вход для сценариев, где используется `admin.html`.

Основные вкладки:

- `Загрузка файлов` — загрузка и парсинг прайсов.
- `История заказов` — просмотр и скачивание заказов.
- `Краны` — локации, краны, очередь, видимость, доступные позиции.
- `Настройки поставщиков` — маппинг колонок и настройки поставщика.
- `Статистика` — агрегаты по заказам.
- `Админ-панель` — пользователи и роли.

## Основной workflow

1. Войти администратором.
2. Загрузить прайс поставщика.
3. Выбрать тип поставщика или настройки маппинга при необходимости.
4. Запустить парсинг.
5. Проверить и отредактировать позиции.
6. Сформировать заказ и экспортировать файл.
7. При необходимости перенести позиции в краны или обновить очередь.

## API

Базовый URL: `/api`.

Авторизация:

- `POST /api/auth/login/` — вход, тело: `username`, `password`.
- `GET /api/auth/me/` — текущий пользователь и роль.
- `POST /api/auth/logout/` — выход.

Файлы и парсинг:

- `POST /api/upload/` — загрузка файла.
- `GET /api/files/` — список файлов.
- `POST /api/files/<id>/parse/` — запуск парсинга (**202 Accepted** сразу, работа в фоне; итог — `parse_progress/` + позиции).
- `GET /api/files/<id>/parse_progress/` — прогресс парсинга.
- `GET /api/files/<id>/items/` — позиции файла.
- `GET /api/files/<id>/metadata/` — метаданные.

Позиции:

- `PATCH /api/items/<id>/` — редактирование позиции.
- `DELETE /api/items/<id>/` — удаление позиции.
- `PATCH /api/items/bulk_update/` — массовое обновление.
- `POST /api/items/bulk_delete/` — массовое удаление.

Заказы:

- `GET /api/orders/` — история заказов.
- `POST /api/orders/` — создание заказа.
- `GET /api/orders/<id>/` — детали заказа.
- `GET /api/orders/<id>/export/` — скачивание экспорта.
- `GET /api/orders/statistics/` — статистика.

Краны:

- `GET/POST /api/locations/` — список и создание локаций.
- `GET/PATCH/DELETE /api/locations/<id>/` — локация.
- `GET/POST /api/locations/<id>/taps/` — краны локации.
- `POST /api/locations/<id>/add_from_parser/` — добавить позицию из парсера.
- `PATCH/DELETE /api/taps/<id>/` — изменение/удаление крана.
- `POST /api/taps/reorder/` — изменение порядка.
- `GET/POST /api/available-beers/` — доступные позиции для кранов.
- `POST /api/available-beers/bulk_create/` — массовое добавление.

Администрирование:

- `GET/POST /api/users/` — пользователи.
- `PATCH/DELETE /api/users/<id>/` — изменение/удаление пользователя.
- `GET/POST /api/suppliers/` — поставщики.
- `PATCH/DELETE /api/suppliers/<id>/` — изменение/удаление поставщика.
- `GET /api/parse-runs/` — история запусков парсинга.
- `GET/POST /api/column-mappings/` — ручные маппинги колонок.
- `GET/POST /api/parsing-feedback/` — feedback по парсингу.

## Деплой

**Vercel → Render:** `frontend/vercel.json` проксирует `/api` на backend. У платформенного rewrite короткий лимит ожидания ответа; долгий синхронный `POST …/parse/` давал 502 и HTML вместо JSON. Парсинг вынесен в фон после **202**; прогресс — `GET …/parse_progress/`. Тяжёлый `POST /api/upload/` при очень больших файлах всё ещё может упираться в лимит шлюза — тогда имеет смысл `REACT_APP_FORCE_API_URL` на прямой Render (см. комментарии в `frontend/src/api.js`).

**Фоновые задачи / cron:** в репозитории нет Celery, django-crontab и отдельных Render Cron Jobs в `render.yaml`; синхронизация данных — по HTTP API и ручным действиям в UI. При появлении периодических задач их лучше оформить отдельным Render Cron или management-командой + внешний планировщик.

Backend рассчитан на Render:

- конфиг: `render.yaml`
- start command: `bash entrypoint.sh`
- `entrypoint.sh` выполняет `migrate`, `collectstatic`, затем запускает `gunicorn`
- production-БД: PostgreSQL

Frontend рассчитан на Vercel:

- конфиг: `frontend/vercel.json`
- rewrite `/api/*` и `/media/*` на Render backend

Для production обязательно задайте:

- `DJANGO_SECRET_KEY`
- `ADMIN_PASSWORD`
- PostgreSQL credentials
- корректные `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`

## Частые проблемы

### `Request failed with status code 403`

Проверьте два случая:

1. Пользователь не имеет нужной роли. Создание локаций, поставщиков, пользователей, загрузка и парсинг доступны только `admin`.
2. Backend не перезапущен после изменений. SPA использует cookie-сессию, а unsafe API-запросы (`POST/PATCH/DELETE`) в активных ViewSet'ах должны работать через `SessionAuthenticationNoCSRF`.

### Не создаётся локация в «Кранах»

Нужно быть администратором. Введите название и нажмите `✓` или `Enter`. Если toast показывает `403`, проверьте роль текущего пользователя и перезапустите backend.

### `Network Error`

Проверьте, что backend запущен на `http://localhost:8000`, а frontend использует правильный `REACT_APP_API_URL` или dev proxy.

### Парсинг PDF/OCR не работает локально

Установите системные зависимости для OCR/PDF. В Dockerfile они уже добавлены: `tesseract-ocr`, `poppler-utils`, библиотеки для Pillow/lxml.

## Проверки перед коммитом

Backend:

```bash
cd backend
python manage.py check
python manage.py migrate --check
```

Frontend:

```bash
cd frontend
npm test
npm run build
```

## Статус

Проект находится в MVP/внутренней production-ready итерации для работы бара с прайсами, заказами и кранами.

