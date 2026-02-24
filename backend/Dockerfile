FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=beer_app.settings

# Системные зависимости для pillow, lxml, tesseract/pdf парсеров
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
    poppler-utils \
    libtiff5 \
    libjpeg62-turbo \
    libopenjp2-7 \
    zlib1g-dev \
    libwebp-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Устанавливаем зависимости
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Копируем проект
COPY backend /app

# Статические файлы соберутся на старте (см. entrypoint.sh)
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

CMD ["bash", "/app/entrypoint.sh"]
