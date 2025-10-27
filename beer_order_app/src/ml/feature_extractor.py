"""Извлечение признаков для ML модели."""

import pandas as pd
import re
from typing import List, Dict


class FeatureExtractor:
    """Извлекает признаки из колонок таблицы.

    Для каждой колонки создает вектор признаков
    для классификации в ML модели.
    """

    # Ключевые слова для разных типов колонок
    KEYWORDS = {
        'название': ['название', 'name', 'пиво', 'товар', 'продукт',
                     'beer', 'product'],
        'производитель': ['пивоварня', 'производитель', 'brewery',
                          'manufacturer', 'brand', 'бренд'],
        'тара': ['тара', 'container', 'упаковка', 'package', 'type', 'тип'],
        'кег': ['кег', 'keg', 'кега', 'кеги'],
        'объем': ['объем', 'volume', 'лит', 'л', 'ml', 'мл'],
        'цена': ['цена', 'price', 'стоим', 'cost', 'руб', 'rur'],
        'остаток': ['остаток', 'stock', 'количество', 'quantity', 'шт', 'pcs']
    }

    @staticmethod
    def extract_features(df: pd.DataFrame) -> List[Dict]:
        """Извлечь признаки из всех колонок DataFrame.

        Args:
            df: DataFrame с данными

        Returns:
            Список словарей с признаками для каждой колонки
        """
        features = []

        for col in df.columns:
            col_features = FeatureExtractor._extract_column_features(
                df[col], col
            )
            features.append(col_features)

        return features

    @staticmethod
    def _extract_column_features(series: pd.Series,
                                  column_name: str) -> Dict:
        """Извлечь признаки из одной колонки.

        Args:
            series: Серия данных (колонка)
            column_name: Название колонки

        Returns:
            Словарь с признаками
        """
        col_lower = str(column_name).lower()

        # Базовые признаки
        features = {
            'is_numeric': FeatureExtractor._is_numeric(series),
            'is_text': FeatureExtractor._is_text(series),
            'is_date': FeatureExtractor._is_date(series),
            'unique_ratio': len(series.unique()) / len(series) if len(series) > 0 else 0,
            'has_null': series.isna().any(),
            'null_ratio': series.isna().sum() / len(series) if len(series) > 0 else 0,
        }

        # Признаки на основе ключевых слов в названии колонки
        for category, keywords in FeatureExtractor.KEYWORDS.items():
            features[f'has_keyword_{category}'] = any(
                keyword in col_lower for keyword in keywords
            )

        # Статистические признаки для числовых колонок
        if features['is_numeric']:
            features['min'] = series.min()
            features['max'] = series.max()
            features['mean'] = series.mean()
            features['std'] = series.std()
        else:
            features['min'] = 0
            features['max'] = 0
            features['mean'] = 0
            features['std'] = 0

        # Признаки для текстовых колонок
        if features['is_text']:
            avg_length = series.astype(str).apply(len).mean()
            features['avg_text_length'] = avg_length
            features['has_beer_keywords'] = any(
                'пиво' in str(val).lower() or 'beer' in str(val).lower()
                for val in series.head(5)
            )
        else:
            features['avg_text_length'] = 0
            features['has_beer_keywords'] = False

        return features

    @staticmethod
    def _is_numeric(series: pd.Series) -> bool:
        """Проверить, является ли колонка числовой.

        Args:
            series: Серия данных

        Returns:
            True если колонка числовая
        """
        try:
            pd.to_numeric(series.dropna())
            return True
        except:
            return False

    @staticmethod
    def _is_text(series: pd.Series) -> bool:
        """Проверить, является ли колонка текстовой.

        Args:
            series: Серия данных

        Returns:
            True если колонка текстовая
        """
        return series.dtype == 'object'

    @staticmethod
    def _is_date(series: pd.Series) -> bool:
        """Проверить, является ли колонка датой.

        Args:
            series: Серия данных

        Returns:
            True если колонка дата
        """
        try:
            pd.to_datetime(series.dropna())
            return True
        except:
            return False

    @staticmethod
    def features_to_vector(features: List[Dict]) -> List[List[float]]:
        """Преобразовать признаки в вектор для ML модели.

        Args:
            features: Список словарей с признаками

        Returns:
            Список векторов признаков
        """
        vectors = []

        # Порядок признаков (фиксированный)
        feature_order = [
            'is_numeric', 'is_text', 'is_date', 'unique_ratio',
            'has_null', 'null_ratio', 'has_keyword_название',
            'has_keyword_производитель', 'has_keyword_тара',
            'has_keyword_кег', 'has_keyword_объем', 'has_keyword_цена',
            'has_keyword_остаток', 'min', 'max', 'mean', 'std',
            'avg_text_length', 'has_beer_keywords'
        ]

        for feat_dict in features:
            vector = [feat_dict.get(f, 0) for f in feature_order]
            # Булевы значения преобразуем в float
            vector = [float(v) if isinstance(v, bool) else v for v in vector]
            vectors.append(vector)

        return vectors
