#!/bin/bash
# Запуск ngrok туннелей для публичного доступа

set -e

echo "🚀 Запуск ngrok туннелей"
echo ""

# Проверяем что Docker контейнеры запущены
if ! docker-compose ps | grep -q "Up"; then
    echo "⚠️  Docker контейнеры не запущены"
    echo "Запускаю docker-compose..."
    docker-compose up -d
    sleep 5
fi

# Проверяем авторизацию ngrok
if ! ngrok config check &> /dev/null; then
    echo "❌ ngrok не авторизован"
    echo "Выполните: ./scripts/setup-ngrok.sh"
    exit 1
fi

# Получаем authtoken из конфига
AUTHTOKEN=$(cat ~/.ngrok2/ngrok.yml 2>/dev/null | grep authtoken | awk '{print $2}' || echo "")

if [ -z "$AUTHTOKEN" ]; then
    echo "⚠️  Не удалось найти authtoken"
    echo "Введите ваш ngrok authtoken (можно получить на https://dashboard.ngrok.com/get-started/your-authtoken):"
    read -p "Authtoken: " AUTHTOKEN
    
    if [ -z "$AUTHTOKEN" ]; then
        echo "❌ Authtoken не может быть пустым"
        exit 1
    fi
    
    ngrok config add-authtoken "$AUTHTOKEN"
fi

# Обновляем конфигурационные файлы
if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s|YOUR_NGROK_AUTHTOKEN_HERE|$AUTHTOKEN|g" ngrok/ngrok.yml
    sed -i '' "s|YOUR_NGROK_AUTHTOKEN_HERE|$AUTHTOKEN|g" ngrok/ngrok-backend.yml
else
    sed -i "s|YOUR_NGROK_AUTHTOKEN_HERE|$AUTHTOKEN|g" ngrok/ngrok.yml
    sed -i "s|YOUR_NGROK_AUTHTOKEN_HERE|$AUTHTOKEN|g" ngrok/ngrok-backend.yml
fi

echo "✅ Конфигурация обновлена"
echo ""

# Запускаем ngrok через Docker
echo "🌐 Запуск ngrok туннелей..."
docker-compose -f docker-compose.yml -f docker-compose.ngrok.yml up -d ngrok-frontend ngrok-backend

echo ""
echo "⏳ Ожидание запуска туннелей..."
sleep 5

# Получаем URL туннелей
echo ""
echo "🔗 Публичные URL:"
echo ""

FRONTEND_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | python3 -c "import sys, json; data=json.load(sys.stdin); tunnels=[t for t in data.get('tunnels', []) if 'frontend' in t.get('name', '').lower()]; print(tunnels[0]['public_url'] if tunnels else 'Ожидание...')" 2>/dev/null || echo "Ожидание...")
BACKEND_URL=$(curl -s http://localhost:4041/api/tunnels 2>/dev/null | python3 -c "import sys, json; data=json.load(sys.stdin); tunnels=[t for t in data.get('tunnels', []) if 'backend' in t.get('name', '').lower()]; print(tunnels[0]['public_url'] if tunnels else 'Ожидание...')" 2>/dev/null || echo "Ожидание...")

echo "Frontend: $FRONTEND_URL"
echo "Backend:  $BACKEND_URL"
echo ""
echo "📊 Web интерфейсы ngrok:"
echo "  Frontend: http://localhost:4040"
echo "  Backend:  http://localhost:4041"
echo ""
echo "✅ Туннели запущены! Теперь ваш сайт доступен по публичным URL выше"
