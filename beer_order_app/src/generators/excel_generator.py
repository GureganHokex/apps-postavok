"""Генератор Excel файлов для заказов."""

import pandas as pd
import os
from datetime import datetime
from typing import List, Dict, Optional


class ExcelGenerator:
    """Генерирует Excel файл заказа на основе исходного файла."""

    @staticmethod
    def generate(source_path: str, ordered_items: List[Dict],
                 output_path: Optional[str] = None) -> str:
        """Сгенерировать файл заказа.

        Args:
            source_path: Путь к исходному Excel файлу
            ordered_items: Список заказанных позиций
            output_path: Путь для сохранения (если None - автогенерация)

        Returns:
            Путь к созданному файлу

        Raises:
            ValueError: Если не удалось создать файл
        """
        try:
            # Читаем исходный файл
            df = pd.read_excel(source_path)

            # Добавляем колонку с количеством заказа
            df['Заказано'] = 0

            # Заполняем колонку заказа
            for item in ordered_items:
                # Ищем строку по индексу или по данным
                row_idx = item.get('row_index')
                quantity = item.get('quantity', 0)

                if row_idx is not None and row_idx < len(df):
                    df.at[row_idx, 'Заказано'] = quantity

            # Фильтруем только заказанные позиции
            df_filtered = df[df['Заказано'] > 0]

            # Генерируем путь для сохранения
            if output_path is None:
                base_name = os.path.splitext(source_path)[0]
                date_str = datetime.now().strftime("%Y%m%d")
                output_path = f"{base_name}_order_{date_str}.xlsx"

            # Сохраняем в новый файл
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                df_filtered.to_excel(writer, index=False, sheet_name='Заказ')

                # Форматирование (если нужно)
                worksheet = writer.sheets['Заказ']
                worksheet.column_dimensions['A'].width = 15

                for column in worksheet.columns:
                    max_length = 0
                    column = [cell for cell in column]
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(cell.value)
                        except:
                            pass
                    adjusted_width = (max_length + 2)
                    worksheet.column_dimensions[column[0].column_letter].width = adjusted_width

            return output_path

        except Exception as e:
            raise ValueError(f"Ошибка создания Excel файла: {str(e)}")
