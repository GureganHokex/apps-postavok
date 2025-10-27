"""Менеджер базы данных.

Обеспечивает взаимодействие с SQLite базой данных.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Optional
from .models import Base, Supplier, TrainingData, Order, BeerDatabase


class DatabaseManager:
    """Менеджер для работы с базой данных.

    Управляет подключением к БД, создает сессии и предоставляет
    методы для работы с данными.
    """

    def __init__(self, db_path: str = "data/database.db"):
        """Инициализация менеджера БД.

        Args:
            db_path: Путь к файлу базы данных
        """
        # Создаем директорию для данных если её нет
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # Создаем подключение к БД
        self.db_path = db_path
        self.engine = create_engine(f'sqlite:///{db_path}')
        self.SessionLocal = sessionmaker(
            bind=self.engine, autocommit=False, autoflush=False
        )

    def initialize_database(self):
        """Инициализация базы данных.

        Создает все таблицы в БД.
        """
        Base.metadata.create_all(bind=self.engine)

    def get_session(self) -> Session:
        """Получить сессию для работы с БД.

        Returns:
            SQLAlchemy session
        """
        return self.SessionLocal()

    def add_supplier(self, name: str, file_path: Optional[str] = None,
                     column_mapping: Optional[dict] = None) -> Supplier:
        """Добавить нового поставщика.

        Args:
            name: Название поставщика
            file_path: Путь к файлу прайс-листа
            column_mapping: Маппинг колонок (словарь)

        Returns:
            Созданный объект Supplier
        """
        import json
        session = self.get_session()
        try:
            supplier = Supplier(
                name=name,
                last_file_path=file_path,
                column_mapping_json=json.dumps(column_mapping)
            )
            session.add(supplier)
            session.commit()
            session.refresh(supplier)
            return supplier
        finally:
            session.close()

    def add_training_data(self, file_hash: str,
                          labeled_structure: dict) -> TrainingData:
        """Добавить данные для обучения.

        Args:
            file_hash: Хеш файла
            labeled_structure: Словарь с размеченной структурой

        Returns:
            Созданный объект TrainingData
        """
        import json
        session = self.get_session()
        try:
            training = TrainingData(
                file_hash=file_hash,
                labeled_structure_json=json.dumps(labeled_structure)
            )
            session.add(training)
            session.commit()
            session.refresh(training)
            return training
        finally:
            session.close()

    def add_order(self, supplier_id: Optional[int], items: list,
                  total_amount: float, output_file_path: str) -> Order:
        """Добавить заказ в историю.

        Args:
            supplier_id: ID поставщика
            items: Список позиций заказа
            total_amount: Общая сумма
            output_file_path: Путь к файлу заказа

        Returns:
            Созданный объект Order
        """
        import json
        session = self.get_session()
        try:
            order = Order(
                supplier_id=supplier_id,
                items_json=json.dumps(items),
                total_amount=total_amount,
                output_file_path=output_file_path
            )
            session.add(order)
            session.commit()
            session.refresh(order)
            return order
        finally:
            session.close()

    def get_all_orders(self) -> list[Order]:
        """Получить все заказы.

        Returns:
            Список всех заказов
        """
        session = self.get_session()
        try:
            return session.query(Order).order_by(
                Order.order_date.desc()
            ).all()
        finally:
            session.close()
