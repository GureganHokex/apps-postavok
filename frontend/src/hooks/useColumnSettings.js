/**
 * Хук для управления настройками колонок таблицы
 */

import { useCallback } from 'react';
import { useLocalStorage } from './useLocalStorage';

export function useColumnSettings(defaultColumns) {
  const [columns, setColumns] = useLocalStorage('tableColumns', defaultColumns);
  const [visibleColumns, setVisibleColumns] = useLocalStorage(
    'visibleColumns',
    defaultColumns.map(col => col.key)
  );

  const toggleColumnVisibility = useCallback((columnKey) => {
    setVisibleColumns(prev => {
      if (prev.includes(columnKey)) {
        return prev.filter(key => key !== columnKey);
      } else {
        return [...prev, columnKey];
      }
    });
  }, [setVisibleColumns]);

  const reorderColumns = useCallback((fromIndex, toIndex) => {
    setColumns(prev => {
      const newColumns = [...prev];
      const [removed] = newColumns.splice(fromIndex, 1);
      newColumns.splice(toIndex, 0, removed);
      return newColumns;
    });
  }, [setColumns]);

  const resetColumns = useCallback(() => {
    setColumns(defaultColumns);
    setVisibleColumns(defaultColumns.map(col => col.key));
  }, [defaultColumns, setColumns, setVisibleColumns]);

  const getVisibleColumns = useCallback(() => {
    return columns.filter(col => visibleColumns.includes(col.key));
  }, [columns, visibleColumns]);

  return {
    columns,
    visibleColumns,
    toggleColumnVisibility,
    reorderColumns,
    resetColumns,
    getVisibleColumns,
  };
}
