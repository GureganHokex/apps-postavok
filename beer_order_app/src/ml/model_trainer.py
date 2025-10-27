"""Обучение ML модели."""

import joblib
import os
from typing import List, Dict
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from .feature_extractor import FeatureExtractor


class ModelTrainer:
    """Обучает модель для распознавания структуры прайс-листов.

    Использует Random Forest Classifier для классификации колонок.
    """

    # Категории колонок
    CATEGORIES = [
        'название_пива', 'производитель', 'тип_тары', 'объем',
        'цена', 'остаток', 'прочее'
    ]

    def __init__(self, model_path: str = "data/ml_model.pkl"):
        """Инициализация тренера модели.

        Args:
            model_path: Путь для сохранения модели
        """
        self.model_path = model_path
        self.model = RandomForestClassifier(
            n_estimators=100, random_state=42, max_depth=10
        )

    def train(self, features: List[Dict], labels: List[str]):
        """Обучить модель на размеченных данных.

        Args:
            features: Признаки (результат FeatureExtractor)
            labels: Разметка (категории для каждой колонки)

        Returns:
            Точность на тестовой выборке
        """
        # Преобразуем признаки в векторы
        X = FeatureExtractor.features_to_vector(features)

        # Преобразуем названия категорий в числа
        category_to_int = {cat: i for i, cat in enumerate(self.CATEGORIES)}
        y = [category_to_int[label] for label in labels]

        # Разделение на обучающую и тестовую выборки
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Обучение модели
        self.model.fit(X_train, y_train)

        # Оценка точности
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)

        # Сохранение модели
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(self.model, self.model_path)

        return accuracy

    def load_model(self):
        """Загрузить обученную модель.

        Returns:
            True если модель загружена успешно
        """
        if not os.path.exists(self.model_path):
            return False

        try:
            self.model = joblib.load(self.model_path)
            return True
        except:
            return False

    def predict(self, features: List[Dict]) -> List[Dict]:
        """Предсказать категории для колонок.

        Args:
            features: Признаки колонок

        Returns:
            Список словарей с категорией и уверенностью
        """
        if not hasattr(self.model, 'classes_'):
            raise ValueError("Модель не обучена. Сначала вызовите train()")

        X = FeatureExtractor.features_to_vector(features)

        # Предсказания
        predictions = self.model.predict(X)

        # Вероятности для каждого класса
        probabilities = self.model.predict_proba(X)

        # Формируем результат
        result = []
        int_to_category = {i: cat for i, cat in enumerate(self.CATEGORIES)}

        for i, pred in enumerate(predictions):
            category = int_to_category[pred]
            confidence = float(max(probabilities[i]))
            result.append({
                'category': category,
                'confidence': confidence
            })

        return result
