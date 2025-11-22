/**
 * Конфигурация колонок таблицы
 */

export const columnConfig = {
  brewery: { key: 'brewery', label: 'Пивоварня', sortable: true },
  beer_name: { key: 'beer_name', label: 'Название', sortable: true },
  style: { key: 'style', label: 'Стиль', sortable: true },
  abv: { key: 'abv', label: 'Крепость (%)', sortable: true },
  ibu: { key: 'ibu', label: 'IBU', sortable: true },
  price: { key: 'price', label: 'Цена', sortable: true },
  currency: { key: 'currency', label: 'Валюта', sortable: true },
  volume: { key: 'volume', label: 'Объём (л)', sortable: true },
  format_type: { key: 'format_type', label: 'Формат', sortable: true },
  stock: { key: 'stock', label: 'Остатки', sortable: true },
  description: { key: 'description', label: 'Описание', sortable: false },
};

export function getColumnLabel(key) {
  return columnConfig[key]?.label || key;
}

export function isColumnSortable(key) {
  return columnConfig[key]?.sortable || false;
}

