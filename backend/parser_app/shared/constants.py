"""
Константы для приложения парсинга прайсов.
"""

# Валидация данных
MIN_PRICE = 0
MAX_PRICE = 100000  # 100000 рублей максимум
MIN_VOLUME = 0
MAX_VOLUME = 100  # 100 литров максимум
MIN_ABV = 0
MAX_ABV = 20  # 20% максимум крепости

# Кэширование
CACHE_TIMEOUT_PARSE_PROGRESS = 600  # 10 минут
CACHE_TIMEOUT_COMPLETED = 60  # 1 минута после завершения

# Пакетная обработка
BULK_CREATE_BATCH_SIZE = 100
PROGRESS_UPDATE_INTERVAL = 10  # Обновлять прогресс каждые N позиций

# Служебные строки для очистки числовых полей
EMPTY_VALUE_STRINGS = [
    '', '-', '—', '–', 'nan', 'none', 'null', 'n/a', 'na', 
    'хх', 'xx', 'н/д', 'н.д.'
]

# Эвристика для определения стиля пива
BEER_STYLE_KEYWORDS = {
    'berliner_weisse': ['берлинер вайссе', 'berliner weisse'],
    'gose': ['гозэ', 'гозе', 'gose'],
    'sour_ale': ['саур', 'sour'],
    'stout': ['стаут', 'stout'],
    'imperial_stout': ['имперский стаут', 'imperial stout'],
    'porter': ['портер', 'porter'],
    'ipa': ['ипа', 'ipa'],
    'lager': ['лагер', 'lager'],
    'pale_ale': ['пале эль', 'pale ale'],
    'ale': ['эль', 'ale'],
}

BEER_STYLE_MAPPING = {
    'berliner_weisse': 'Berliner Weisse',
    'gose': 'Gose',
    'sour_ale': 'Sour Ale',
    'stout': 'Stout',
    'imperial_stout': 'Imperial Stout',
    'porter': 'Porter',
    'ipa': 'IPA',
    'lager': 'Lager',
    'pale_ale': 'Pale Ale',
    'ale': 'Ale',
}
