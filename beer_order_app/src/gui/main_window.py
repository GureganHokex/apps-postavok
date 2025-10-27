"""Главное окно приложения."""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional


class MainWindow:
    """Главное окно приложения."""

    def __init__(self):
        """Инициализация главного окна."""
        self.root = tk.Tk()
        self.root.title("Менеджер прайс-листов пива")
        self.root.geometry("1000x700")

        # Данные приложения
        self.current_df = None  # Текущий DataFrame
        self.current_file_path = None  # Путь к текущему файлу
        self.order_items = []  # Позиции заказа

        # Создаем интерфейс
        self._create_menu()
        self._create_notebook()

    def _create_menu(self):
        """Создать меню приложения."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # Меню "Файл"
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(label="Выход", command=self.root.quit)

        # Меню "Справка"
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Справка", menu=help_menu)
        help_menu.add_command(label="О программе", command=self._show_about)

    def _create_notebook(self):
        """Создать вкладки приложения."""
        self.notebook = ttk.Notebook(self.root)

        # Импортируем вкладки
        from .upload_tab import UploadTab
        from .training_tab import TrainingTab
        from .order_tab import OrderTab
        from .history_tab import HistoryTab

        # Создаем вкладки
        self.upload_tab = UploadTab(self.notebook, self)
        self.training_tab = TrainingTab(self.notebook, self)
        self.order_tab = OrderTab(self.notebook, self)
        self.history_tab = HistoryTab(self.notebook, self)

        # Добавляем вкладки в notebook
        self.notebook.add(self.upload_tab, text="Загрузка файла")
        self.notebook.add(self.training_tab, text="Обучение")
        self.notebook.add(self.order_tab, text="Создание заказа")
        self.notebook.add(self.history_tab, text="История")

        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _show_about(self):
        """Показать информацию о программе."""
        about_text = (
            "Менеджер прайс-листов пива\n\n"
            "Версия: 1.0.0\n"
            "Программа для анализа прайс-листов пива\n"
            "и формирования заказов."
        )

        tk.messagebox.showinfo("О программе", about_text)

    def run(self):
        """Запустить приложение."""
        self.root.mainloop()

    def set_current_file(self, file_path: str, df):
        """Установить текущий файл.

        Args:
            file_path: Путь к файлу
            df: DataFrame с данными
        """
        self.current_file_path = file_path
        self.current_df = df

    def get_current_file(self) -> tuple[Optional[str], Optional]:
        """Получить текущий файл.

        Returns:
            Tuple (путь, DataFrame)
        """
        return self.current_file_path, self.current_df
