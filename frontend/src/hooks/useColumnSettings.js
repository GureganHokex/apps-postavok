/**
 * Хук для управления настройками колонок
 */

import { useLocalStorage } from './useLocalStorage';

const defaultColumns = {
  brewery: { visible: true, order: 0 },
  beer_name: { visible: true, order: 1 },
  style: { visible: true, order: 2 },
  abv: { visible: true, order: 3 },
  ibu: { visible: true, order: 4 },
  price: { visible: true, order: 5 },
  currency: { visible: true, order: 6 },
  volume: { visible: true, order: 7 },
  format_type: { visible: true, order: 8 },
  stock: { visible: true, order: 9 },
  description: { visible: true, order: 10 },
};

export function useColumnSettings(storageKey = 'table_columns') {
  const [columns, setColumns] = useLocalStorage(storageKey, defaultColumns);

  const toggleColumn = (columnKey) => {
    setColumns(prev => ({
      ...prev,
      [columnKey]: {
        ...prev[columnKey],
        visible: !prev[columnKey]?.visible,
      },
    }));
  };

  const reorderColumns = (fromIndex, toIndex) => {
    const columnKeys = Object.keys(columns).sort(
      (a, b) => columns[a].order - columns[b].order
    );
    
    const [removed] = columnKeys.splice(fromIndex, 1);
    columnKeys.splice(toIndex, 0, removed);

    setColumns(prev => {
      const newColumns = { ...prev };
      columnKeys.forEach((key, index) => {
        newColumns[key] = {
          ...newColumns[key],
          order: index,
        };
      });
      return newColumns;
    });
  };

  const resetColumns = () => {
    setColumns(defaultColumns);
  };

  const visibleColumns = Object.keys(columns)
    .filter(key => columns[key].visible)
    .sort((a, b) => columns[a].order - columns[b].order);

  return {
    columns,
    visibleColumns,
    toggleColumn,
    reorderColumns,
    resetColumns,
  };
}

