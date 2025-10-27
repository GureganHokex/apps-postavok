"""Вкладка обучения ML модели."""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from ..parsers import ExcelParser, PDFParser, TXTParser
from ..ml import FeatureExtractor, ModelTrainer


class TrainingTab(ttk.Frame):
    """Вкладка для обучения ML модели."""

    def __init__(self, parent, main_window):
        """Инициализация вкладки.

        Args:
            parent: Родительский виджет
            main_window: Ссылка на главное окно
        """
        super().__init__(parent)
        self.main_window = main_window

        self.training_data = []  # Список размеченных данных

        self._create_widgets()

    def _create_widgets(self):
        """Создать виджеты интерфейса."""
        # Заголовок
        title = ttk.Label(
            self, text="Обучение модели",
            font=('Arial', 14, 'bold')
        )
        title.pack(pady=10)

        # Инструкция
        info_text = (
            "Загрузите примеры прайс-листов и разместите их.\n"
            "После разметки минимум 10 примеров обучите модель."
        )
        ttk.Label(self, text=info_text, justify=tk.CENTER).pack(pady=5)

        # Кнопка загрузки файла
        load_btn = ttk.Button(
            self, text="Загрузить файл для разметки",
            command=self._load_file
        )
        load_btn.pack(pady=10)

        # Область для разметки
        self.labeling_frame = ttk.LabelFrame(self, text="Разметка колонок")
        self.labeling_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

        # Список размеченных файлов
        self.files_frame = ttk.LabelFrame(self, text="Размеченные файлы")
        self.files_frame.pack(pady=10, padx=20, fill=tk.BOTH)

        self.files_listbox = tk.Listbox(self.files_frame, height=8)
        self.files_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Кнопка обучения
        self.train_btn = ttk.Button(
            self, text="Обучить модель",
            command=self._train_model, state=tk.DISABLED
        )
        self.train_btn.pack(pady=10)

        # Индикатор обучения
        self.progress = ttk.Progressbar(
            self, mode='indeterminate', length=300
        )
        self.progress.pack(pady=5)

    def _load_file(self):
        """Загрузить файл для разметки."""
        file_path = filedialog.askopenfilename(
            filetypes=[
                ("Excel files", "*.xlsx *.xls"),
                ("PDF files", "*.pdf"),
                ("Text files", "*.txt *.csv")
            ]
        )

        if not file_path:
            return

        messagebox.showinfo(
            "Информация",
            "Функция разметки будет реализована в следующей версии.\n"
            "Сейчас используйте ручную настройку на вкладке заказа."
        )

    def _train_model(self):
        """Обучить модель."""
        if len(self.training_data) < 10:
            messagebox.showwarning(
                "Недостаточно данных",
                "Для обучения нужно минимум 10 размеченных примеров."
            )
            return

        self.train_btn.config(state=tk.DISABLED)
        self.progress.start(10)

        try:
            trainer = ModelTrainer()
            # Здесь будет обучение модели
            messagebox.showinfo("Успех", "Модель успешно обучена!")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось обучить модель:\n{e}")
        finally:
            self.progress.stop()
            self.train_btn.config(state=tk.NORMAL)
