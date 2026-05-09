#!/usr/bin/env bash
set -euo pipefail

# Запускаем миграции и сбор статических файлов перед стартом
python manage.py migrate --noinput
# Создаёт/обновляет админа из ADMIN_USERNAME + ADMIN_PASSWORD (секреты только в env, не в git).
if [ -n "${ADMIN_PASSWORD:-}" ]; then
  python manage.py create_admin_user
fi
python manage.py collectstatic --noinput

# Стартуем gunicorn
exec gunicorn beer_app.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 3
