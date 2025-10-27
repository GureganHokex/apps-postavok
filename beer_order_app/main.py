"""Точка входа в приложение."""

import sys
import os

# Добавляем путь к модулям
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.database.db_manager import DatabaseManager
from src.gui.main_window import MainWindow


def main():
    """Главная функция приложения."""
    # Инициализация базы данных
    db_manager = DatabaseManager()
    db_manager.initialize_database()

    # Создание и запуск GUI
    app = MainWindow()
    app.run()


if __name__ == "__main__":
    main()
