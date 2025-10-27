"""SQLAlchemy модели для базы данных."""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

# Базовый класс для всех моделей
Base = declarative_base()


class Supplier(Base):
    """Модель поставщика.

    Хранит информацию о поставщиках прайс-листов.
    """

    __tablename__ = 'suppliers'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)  # Название поставщика
    last_file_path = Column(String(500))  # Путь к последнему файлу
    column_mapping_json = Column(Text)  # JSON с маппингом колонок
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<Supplier(id={self.id}, name='{self.name}')>"


class TrainingData(Base):
    """Модель обучающих данных.

    Хранит размеченные примеры прайс-листов для обучения ML модели.
    """

    __tablename__ = 'training_data'

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_hash = Column(String(64), unique=True, nullable=False)
    labeled_structure_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<TrainingData(id={self.id}, hash='{self.file_hash[:8]}...')>"


class Order(Base):
    """Модель заказа.

    Хранит историю созданных заказов.
    """

    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier_id = Column(Integer)  # ID поставщика (nullable)
    order_date = Column(DateTime, default=datetime.now)
    items_json = Column(Text, nullable=False)  # JSON с позициями заказа
    total_amount = Column(Float)  # Общая сумма заказа
    output_file_path = Column(String(500))  # Путь к файлу заказа

    def __repr__(self):
        return (f"<Order(id={self.id}, date={self.order_date}, "
                f"total={self.total_amount})>")


class BeerDatabase(Base):
    """Справочник сортов пива.

    Хранит информацию о известных сортах пива.
    """

    __tablename__ = 'beer_database'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)  # Название сорта
    style = Column(String(100))  # Стиль пива (IPA, Lager, Stout и т.д.)
    brewery = Column(String(200))  # Пивоварня
    keywords = Column(Text)  # Ключевые слова для поиска
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return (f"<BeerDatabase(id={self.id}, name='{self.name}', "
                f"style='{self.style}')>")
