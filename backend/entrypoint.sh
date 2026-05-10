#!/usr/bin/env bash
set -euo pipefail

# Запускаем миграции и сбор статических файлов перед стартом
python manage.py migrate --noinput
# Таблица для DatabaseCache (production); при LocMem в DEBUG команда просто не создаст лишнего.
python manage.py createcachetable || true
# Создаёт/обновляет админа из ADMIN_USERNAME + ADMIN_PASSWORD (секреты только в env, не в git).
if [ -n "${ADMIN_PASSWORD:-}" ]; then
  python manage.py create_admin_user
fi
python manage.py collectstatic --noinput

# Gunicorn: 2 воркера — GET parse_progress и остальной API, пока другой воркер занят фоновым парсингом (после 202 на POST /parse/).
# При OOM верни GUNICORN_WORKERS=1 в env Render. На платном плане можно 3.
# Таймаут большой: фоновый парсинг большого Excel может идти минуты внутри воркера.
exec gunicorn beer_app.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${GUNICORN_WORKERS:-2}" \
  --timeout "${GUNICORN_TIMEOUT:-1200}" \
  --graceful-timeout 120 \
  --max-requests 200 \
  --max-requests-jitter 50
