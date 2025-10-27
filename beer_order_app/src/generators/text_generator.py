"""Генератор текстовых файлов заказов."""

from typing import List, Dict


class TextGenerator:
    """Генерирует текстовое представление заказа."""

    @staticmethod
    def generate(ordered_items: List[Dict]) -> str:
        """Сгенерировать текстовый заказ.

        Args:
            ordered_items: Список заказанных позиций

        Returns:
            Отформатированная текстовая строка заказа
        """
        if not ordered_items:
            return "Заказ пуст"

        lines = []
        total_amount = 0

        # Группируем по производителю
        by_brewery = {}
        for item in ordered_items:
            brewery = item.get('brewery', 'Неизвестно')
            if brewery not in by_brewery:
                by_brewery[brewery] = []

            by_brewery[brewery].append(item)
            total_amount += item.get('total', 0)

        # Формируем вывод по каждому производителю
        for brewery, items in by_brewery.items():
            lines.append(f"\n=== {brewery} ===")

            for item in items:
                beer_name = item.get('beer_name', 'н/д')
                quantity = item.get('quantity', 0)
                container = item.get('container_type', 'н/д')
                volume = item.get('volume_str', 'н/д')
                price = item.get('price', 0)

                line = (f"{beer_name} | {quantity} шт | {container} "
                        f"({volume}) | {price} руб")
                lines.append(line)

        # Итоговая сумма
        lines.append(f"\nИтого: {total_amount:.2f} руб")

        return "\n".join(lines)
