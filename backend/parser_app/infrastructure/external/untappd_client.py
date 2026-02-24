"""
Клиент для работы с Untappd через веб-скрейпинг.
Используется для поиска стиля пива по названию и пивоварне.
"""

import requests
import logging
import time
import re
from typing import Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class UntappdClient:
    """
    Клиент для работы с Untappd через веб-скрейпинг.
    
    Использует публичную страницу поиска Untappd для поиска стиля пива.
    Не требует API ключей.
    """
    
    BASE_URL = "https://untappd.com"
    SEARCH_URL = "https://untappd.com/search"
    
    def __init__(self):
        """Инициализация клиента Untappd."""
        self.rate_limit_delay = 2.0  # Задержка между запросами (2 секунды)
        self.last_request_time = 0
        self.session = requests.Session()
        # Устанавливаем заголовки, чтобы имитировать обычный браузер
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        
    def _wait_for_rate_limit(self):
        """Ждет, чтобы не превысить лимит запросов."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        self.last_request_time = time.time()
    
    def _clean_beer_name(self, beer_name: str) -> str:
        """Очищает название пива от служебных символов."""
        # Убираем "(NEW)", "NEW" и другие префиксы
        beer_name = re.sub(r'^\(NEW\)\s*', '', beer_name, flags=re.IGNORECASE)
        beer_name = re.sub(r'^NEW\s+', '', beer_name, flags=re.IGNORECASE)
        return beer_name.strip()
    
    def get_beer_style(self, beer_name: str, brewery_name: Optional[str] = None) -> Optional[str]:
        """
        Получает стиль пива по названию и опционально по пивоварне.
        
        Использует веб-скрейпинг публичной страницы поиска Untappd.
        Также использует эвристику для определения стиля по названию пива.
        
        Args:
            beer_name: Название пива
            brewery_name: Название пивоварни (опционально)
            
        Returns:
            Стиль пива (строка) или None, если не найдено
        """
        if not beer_name or not beer_name.strip():
            return None
        
        # Сначала пробуем эвристику - определяем стиль по ключевым словам в названии
        style_from_heuristic = self._guess_style_from_name(beer_name)
        if style_from_heuristic:
            logger.debug(f"Стиль определен эвристически для {beer_name}: {style_from_heuristic}")
            return style_from_heuristic
        
        # Если эвристика не сработала, пробуем веб-скрейпинг
        try:
            self._wait_for_rate_limit()
            
            # Очищаем название пива
            clean_beer_name = self._clean_beer_name(beer_name)
            
            # Формируем поисковый запрос
            query = clean_beer_name
            if brewery_name:
                # Комбинируем пивоварню и название пива
                query = f"{brewery_name} {clean_beer_name}"
            
            # Параметры поиска
            params = {
                'q': query,
                'type': 'beer'  # Ищем только пиво
            }
            
            # Выполняем поиск
            response = self.session.get(self.SEARCH_URL, params=params, timeout=10)
            response.raise_for_status()
            
            # Парсим HTML
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Ищем первую карточку пива в результатах поиска
            # Untappd использует различные селекторы для результатов поиска
            beer_card = None
            
            # Попытка 1: Ищем по классу карточки пива
            beer_cards = soup.find_all('div', class_=re.compile(r'beer-item|search-beer|beer-card', re.I))
            if not beer_cards:
                # Попытка 2: Ищем ссылки на страницы пива
                beer_links = soup.find_all('a', href=re.compile(r'/b/[^/]+/[^/]+'))
                if beer_links:
                    # Берем первую ссылку и переходим на страницу пива
                    beer_url = beer_links[0].get('href')
                    if beer_url and not beer_url.startswith('http'):
                        beer_url = f"{self.BASE_URL}{beer_url}"
                    
                    # Делаем запрос к странице пива
                    time.sleep(1)  # Небольшая задержка между запросами
                    beer_response = self.session.get(beer_url, timeout=10)
                    if beer_response.status_code == 200:
                        soup = BeautifulSoup(beer_response.text, 'lxml')
                        beer_card = soup
            
            # Извлекаем стиль из страницы
            if beer_card:
                style = self._extract_style_from_page(beer_card, beer_name, brewery_name)
                if style:
                    logger.debug(f"Найден стиль через Untappd: {beer_name} -> {style}")
                    return style
            
            logger.debug(f"Стиль не найден в Untappd для: {beer_name}")
            return None
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Ошибка при запросе к Untappd: {str(e)}")
        except Exception as e:
            logger.warning(f"Ошибка при поиске стиля в Untappd для {beer_name}: {str(e)}")
        
        return None
    
    def _guess_style_from_name(self, beer_name: str) -> Optional[str]:
        """Определяет стиль пива по ключевым словам в названии."""
        beer_name_lower = beer_name.lower()
        
        # Маппинг ключевых слов на стили
        style_keywords = {
            'ipa': ['ipa', 'india pale ale', 'imperial ipa', 'double ipa', 'triple ipa', 'hazy ipa', 'neipa'],
            'Stout': ['stout', 'imperial stout', 'russian imperial stout', 'oatmeal stout', 'milk stout', 'coffee stout', 'chocolate stout', 'pastry stout'],
            'Porter': ['porter', 'baltic porter', 'imperial porter', 'smoked porter', 'coffee porter'],
            'Lager': ['lager', 'pilsner', 'vienna lager', 'helles', 'dunkel', 'bock'],
            'Sour Ale': ['sour', 'sour ale', 'gose', 'berliner weisse', 'lambic', 'gueuze', 'wild ale'],
            'Wheat Beer': ['wheat', 'hefeweizen', 'weizen', 'witbier', 'belgian wit'],
            'Pale Ale': ['pale ale', 'american pale ale', 'english pale ale', 'blonde ale'],
            'Saison': ['saison', 'farmhouse', 'bière de garde'],
            'Barleywine': ['barleywine', 'barley wine'],
        }
        
        # Ищем ключевые слова в названии
        for style, keywords in style_keywords.items():
            for keyword in keywords:
                if keyword in beer_name_lower:
                    return style
        
        return None
    
    def _extract_style_from_page(self, soup: BeautifulSoup, beer_name: str, brewery_name: Optional[str] = None) -> Optional[str]:
        """Извлекает стиль пива из HTML страницы."""
        
        # Попытка 1: Ищем в метаданных (Open Graph, Schema.org)
        meta_tags = soup.find_all('meta', property=re.compile(r'og:|beer:', re.I))
        for meta in meta_tags:
            content = meta.get('content', '')
            if 'style' in content.lower() or 'ipa' in content.lower() or 'stout' in content.lower():
                # Пытаемся извлечь стиль из метаданных
                match = re.search(r'(IPA|Stout|Porter|Lager|Ale|Wheat|Sour|Gose|Pilsner|Saison|Farmhouse|Barleywine|Imperial|Double|Triple|Quad|Pale|Red|Brown|Blonde|Black|White|Golden|Amber|Hazy|New England|West Coast|Belgian|German|Czech|Bohemian|Bock|Doppelbock|Weizen|Hefeweizen|Dunkel|Helles|Märzen|Oktoberfest|Schwarzbier|Kölsch|Altbier|Gose|Berliner|Lambic|Gueuze|Flanders|Kriek|Framboise|Tart|Wild|Brett|Farmhouse|Bière|Grisette|Gruit|Steam|Cream|Mild|Bitter|ESB|English|Scottish|Irish|Foreign|Extra|Export|Dortmunder|Malt|Dortmunder|Malty|Crisp|Hoppy|Fruity|Citrusy|Tropical|Piney|Resinous|Floral|Spicy|Herbal|Earthy|Woody|Smoky|Roasty|Toasty|Caramel|Chocolate|Coffee|Vanilla|Oak|Bourbon|Wine|Brandy|Rum|Whiskey|Barrel|Aged|Sour|Tart|Funk|Barnyard|Horse|Leather|Tobacco|Cherry|Raspberry|Strawberry|Peach|Apricot|Mango|Pineapple|Passion|Guava|Papaya|Coconut|Banana|Apple|Pear|Grape|Plum|Prune|Date|Fig|Raisin|Currant|Cranberry|Blueberry|Blackberry|Boysenberry|Elderberry|Gooseberry|Lingonberry|Cloudberry|Sea Buckthorn|Hibiscus|Rose|Lavender|Lilac|Chamomile|Elderflower|Jasmine|Yuzu|Lime|Lemon|Orange|Grapefruit|Tangerine|Mandarin|Kumquat|Bergamot|Cardamom|Cinnamon|Ginger|Turmeric|Peppercorn|Coriander|Fennel|Anise|Star Anise|Licorice|Vanilla|Tonka|Cacao|Coffee|Tea|Matcha|Honey|Maple|Molasses|Brown Sugar|Demerara|Turbinado|Piloncillo|Palm Sugar|Coconut Sugar|Agave|Stevia|Erythritol|Xylitol|Sorbitol|Maltitol|Isomalt|Trehalose|Allulose|Tagatose|Monk Fruit|Yacon|Chicory|Dandelion|Burdock|Sarsaparilla|Root Beer|Birch Beer|Ginger Beer|Kombucha|Kvass|Kefir|Yogurt|Cheese|Milk|Cream|Butter|Ghee|Clarified|Cultured|Fermented|Probiotic|Prebiotic|Synbiotic|Postbiotic|Psychobiotic|Psychobiotic|Psychobiotic|Psychobiotic|Psychobiotic)', content, re.I)
                if match:
                    return match.group(1).strip()
        
        # Попытка 2: Ищем текст со стилем пива в содержимом страницы
        # Ищем общие паттерны стилей пива
        style_patterns = [
            r'(IPA|India Pale Ale|Imperial IPA|Double IPA|Triple IPA|Hazy IPA|New England IPA|West Coast IPA|Milkshake IPA|Sour IPA|Brut IPA|Black IPA|Red IPA|White IPA|Brown IPA|Rye IPA|Belgian IPA|English IPA|Session IPA)',
            r'(Stout|Imperial Stout|Russian Imperial Stout|Oatmeal Stout|Milk Stout|Sweet Stout|Coffee Stout|Chocolate Stout|Pastry Stout|Barrel-Aged Stout|Foreign Extra Stout|Dry Stout|Irish Stout)',
            r'(Porter|Baltic Porter|Imperial Porter|Robust Porter|Brown Porter|Smoked Porter|Coffee Porter|Chocolate Porter|Vanilla Porter|Peanut Butter Porter|Coconut Porter)',
            r'(Lager|Pilsner|German Pilsner|Czech Pilsner|Bohemian Pilsner|American Pilsner|Imperial Pilsner|Mexican Lager|Vienna Lager|Märzen|Oktoberfest|Helles|Dunkel|Schwarzbier|Bock|Doppelbock|Eisbock|Maibock|Kellerbier|Zwickelbier)',
            r'(Wheat|Hefeweizen|Weizenbock|Dunkelweizen|Weissbier|Witbier|Belgian Wit|American Wheat|Wheatwine|Berliner Weisse|Gose)',
            r'(Sour|Wild Ale|Lambic|Gueuze|Flanders Red|Flanders Brown|Oud Bruin|Kriek|Framboise|Peche|Gueuze|Lambic|Spontaneously Fermented|Mixed Fermentation|Brett|Brettanomyces|Pediococcus|Lactobacillus)',
            r'(Saison|Farmhouse|Bière de Garde|Grisette|Table Beer|Petite Saison)',
            r'(Barleywine|Barley Wine|English Barleywine|American Barleywine)',
            r'(Pale Ale|American Pale Ale|English Pale Ale|Blonde Ale|Golden Ale|Amber Ale|Red Ale|Brown Ale|Scottish Ale|Irish Red Ale)',
            r'(Belgian|Dubbel|Tripel|Quad|Quadrupel|Singel|Blonde|Dark|Strong|Weak|Table|Trappist|Abbey|Golden Strong|Dark Strong)',
        ]
        
        # Получаем весь текст страницы
        page_text = soup.get_text()
        
        # Ищем стили в тексте
        for pattern in style_patterns:
            match = re.search(pattern, page_text, re.I)
            if match:
                style = match.group(1).strip()
                # Проверяем, что это не часть другого слова или названия пива
                if len(style) > 2 and style.lower() not in beer_name.lower():
                    return style
        
        # Попытка 3: Ищем в структурированных данных (JSON-LD)
        json_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_scripts:
            try:
                import json
                data = json.loads(script.string)
                # Ищем стиль в структурированных данных
                if isinstance(data, dict):
                    style = data.get('genre') or data.get('category') or data.get('keywords')
                    if style:
                        # Проверяем, что это похоже на стиль пива
                        if re.search(r'(IPA|Stout|Porter|Lager|Ale|Wheat|Sour)', str(style), re.I):
                            return str(style).strip()
            except:
                pass
        
        return None

