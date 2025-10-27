"""Вкладка загрузки файлов."""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
from ..parsers import ExcelParser, PDFParser, TXTParser


class UploadTab(ttk.Frame):
    """Вкладка для загрузки файлов."""

    def __init__(self, parent, main_window):
        """Инициализация вкладки.

        Args:
            parent: Родительский виджет
            main_window: Ссылка на главное окно
        """
        super().__init__(parent)
        self.main_window = main_window

        self.file_path = None
        self.df = None

        # Создаем интерфейс
        self._create_widgets()

    def _create_widgets(self):
        """Создать виджеты интерфейса."""
        # Заголовок
        title = ttk.Label(
            self, text="Загрузка прайс-листа",
            font=('Arial', 14, 'bold')
        )
        title.pack(pady=10)

        # Кнопка выбора файла
        select_btn = ttk.Button(
            self, text="Выбрать файл (Excel/PDF/TXT)",
            command=self._select_file
        )
        select_btn.pack(pady=5)

        # Поле для ссылки на Google Таблицы (заглушка)
        google_frame = ttk.LabelFrame(self, text="Google Таблицы")
        google_frame.pack(pady=10, padx=20, fill=tk.X)

        ttk.Label(
            google_frame,
            text="Ссылка на Google Таблицы (будет добавлено в следующей версии)"
        ).pack(pady=5)

        # Поле предпросмотра
        self.preview_frame = ttk.LabelFrame(self, text="Предпросмотр данных")
        self.preview_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

        # Таблица предпросмотра
        self.preview_tree = ttk.Treeview(
            self.preview_frame, show='headings', height=10
        )
        scrollbar_y = ttk.Scrollbar(
            self.preview_frame, orient='vertical',
            command=self.preview_tree.yview
        )
        scrollbar_x = ttk.Scrollbar(
            self.preview_frame, orient='horizontal',
            command=self.preview_tree.xview
        )

        self.preview_tree.configure(
            yscrollcommand=scrollbar_y.set,
            xscrollcommand=scrollbar_x.set
        )

        self.preview_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

        # Кнопка анализа
        self.analyze_btn = ttk.Button(
            self, text="Анализировать прайс-лист",
            command=self._analyze, state=tk.DISABLED
        )
        self.analyze_btn.pack(pady=10)

    def _select_file(self):
        """Выбрать файл для загрузки."""
        file_path = filedialog.askopenfilename(
            filetypes=[
                ("Excel files", "*.xlsx *.xls"),
                ("PDF files", "*.pdf"),
                ("Text files", "*.txt *.csv"),
                ("All files", "*.*")
            ]
        )

        if not file_path:
            return

        # Парсинг файла
        self.df = None

        try:
            if file_path.endswith(('.xlsx', '.xls')):
                parser = ExcelParser()
                self.df = parser.parse(file_path)
            elif file_path.endswith('.pdf'):
                parser = PDFParser()
                self.df = parser.parse(file_path)
            else:
                parser = TXTParser()
                self.df = parser.parse(file_path)

            self.file_path = file_path

            # Показываем предпросмотр
            self._show_preview()
            self.analyze_btn.config(state=tk.NORMAL)

        except Exception as e:
            messagebox.showerror(
                "Ошибка",
                f"Не удалось загрузить файл:\n{str(e)}"
            )

    def _show_preview(self):
        """Показать предпросмотр данных."""
        # Очищаем таблицу
        for item in self.preview_tree.get_children():
            self.preview_tree.delete(item)

        if self.df is None or self.df.empty:
            return

        # Настройка колонок
        columns = list(self.df.columns)[:10]  # Первые 10 колонок
        self.preview_tree['columns'] = columns

        for col in columns:
            self.preview_tree.heading(col, text=str(col))
            self.preview_tree.column(col, width=100)

        # Добавляем первые 20 строк
        for idx, row in self.df.head(20).iterrows():
            values = [str(val)[:50] for val in row[columns]]
            self.preview_tree.insert('', tk.END, values=values)

    def _analyze(self):
        """Анализировать прайс-лист."""
        if self.df is None:
            return

        # Передаем данные в главное окно
        self.main_window.set_current_file(self.file_path, self.df)

        messagebox.showinfo(
            "Успех",
            f"Загружено {len(self.df)} строк\n"
            f"Перейдите на вкладку 'Создание заказа'"
        )
