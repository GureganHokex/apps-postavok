#!/bin/bash
# Скрипт для проверки статуса деплоя

echo "🔍 Проверка статуса деплоя appspostavoktest.ru"
echo ""

# Проверка Docker
echo "📦 Docker контейнеры:"
docker-compose ps
echo ""

# Проверка Backend
echo "🔌 Backend API:"
if curl -s http://localhost:8000/api/ > /dev/null 2>&1; then
    echo "✅ Backend доступен: http://localhost:8000/api/"
    curl -s http://localhost:8000/api/ | head -1
else
    echo "❌ Backend недоступен"
fi
echo ""

# Проверка Frontend
echo "🌐 Frontend:"
if curl -s http://localhost/health > /dev/null 2>&1; then
    echo "✅ Frontend доступен: http://localhost"
    curl -s http://localhost/health
else
    echo "❌ Frontend недоступен"
fi
echo ""

# Проверка DNS (если домен настроен)
echo "🌍 DNS проверка:"
if command -v dig &> /dev/null; then
    DNS_IP=$(dig +short appspostavoktest.ru)
    if [ -n "$DNS_IP" ]; then
        echo "✅ DNS резолвится: appspostavoktest.ru -> $DNS_IP"
    else
        echo "⚠️  DNS не настроен или еще не распространился"
    fi
else
    echo "ℹ️  dig не установлен, пропускаем DNS проверку"
fi
echo ""

# Проверка SSL (если настроен)
echo "🔒 SSL проверка:"
if curl -s https://appspostavoktest.ru/health > /dev/null 2>&1; then
    echo "✅ HTTPS доступен: https://appspostavoktest.ru"
else
    echo "⚠️  HTTPS не настроен (это нормально если SSL еще не настроен)"
fi
echo ""

echo "✅ Проверка завершена"
