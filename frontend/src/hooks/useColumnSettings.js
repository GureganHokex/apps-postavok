/**
 * Хук для управления настройками колонок таблицы
 */

import { useCallback, useEffect, useMemo } from 'react';
import { useLocalStorage } from './useLocalStorage';

function isValidColumns(val) {
  return (
    Array.isArray(val) &&
    val.length > 0 &&
    val.every((c) => c && typeof c === 'object' && typeof c.key === 'string')
  );
}

function isValidVisibleKeys(val) {
  return Array.isArray(val) && val.length > 0 && val.every((k) => typeof k === 'string');
}

export function useColumnSettings(defaultColumns) {
  const defaultKeys = useMemo(() => defaultColumns.map((col) => col.key), [defaultColumns]);

  const [columnsRaw, setColumns] = useLocalStorage('tableColumns', defaultColumns);
  const [visibleRaw, setVisibleColumns] = useLocalStorage('visibleColumns', defaultKeys);

  const columns = useMemo(
    () => (isValidColumns(columnsRaw) ? columnsRaw : defaultColumns),
    [columnsRaw, defaultColumns]
  );
  const visibleColumns = useMemo(
    () => (isValidVisibleKeys(visibleRaw) ? visibleRaw : defaultKeys),
    [visibleRaw, defaultKeys]
  );

  useEffect(() => {
    if (!isValidColumns(columnsRaw) && isValidColumns(defaultColumns)) {
      setColumns(defaultColumns);
    }
  }, [columnsRaw, defaultColumns, setColumns]);

  useEffect(() => {
    if (!isValidVisibleKeys(visibleRaw) && defaultKeys.length > 0) {
      setVisibleColumns(defaultKeys);
    }
  }, [visibleRaw, defaultKeys, setVisibleColumns]);

  const toggleColumnVisibility = useCallback(
    (columnKey) => {
      setVisibleColumns((prev) => {
        const base = isValidVisibleKeys(prev) ? prev : defaultKeys;
        if (base.includes(columnKey)) {
          return base.filter((key) => key !== columnKey);
        }
        return [...base, columnKey];
      });
    },
    [setVisibleColumns, defaultKeys]
  );

  const reorderColumns = useCallback(
    (fromIndex, toIndex) => {
      setColumns((prev) => {
        const base = isValidColumns(prev) ? prev : defaultColumns;
        const newColumns = [...base];
        const [removed] = newColumns.splice(fromIndex, 1);
        newColumns.splice(toIndex, 0, removed);
        return newColumns;
      });
    },
    [setColumns, defaultColumns]
  );

  const resetColumns = useCallback(() => {
    setColumns(defaultColumns);
    setVisibleColumns(defaultKeys);
  }, [defaultColumns, defaultKeys, setColumns, setVisibleColumns]);

  const getVisibleColumns = useCallback(() => {
    return columns.filter((col) => visibleColumns.includes(col.key));
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
