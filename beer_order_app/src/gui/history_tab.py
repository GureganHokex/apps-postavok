"""Вкладка истории заказов."""

import tkinter as tk
from tkinter import ttk, messagebox


class HistoryTab(ttk.Frame):
    """Вкладка для просмотра истории заказов."""

    def __init__(self, parent, main_window):
        """Инициализация вкладки.

        Args:
            parent: Родительский виджет
            main_window: Ссылка на главное окно
        """
        super().__init__(parent)
        self.main_window = main_window

        self._create_widgets()

    def _create_widgets(self):
        """Создать виджеты интерфейса."""
        # Заголовок
        title = ttk.Label(
            self, text="История заказов",
            font=('Arial', 14, 'bold')
        )
        title.pack(pady=10)

        # Информация
        info_label = ttk.Label(
            self,
            text="История заказов будет доступна после создания заказов.\n"
                 "Функция реализуется в следующей версии."
        )
        info_label.pack(pady=20)

        # Таблица истории
        columns = ('date', 'supplier', 'total', 'file')
        self.history_tree = ttk.Treeview(
            self, columns=columns, show='headings', height=20
        )

        self.history_tree.heading('date', text='Дата')
        self.history_tree.heading('supplier', text='Поставщик')
        self.history_tree.heading('total', text='Сумма')
        self.history_tree.heading('file', text='Файл')

        self.history_tree.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    def refresh_history(self):
        """Обновить историю заказов."""
        # Очищаем таблицу
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        # Загрузка данных будет реализована позже
        # orders = database.get_all_orders()
