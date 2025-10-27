"""Вкладка создания заказа."""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from ..generators import ExcelGenerator, TextGenerator
from ..analyzers import ContainerDetector, BeerAnalyzer


class OrderTab(ttk.Frame):
    """Вкладка для создания заказа."""

    def __init__(self, parent, main_window):
        """Инициализация вкладки.

        Args:
            parent: Родительский виджет
            main_window: Ссылка на главное окно
        """
        super().__init__(parent)
        self.main_window = main_window

        self.order_items = []  # Позиции заказа

        self._create_widgets()

    def _create_widgets(self):
        """Создать виджеты интерфейса."""
        # Заголовок
        title = ttk.Label(
            self, text="Создание заказа",
            font=('Arial', 14, 'bold')
        )
        title.pack(pady=10)

        # Фильтры
        filters_frame = ttk.LabelFrame(self, text="Фильтры")
        filters_frame.pack(pady=10, padx=20, fill=tk.X)

        ttk.Label(filters_frame, text="Тип тары:").grid(row=0, column=0, padx=5)
        self.container_filter = ttk.Combobox(
            filters_frame,
            values=["Все", "Кега", "Банка", "Бутылка"]
        )
        self.container_filter.set("Все")
        self.container_filter.grid(row=0, column=1, padx=5)

        # Таблица с позициями
        self.items_frame = ttk.LabelFrame(self, text="Позиции прайс-листа")
        self.items_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

        # Создаем таблицу
        columns = ('select', 'brewery', 'beer', 'container', 'price')
        self.items_tree = ttk.Treeview(
            self.items_frame, columns=columns, show='headings', height=15
        )

        self.items_tree.heading('select', text='Выбрать')
        self.items_tree.heading('brewery', text='Пивоварня')
        self.items_tree.heading('beer', text='Пиво')
        self.items_tree.heading('container', text='Тапа (объем)')
        self.items_tree.heading('price', text='Цена')

        self.items_tree.column('select', width=60)
        self.items_tree.column('brewery', width=150)
        self.items_tree.column('beer', width=200)
        self.items_tree.column('container', width=150)
        self.items_tree.column('price', width=100)

        scrollbar = ttk.Scrollbar(
            self.items_frame, orient='vertical',
            command=self.items_tree.yview
        )
        self.items_tree.configure(yscrollcommand=scrollbar.set)

        self.items_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Кнопки
        buttons_frame = ttk.Frame(self)
        buttons_frame.pack(pady=10)

        self.create_order_btn = ttk.Button(
            buttons_frame, text="Создать заказ",
            command=self._create_order, state=tk.DISABLED
        )
        self.create_order_btn.pack(side=tk.LEFT, padx=5)

        refresh_btn = ttk.Button(
            buttons_frame, text="Обновить",
            command=self._refresh_items
        )
        refresh_btn.pack(side=tk.LEFT, padx=5)

    def _refresh_items(self):
        """Обновить список позиций."""
        file_path, df = self.main_window.get_current_file()

        if df is None:
            messagebox.showwarning(
                "Нет данных",
                "Сначала загрузите прайс-лист на вкладке 'Загрузка файла'"
            )
            return

        # Очищаем таблицу
        for item in self.items_tree.get_children():
            self.items_tree.delete(item)

        # Пока просто заполняем данными из DF
        # В реальной версии здесь будет ML распознавание структуры
        for idx, row in df.head(50).iterrows():
            beer_name = str(row.iloc[0]) if len(row) > 0 else "н/д"
            brewery = "н/д"
            container = "н/д"
            price = str(row.iloc[-1]) if len(row) > 1 else "0"

            self.items_tree.insert(
                '',
                tk.END,
                values=(False, brewery, beer_name, container, price)
            )

        self.create_order_btn.config(state=tk.NORMAL)

    def _create_order(self):
        """Создать заказ."""
        # Получаем выбранные элементы
        selected = []
        for item in self.items_tree.get_children():
            values = self.items_tree.item(item, 'values')
            if values[0]:  # Если выбрано
                selected.append(item)

        if not selected:
            messagebox.showwarning("Внимание", "Выберите позиции для заказа")
            return

        file_path, df = self.main_window.get_current_file()
        is_excel = file_path and file_path.endswith(('.xlsx', '.xls'))

        if is_excel:
            # Генерируем Excel файл
            output_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")]
            )
            if output_path:
                generator = ExcelGenerator()
                generator.generate(file_path, selected, output_path)
                messagebox.showinfo("Успех", f"Заказ сохранен в:\n{output_path}")
        else:
            # Генерируем текстовый файл
            output_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt")]
            )
            if output_path:
                with open(output_path, 'w', encoding='utf-8') as f:
                    # Здесь будет текстовый генератор
                    f.write("Заказ:\n")
                messagebox.showinfo("Успех", f"Заказ сохранен в:\n{output_path}")
