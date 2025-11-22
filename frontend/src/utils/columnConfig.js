/**
 * Конфигурация колонок таблицы
 */

export const columnConfig = {
  brewery: {
    label: 'Пивоварня',
    sortable: true,
  },
  beer_name: {
    label: 'Название',
    sortable: true,
  },
  style: {
    label: 'Стиль',
    sortable: true,
  },
  abv: {
    label: 'ABV',
    sortable: true,
  },
  ibu: {
    label: 'IBU',
    sortable: true,
  },
  price: {
    label: 'Цена',
    sortable: true,
  },
  currency: {
    label: 'Валюта',
    sortable: true,
  },
  volume: {
    label: 'Объем',
    sortable: true,
  },
  format_type: {
    label: 'Формат',
    sortable: true,
  },
  stock: {
    label: 'Остаток',
    sortable: true,
  },
  description: {
    label: 'Описание',
    sortable: false,
  },
};

export function getColumnLabel(key) {
  return columnConfig[key]?.label || key;
}

export function isColumnSortable(key) {
  return columnConfig[key]?.sortable !== false;
}
