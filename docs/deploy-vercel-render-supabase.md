# Deploy: Vercel + Render + Supabase

Этот сценарий деплоит:
- фронтенд (`frontend`) на **Vercel**
- бэкенд Django (`backend`) на **Render**
- PostgreSQL на **Supabase**

## 1) Supabase: создать БД и взять доступы

1. Создай проект в Supabase.
2. В `Project Settings -> Database` возьми:
   - host (`db.<project-ref>.supabase.co`)
   - port (`5432`)
   - database (`postgres`)
   - user (`postgres`)
   - password (database password)
   - SSL mode: `require`

## 2) Render: деплой backend

В репозитории уже есть `render.yaml` для сервиса `apps-postavok-backend`.

1. Запушь изменения в Git remote.
2. В Render открой Blueprint deploy из репозитория.
3. Заполни обязательные секреты:
   - `DJANGO_SECRET_KEY`
   - `DB_PASSWORD`
   - `DB_HOST` (supabase host)
   - `ADMIN_PASSWORD`
4. Проверь домен backend после деплоя:
   - ожидаемо `https://apps-postavok-backend.onrender.com`
5. Убедись, что миграции прошли (entrypoint запускает `manage.py migrate` автоматически).

## 3) Vercel: деплой frontend

1. Импортируй проект в Vercel и укажи `Root Directory = frontend`.
2. Build settings:
   - Install: `npm install`
   - Build: `npm run build`
   - Output: `build`
3. Environment Variables:
   - `REACT_APP_API_URL=/api`
4. Задеплой.

`frontend/vercel.json` уже проксирует:
- `/api/*` -> Render backend
- `/media/*` -> Render backend

## 4) Важно: домены

Если реальные домены отличаются от шаблонных, обнови:
- `render.yaml`:
  - `DJANGO_ALLOWED_HOSTS`
  - `DJANGO_CSRF_TRUSTED_ORIGINS`
  - `CORS_ALLOWED_ORIGINS`
- `frontend/vercel.json`:
  - `destination` на фактический Render URL

## 5) Проверка после деплоя

1. Открыть фронтенд URL Vercel.
2. Войти под админом.
3. Загрузить тестовый Excel и запустить parse.
4. Проверить, что позиции сохраняются и видны в таблице.

## 6) Миграция данных из SQLite в Supabase (опционально)

Если нужно перенести текущие данные:

```bash
# Из корня проекта
./backend/venv/bin/python ./backend/manage.py dumpdata \
  --exclude contenttypes \
  --exclude auth.permission \
  > /tmp/apps-postavok-data.json

DB_ENGINE=postgresql \
DB_NAME=postgres \
DB_USER=postgres \
DB_PASSWORD='<SUPABASE_DB_PASSWORD>' \
DB_HOST='<SUPABASE_DB_HOST>' \
DB_PORT=5432 \
DB_SSLMODE=require \
./backend/venv/bin/python ./backend/manage.py loaddata /tmp/apps-postavok-data.json
```
