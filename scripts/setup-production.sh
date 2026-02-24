#!/bin/bash
# Скрипт для настройки production окружения

set -e

echo "🚀 Настройка production окружения для appspostavoktest.ru"
echo ""

# Проверяем наличие .env
if [ ! -f .env ]; then
    echo "📝 Создаю .env из .env.example..."
    cp .env.example .env
fi

# Генерируем секретный ключ если его нет или он дефолтный
CURRENT_KEY=$(grep "^DJANGO_SECRET_KEY=" .env | cut -d'=' -f2-)
if [ -z "$CURRENT_KEY" ] || [ "$CURRENT_KEY" = "dev-secret-key-change-in-production" ] || [ "$CURRENT_KEY" = "your-secret-key-here-change-in-production" ]; then
    echo "🔐 Генерирую новый секретный ключ..."
    NEW_KEY=$(python3 scripts/generate-secret-key.py)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$NEW_KEY|" .env
    else
        # Linux
        sed -i "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$NEW_KEY|" .env
    fi
    echo "✅ Секретный ключ обновлен"
else
    echo "✅ Секретный ключ уже установлен"
fi

# Проверяем настройки домена
echo ""
echo "📋 Текущие настройки домена:"
grep -E "(FRONTEND_DOMAIN|REACT_APP_API_URL|DJANGO_ALLOWED_HOSTS)" .env | head -3

echo ""
echo "✅ Настройка завершена!"
echo ""
echo "📝 Следующие шаги:"
echo "1. Настройте DNS записи для appspostavoktest.ru"
echo "2. Настройте SSL сертификат (см. DEPLOY_CHECKLIST.md)"
echo "3. Запустите: docker-compose up --build -d"
