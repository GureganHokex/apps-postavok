# Многоэтапная сборка для оптимизации размера образа
FROM node:18-alpine AS builder

WORKDIR /app

# Аргументы сборки для настройки API URL
ARG REACT_APP_API_URL=http://localhost:8000/api

# Копируем package.json и package-lock.json
COPY package*.json ./

# Устанавливаем зависимости
RUN npm ci --only=production=false

# Копируем исходный код
COPY . .

# Устанавливаем переменную окружения для сборки
ENV REACT_APP_API_URL=$REACT_APP_API_URL

# Собираем приложение
RUN npm run build

# Production образ с nginx
FROM nginx:alpine

# Устанавливаем envsubst для подстановки переменных
RUN apk add --no-cache gettext

# Копируем собранное приложение
COPY --from=builder /app/build /usr/share/nginx/html

# Копируем шаблон конфигурации nginx
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Скрипт для запуска nginx с подстановкой переменных
# Используем envsubst только для FRONTEND_DOMAIN, остальные переменные nginx ($uri, $host и т.д.) не заменяются
RUN echo '#!/bin/sh' > /docker-entrypoint.sh && \
    echo 'export FRONTEND_DOMAIN=${FRONTEND_DOMAIN:-localhost}' >> /docker-entrypoint.sh && \
    echo 'envsubst '"'"'${FRONTEND_DOMAIN}'"'"' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf' >> /docker-entrypoint.sh && \
    echo 'exec nginx -g "daemon off;"' >> /docker-entrypoint.sh && \
    chmod +x /docker-entrypoint.sh

# Открываем порт
EXPOSE 80

# Запускаем nginx через наш скрипт
CMD ["/docker-entrypoint.sh"]
