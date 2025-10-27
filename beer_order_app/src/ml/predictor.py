"""Предсказание структуры прайс-листов."""

import pandas as pd
from typing import List, Dict
from .feature_extractor import FeatureExtractor
from .model_trainer import ModelTrainer


class Predictor:
    """Класс для предсказания структуры файлов."""

    def __init__(self, model_path: str = "data/ml_model.pkl"):
        """Инициализация предиктора.

        Args:
            model_path: Путь к обученной модели
        """
        self.trainer = ModelTrainer(model_path)
        self.is_loaded = self.trainer.load_model()

    def predict_structure(self, df: pd.DataFrame) -> List[Dict]:
        """Предсказать структуру DataFrame.

        Args:
            df: DataFrame для анализа

        Returns:
            Список словарей с категориями колонок
        """
        # Извлекаем признаки
        features = FeatureExtractor.extract_features(df)

        # Делаем предсказание, если модель обучена
        if not self.is_loaded:
            # Если модель не обучена, возвращаем базовые категории
            return [{'category': 'прочее', 'confidence': 0.0}
                    for _ in df.columns]

        predictions = self.trainer.predict(features)

        # Добавляем названия колонок к предсказаниям
        result = []
        for i, col in enumerate(df.columns):
            result.append({
                'column': col,
                'category': predictions[i]['category'],
                'confidence': predictions[i]['confidence']
            })

        return result

    def get_mapping(self, df: pd.DataFrame) -> Dict[str, str]:
        """Получить маппинг колонок на категории.

        Args:
            df: DataFrame

        Returns:
            Словарь {название_колонки: категория}
        """
        predictions = self.predict_structure(df)
        return {pred['column']: pred['category'] for pred in predictions}
