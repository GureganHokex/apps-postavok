"""
Django settings for beer_app project.
"""

from pathlib import Path
import os
import re

# Базовая директория проекта (backend/)
BASE_DIR = Path(__file__).resolve().parent.parent

# Загрузка .env из корня репозитория (родитель backend/) и из backend/
def _load_dotenv_paths():
    try:
        from dotenv import load_dotenv
        root_env = BASE_DIR.parent / '.env'
        backend_env = BASE_DIR / '.env'
        load_dotenv(root_env)
        load_dotenv(backend_env)
        # Поддержка формата "export KEY='value'" в .env
        for p in (root_env, backend_env):
            if p.exists():
                with open(p) as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        m = re.match(r"^export\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
                        if m:
                            key, val = m.group(1), m.group(2).strip()
                            if val.startswith("'") and val.endswith("'") or val.startswith('"') and val.endswith('"'):
                                val = val[1:-1].replace('\\' + val[0], val[0])
                            os.environ.setdefault(key, val)
    except ImportError:
        pass

_load_dotenv_paths()

# Секрет и режим дебага берём из окружения
SECRET_KEY = os.getenv(
    'DJANGO_SECRET_KEY',
    'django-insecure-mvp-development-key-change-in-production',
)
DEBUG = os.getenv('DJANGO_DEBUG', 'false').lower() == 'true'

# Разрешённые хосты и доверенные источники
ALLOWED_HOSTS = [
    host for host in os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
    if host
]
# Для запросов с фронта (например localhost:3000) при пустом env задаём доверенные источники для разработки
_default_csrf_origins = os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS') or 'http://localhost:3000,http://127.0.0.1:3000'
CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in _default_csrf_origins.split(',')
    if origin.strip()
]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'parser_app.apps.ParserAppConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'beer_app.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'beer_app.wsgi.application'

# Database
DB_ENGINE = os.getenv('DB_ENGINE', 'sqlite3').lower()

if DB_ENGINE in {'postgres', 'postgresql', 'psql'}:
    db_options = {}
    db_sslmode = os.getenv('DB_SSLMODE')
    if db_sslmode:
        db_options['sslmode'] = db_sslmode

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'apps_postavok'),
            'USER': os.getenv('DB_USER', 'apps_postavok'),
            'PASSWORD': os.getenv('DB_PASSWORD', 'apps_postavok'),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
            'OPTIONS': db_options,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Настройки DRF
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ],
}

# Настройки CORS (credentials=True нужны для сессионной авторизации)
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOW_CREDENTIALS = True
else:
    _default_cors = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173,https://gureganhokex.github.io"
    _cors_origins = os.getenv("CORS_ALLOWED_ORIGINS", _default_cors)
    CORS_ALLOWED_ORIGINS = [origin.strip() for origin in _cors_origins.split(",") if origin.strip()]
    CORS_ALLOW_CREDENTIALS = True
    # Preview и прод на Vercel (*-git-*.vercel.app и т.д.) — в env не перечислить все URL.
    _cors_regex = os.getenv("CORS_ALLOWED_ORIGIN_REGEXES", "").strip()
    if _cors_regex:
        CORS_ALLOWED_ORIGIN_REGEXES = [p.strip() for p in _cors_regex.split(",") if p.strip()]
    else:
        CORS_ALLOWED_ORIGIN_REGEXES = [
            r'^https://[\w.-]+\.vercel\.app$',
        ]
CORS_EXPOSE_HEADERS = ['Content-Disposition']

# Кэширование для прогресса парсинга.
# LocMem не разделяется между процессами Gunicorn → на Render poll /parse_progress/ часто
# попадает на другой воркер и видит «not_started». В production используем БД (тот же Postgres).
if DEBUG:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
            'LOCATION': 'parse_progress_cache',
        }
    }

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'parser_app': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}

# Примечание: Интеграция с Untappd теперь использует веб-скрейпинг
# API ключи больше не требуются

# HTTPS/Proxy настройки для cloud deploy (Render/Vercel).
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'true').lower() == 'true'
    CSRF_COOKIE_SECURE = os.getenv('CSRF_COOKIE_SECURE', 'true').lower() == 'true'
    # Фронт на другом origin (Vercel) + API на Render: иначе браузер не пришлёт sessionid на XHR.
    SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'None')
    CSRF_COOKIE_SAMESITE = os.getenv('CSRF_COOKIE_SAMESITE', 'None')

# Учёт администратора (для админ-панели). В production задать ADMIN_PASSWORD в env.
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '')  # В production обязательно задать

# Strangler/feature flags для нового Excel pipeline.
EXCEL_PARSER_PIPELINE_V2 = os.getenv('EXCEL_PARSER_PIPELINE_V2', 'false').lower() == 'true'
PARSER_LEGACY_FORCE = os.getenv('PARSER_LEGACY_FORCE', 'false').lower() == 'true'
PARSER_SHADOW_MODE = os.getenv('PARSER_SHADOW_MODE', 'false').lower() == 'true'
