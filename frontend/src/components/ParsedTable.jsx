/**
 * Компонент для отображения таблицы распарсенных позиций.
 */

import React, { useState, useEffect, useCallback, memo, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import { getFileItems, updateItem, getFileSheets } from '../api';
import { useDebounce } from '../hooks/useDebounce';
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts';
import { useLocalStorage } from '../hooks/useLocalStorage';
import { useTableSort } from '../hooks/useTableSort';
import { useColumnSettings } from '../hooks/useColumnSettings';
import { retry, handleApiError } from '../utils/errorHandler';
import { columnConfig, getColumnLabel, isColumnSortable } from '../utils/columnConfig';
import { getSettings, saveSettings } from '../utils/settings';
import { SearchInput } from './SearchInput';
import AdvancedSearch from './AdvancedSearch';
import ExportButton from './ExportButton';
import BulkActions from './BulkActions';
import ContextMenu from './ContextMenu';
import { ColumnSettings } from './ColumnSettings';
import { SortableHeader } from './SortableHeader';
import { Pagination } from './Pagination';
import { SavedFilters } from './SavedFilters';
import { useTableGrouping, GroupedTableRow } from './TableGrouping';
import './ParsedTable.css';
import './ResponsiveTable.css';

const ParsedTable = memo(function ParsedTable({
  fileId,
  items: initialItems,
  onItemsUpdate,
  onItemSelect,
  selectedItems,
  onSelectAll,
  onDeselectAll,
}) {
  const [items, setItems] = useState(initialItems || []);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sheets, setSheets] = useState([]);
  const [selectedSheet, setSelectedSheet] = useState(null);
  const [tempFilters, setTempFilters] = useState({
    brewery: '',
    beer_name: '',
    style: '',
    price_min: '',
    price_max: '',
    volume_min: '',
    volume_max: '',
    abv_min: '',
    abv_max: '',
  });
  const [savedFilters, setSavedFilters] = useLocalStorage('table_filters', {
    brewery: '',
    beer_name: '',
    style: '',
    price_min: '',
    price_max: '',
    volume_min: '',
    volume_max: '',
    abv_min: '',
    abv_max: '',
  });
  const [activeFilters, setActiveFilters] = useState(savedFilters);
  const [searchQuery, setSearchQuery] = useState('');
  const [contextMenu, setContextMenu] = useState({ show: false, x: 0, y: 0, item: null });
  const [showColumnSettings, setShowColumnSettings] = useState(false);
  const [showAdvancedSearch, setShowAdvancedSearch] = useState(false);
  const [advancedSearchParams, setAdvancedSearchParams] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(25);
  const [groupBy, setGroupBy] = useState(null);
  const [expandedGroups, setExpandedGroups] = useState(new Set());
  const [showBreweryStats, setShowBreweryStats] = useState(false);
  const [showOnlyOrderedSheets, setShowOnlyOrderedSheets] = useState(false);
  const [showOnlySelected, setShowOnlySelected] = useState(false);
  const [exportOnlySelected, setExportOnlySelected] = useState(true);
  const [showWarningsOnly, setShowWarningsOnly] = useState(false);
  
  // Сортировка таблицы
  const { sortedData, sortConfig, handleSort } = useTableSort(items);
  
  // Настройки колонок
  const defaultColumns = [
    { key: 'brewery', label: 'Пивоварня' },
    { key: 'beer_name', label: 'Название' },
    { key: 'style', label: 'Стиль' },
    { key: 'abv', label: 'ABV' },
    { key: 'ibu', label: 'IBU' },
    { key: 'price', label: 'Цена' },
    { key: 'currency', label: 'Валюта' },
    { key: 'volume', label: 'Объем' },
    { key: 'format_type', label: 'Формат' },
    { key: 'stock', label: 'Остаток' },
    { key: 'description', label: 'Описание' },
  ];
  const { columns, visibleColumns, toggleColumnVisibility, reorderColumns, resetColumns, getVisibleColumns } = useColumnSettings(defaultColumns);
  
  // Сохраняем фильтры при изменении
  useEffect(() => {
    setSavedFilters(activeFilters);
  }, [activeFilters, setSavedFilters]);
  
  // Используем отсортированные данные
  const sortedItems = sortedData;

  // Опционально показываем только выбранные позиции
  const filteredSortedItems = useMemo(() => {
    const base = showOnlySelected
      ? sortedItems.filter((item) => selectedItems.includes(item.id))
      : sortedItems;
    if (!showWarningsOnly) return base;

    return base.filter((item) => {
      const missingVolume = !item.volume;
      const missingCurrency = !item.currency;
      const missingPrice = !item.price;
      return missingVolume || missingCurrency || missingPrice;
    });
  }, [sortedItems, showOnlySelected, selectedItems, showWarningsOnly]);
  
  // Группировка (если включена)
  const { groups, ungrouped } = useTableGrouping(filteredSortedItems, groupBy);
  
  // Пагинация (только для негруппированных элементов)
  // При группировке показываем все группы, но пагинируем только ungrouped элементы
  const itemsToPaginate = groupBy ? ungrouped : filteredSortedItems;
  const totalPages = groupBy ? 1 : Math.ceil(itemsToPaginate.length / itemsPerPage);
  const startIndex = groupBy ? 0 : (currentPage - 1) * itemsPerPage;
  const endIndex = groupBy ? ungrouped.length : startIndex + itemsPerPage;
  const displayItems = groupBy ? ungrouped : itemsToPaginate.slice(startIndex, endIndex);
  
  // Сбрасываем страницу при изменении фильтров или данных
  useEffect(() => {
    setCurrentPage(1);
  }, [activeFilters, sortedItems.length]);
  
  // Генерируем предложения для автодополнения из текущих данных
  const searchSuggestions = useMemo(() => {
    const suggestions = new Set();
    items.forEach(item => {
      if (item.brewery) suggestions.add(item.brewery);
      if (item.beer_name) suggestions.add(item.beer_name);
      if (item.style) suggestions.add(item.style);
    });
    return Array.from(suggestions);
  }, [items]);

  // Статистика по пивоварням
  const breweryStats = useMemo(() => {
    const breweryCounts = {};
    items.forEach(item => {
      const brewery = item.brewery || 'Не указано';
      if (!breweryCounts[brewery]) {
        breweryCounts[brewery] = {
          count: 0,
          withPrice: 0,
          avgPrice: 0,
          totalPrice: 0,
        };
      }
      breweryCounts[brewery].count += 1;
      if (item.price && parseFloat(item.price) > 0) {
        breweryCounts[brewery].withPrice += 1;
        breweryCounts[brewery].totalPrice += parseFloat(item.price);
      }
    });
    
    // Вычисляем среднюю цену для каждой пивоварни
    Object.keys(breweryCounts).forEach(brewery => {
      if (breweryCounts[brewery].withPrice > 0) {
        breweryCounts[brewery].avgPrice = 
          breweryCounts[brewery].totalPrice / breweryCounts[brewery].withPrice;
      }
    });

    return Object.entries(breweryCounts)
      .map(([name, stats]) => ({ name, ...stats }))
      .sort((a, b) => b.count - a.count);
  }, [items]);

  // Листы, в которых есть выбранные (заказанные) позиции
  const selectedSheetsSet = useMemo(() => {
    const set = new Set();
    items.forEach(item => {
      if (selectedItems.includes(item.id)) {
        const sheetName = item.raw_source_location?.sheet;
        if (sheetName) set.add(sheetName);
      }
    });
    return set;
  }, [items, selectedItems]);

  // Отображаемые листы: все или только содержащие выбранные позиции
  const visibleSheets = useMemo(() => {
    if (!showOnlyOrderedSheets) return sheets;
    return sheets.filter((sheet) => selectedSheetsSet.has(sheet.name));
  }, [sheets, showOnlyOrderedSheets, selectedSheetsSet]);

  // Если включён фильтр по заказанным листам и текущий лист вне видимых — переключаем
  useEffect(() => {
    if (!showOnlyOrderedSheets) {
      return;
    }
    const hasSelectedVisible = selectedSheet && visibleSheets.find(s => s.name === selectedSheet);
    if (!hasSelectedVisible) {
      if (visibleSheets.length > 0) {
        setSelectedSheet(visibleSheets[0].name);
      } else {
        setSelectedSheet(null);
      }
    } else if (!selectedSheet && visibleSheets.length > 0) {
      setSelectedSheet(visibleSheets[0].name);
    }
  }, [showOnlyOrderedSheets, selectedSheet, visibleSheets]);

  // Debounce фильтров для оптимизации
  const debouncedTempFilters = useDebounce(tempFilters, 500);

  const loadSheets = useCallback(async () => {
    try {
      const data = await getFileSheets(fileId);
      const sheetsList = data.sheets || [];
      setSheets(sheetsList);
      
      // Автоматически выбираем первый лист, если есть листы
      if (sheetsList.length > 0 && selectedSheet === null) {
        setSelectedSheet(sheetsList[0].name);
      } else if (sheetsList.length === 0) {
        // Если листов нет (например, PDF файл), устанавливаем флаг для загрузки позиций
        setSelectedSheet(null);
      }
    } catch (err) {
      // Если ошибка загрузки листов (например, для PDF), просто устанавливаем пустой список
      console.warn('Не удалось загрузить листы, возможно это PDF файл:', err);
      setSheets([]);
      setSelectedSheet(null);
    }
  }, [fileId, selectedSheet]);

  const loadItems = useCallback(async () => {
    if (!fileId) return;

    try {
      setLoading(true);
      setError(null);
      const filters = { ...activeFilters };
      // Добавляем фильтр по листу только если лист выбран
      if (selectedSheet) {
        filters.sheet = selectedSheet;
      }
      
      const data = await retry(
        () => getFileItems(fileId, filters),
        {
          maxRetries: 3,
          delay: 1000,
          onRetry: (attempt, maxRetries) => {
            toast.loading(`Повторная попытка загрузки ${attempt}/${maxRetries}...`, {
              id: 'load-items-retry'
            });
          }
        }
      );
      
      toast.dismiss('load-items-retry');
      
      // Обрабатываем данные - может быть массив или объект с results
      const itemsArray = Array.isArray(data) ? data : (data.results || data.items || []);
      
      setItems(itemsArray);
      if (onItemsUpdate) {
        onItemsUpdate(itemsArray);
      }
    } catch (err) {
      toast.dismiss('load-items-retry');
      handleApiError(err);
      const errorMsg = `Ошибка загрузки позиций: ${err.message}`;
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  }, [fileId, activeFilters, selectedSheet, onItemsUpdate]);

  useEffect(() => {
    if (fileId) {
      loadSheets();
    }
  }, [fileId, loadSheets]);

  useEffect(() => {
    // Если есть начальные items из пропсов, используем их
    if (initialItems && initialItems.length > 0 && items.length === 0) {
      setItems(initialItems);
      if (onItemsUpdate) {
        onItemsUpdate(initialItems);
      }
    }
  }, [initialItems, items.length, onItemsUpdate]);

  // Загружаем позиции после загрузки листов или если листов нет
  useEffect(() => {
    if (!fileId) return;
    
    // Если листы загружены и есть выбранный лист - загружаем позиции
    if (selectedSheet !== null) {
      loadItems();
    } 
    // Если листов нет (PDF файл) и еще не загружали позиции - загружаем
    else if (sheets.length === 0 && selectedSheet === null && items.length === 0 && !loading) {
      // Небольшая задержка, чтобы дать время loadSheets завершиться
      const timer = setTimeout(() => {
        if (fileId) {
          loadItems();
        }
      }, 200);
      return () => clearTimeout(timer);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fileId, activeFilters, selectedSheet, sheets.length, loadItems]);

  // Автоматически применяем фильтры после debounce
  useEffect(() => {
    if (JSON.stringify(debouncedTempFilters) !== JSON.stringify(activeFilters)) {
      setActiveFilters(debouncedTempFilters);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedTempFilters]);

  // Клавиатурные сокращения
  useKeyboardShortcuts({
    'ctrl+f': () => {
      // Фокус на поиск
      const searchInput = document.querySelector('.search-input');
      if (searchInput) searchInput.focus();
    },
    'escape': () => {
      // Закрыть контекстное меню
      if (contextMenu.show) {
        setContextMenu({ show: false, x: 0, y: 0, item: null });
      }
    },
  });

  const handleApplyFilters = useCallback(() => {
    setActiveFilters({ ...tempFilters });
    toast.success('Фильтры применены');
  }, [tempFilters]);

  const handleApplySavedFilter = useCallback((savedFilterValues) => {
    setTempFilters(savedFilterValues);
    setActiveFilters(savedFilterValues);
    toast.success('Сохраненный фильтр применен');
  }, []);

  const handleClearFilters = useCallback(() => {
    const clearedFilters = {
      brewery: '',
      beer_name: '',
      style: '',
      price_min: '',
      price_max: '',
      volume_min: '',
      volume_max: '',
      abv_min: '',
      abv_max: '',
    };
    setTempFilters(clearedFilters);
    setActiveFilters(clearedFilters);
    toast.success('Фильтры очищены');
  }, []);


  const handleCheckboxChange = useCallback((itemId, checked) => {
    if (onItemSelect) {
      onItemSelect(itemId, checked);
    }
  }, [onItemSelect]);

  // Функция рендеринга строки таблицы (используется в обычном режиме и в группировке)
  const renderTableRow = useCallback((item, index = 0) => (
    <motion.tr
      key={item.id}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: index * 0.02 }}
      className={selectedItems.includes(item.id) ? 'selected' : ''}
      onContextMenu={(e) => {
        e.preventDefault();
        setContextMenu({
          show: true,
          x: e.clientX,
          y: e.clientY,
          item: item,
        });
      }}
    >
      <td>
        <input
          type="checkbox"
          checked={selectedItems.includes(item.id)}
          onChange={(e) => handleCheckboxChange(item.id, e.target.checked)}
          aria-label={`Выбрать позицию ${item.beer_name || item.id}`}
        />
      </td>
      <>
        {getVisibleColumns().map(column => {
          const key = column.key;
          let value = item[key];
          
          if (key === 'abv' && value != null) {
            value = typeof value === 'number' ? value.toFixed(1) : value;
          } else if (key === 'price' && value != null) {
            value = typeof value === 'number' ? value.toFixed(2) : value;
          } else if (key === 'volume' && value != null) {
            value = typeof value === 'number' ? value.toFixed(2) : value;
          } else if (key === 'description') {
            return (
              <td key={key} className="description-cell">
                {value ? (
                  <div className="description-text" title={value}>
                    {value.length > 100 
                      ? `${value.substring(0, 100)}...` 
                      : value}
                  </div>
                ) : '-'}
              </td>
            );
          }
          
            return <td key={key}>{value || '-'}</td>;
        })}
      </>
    </motion.tr>
  ), [selectedItems, handleCheckboxChange, getVisibleColumns, setContextMenu]);

  const handleSelectAllChange = (e) => {
    if (e.target.checked) {
      // Добавляем все элементы текущего листа к существующим выбранным
      const currentSheetIds = items.map(item => item.id);
      const newSelectedItems = [...new Set([...selectedItems, ...currentSheetIds])];
      if (onSelectAll) {
        onSelectAll(newSelectedItems);
      }
    } else {
      // Удаляем только элементы текущего листа из выбранных
      const currentSheetIds = items.map(item => item.id);
      const newSelectedItems = selectedItems.filter(id => !currentSheetIds.includes(id));
      if (onSelectAll) {
        onSelectAll(newSelectedItems);
      }
    }
  };

  if (loading) {
    return (
      <div className="loading-container">
        <div className="loading-spinner">
          <div className="spinner-ring"></div>
          <div className="spinner-ring"></div>
          <div className="spinner-ring"></div>
        </div>
        <p>Загрузка позиций...</p>
      </div>
    );
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  return (
    <div className="ParsedTable">
      <div className="card">
        <h2>Распарсенные позиции</h2>

        {/* Вкладки листов */}
        {sheets.length > 0 && (
          <div className="sheets-tabs">
            <div className="sheets-tabs__controls">
              <label className="checkbox-inline">
                <input
                  type="checkbox"
                  checked={showOnlyOrderedSheets}
                  onChange={(e) => setShowOnlyOrderedSheets(e.target.checked)}
                />
                <span>Только листы с выбранными</span>
              </label>
              <label className="checkbox-inline">
                <input
                  type="checkbox"
                  checked={showOnlySelected}
                  onChange={(e) => {
                    setShowOnlySelected(e.target.checked);
                    setCurrentPage(1);
                  }}
                />
                <span>Показывать только выбранные позиции</span>
              </label>
              <label className="checkbox-inline">
                <input
                  type="checkbox"
                  checked={showWarningsOnly}
                  onChange={(e) => {
                    setShowWarningsOnly(e.target.checked);
                    setCurrentPage(1);
                  }}
                />
                <span>Только проблемные (нет цены/объёма/валюты)</span>
              </label>
            </div>
            <div className="sheets-tabs__list">
              {(visibleSheets.length > 0 ? visibleSheets : sheets).map((sheet) => (
                <button
                  key={sheet.name}
                  className={`sheet-tab ${selectedSheet === sheet.name ? 'active' : ''}`}
                  onClick={() => setSelectedSheet(sheet.name)}
                >
                  {sheet.name} ({sheet.count})
                </button>
              ))}
              {showOnlyOrderedSheets && visibleSheets.length === 0 && (
                <span className="sheets-tabs__empty">Нет листов с выбранными позициями</span>
              )}
            </div>
          </div>
        )}

            {(selectedSheet !== null || sheets.length === 0) && (
          <>
            <SavedFilters
              currentFilters={activeFilters}
              onApplyFilter={handleApplySavedFilter}
            />
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="filters"
            >
              <div className="search-section">
                <div className="search-input-wrapper">
                  <SearchInput
                    placeholder="Быстрый поиск по всем полям..."
                    value={searchQuery}
                    onChange={(query) => {
                      setSearchQuery(query);
                      // Автоматически применяем поиск к фильтрам
                      if (query) {
                        setTempFilters({
                          brewery: query,
                          beer_name: query,
                          style: query,
                        });
                      }
                    }}
                    suggestions={searchSuggestions}
                  />
                  <button
                    className="button button-secondary"
                    onClick={() => setShowAdvancedSearch(!showAdvancedSearch)}
                    title="Расширенный поиск"
                  >
                    🔍
                  </button>
                </div>
                {showAdvancedSearch && (
                  <AdvancedSearch
                    onSearch={(params) => {
                      setAdvancedSearchParams(params);
                      // Применяем параметры поиска
                      if (params.field) {
                        setTempFilters({
                          [params.field]: params.query,
                        });
                      } else {
                        setTempFilters({
                          brewery: params.query,
                          beer_name: params.query,
                          style: params.query,
                        });
                      }
                    }}
                    onClose={() => setShowAdvancedSearch(false)}
                  />
                )}
              </div>
              
              <div className="filter-inputs">
              <input
                type="text"
                placeholder="Фильтр по пивоварне"
                value={tempFilters.brewery}
                onChange={(e) => setTempFilters({ ...tempFilters, brewery: e.target.value })}
                className="input"
                onKeyPress={(e) => {
                  if (e.key === 'Enter') {
                    handleApplyFilters();
                  }
                }}
              />
              <input
                type="text"
                placeholder="Фильтр по названию"
                value={tempFilters.beer_name}
                onChange={(e) => setTempFilters({ ...tempFilters, beer_name: e.target.value })}
                className="input"
                onKeyPress={(e) => {
                  if (e.key === 'Enter') {
                    handleApplyFilters();
                  }
                }}
              />
              <input
                type="text"
                placeholder="Фильтр по стилю"
                value={tempFilters.style}
                onChange={(e) => setTempFilters({ ...tempFilters, style: e.target.value })}
                className="input"
                onKeyPress={(e) => {
                  if (e.key === 'Enter') {
                    handleApplyFilters();
                  }
                }}
              />
              <div className="filter-range-group">
                <label>Цена:</label>
                <input
                  type="number"
                  placeholder="Мин"
                  value={tempFilters.price_min}
                  onChange={(e) => setTempFilters({ ...tempFilters, price_min: e.target.value })}
                  className="input input-small"
                />
                <span>-</span>
                <input
                  type="number"
                  placeholder="Макс"
                  value={tempFilters.price_max}
                  onChange={(e) => setTempFilters({ ...tempFilters, price_max: e.target.value })}
                  className="input input-small"
                />
              </div>
              <div className="filter-range-group">
                <label>Объем (л):</label>
                <input
                  type="number"
                  placeholder="Мин"
                  value={tempFilters.volume_min}
                  onChange={(e) => setTempFilters({ ...tempFilters, volume_min: e.target.value })}
                  className="input input-small"
                />
                <span>-</span>
                <input
                  type="number"
                  placeholder="Макс"
                  value={tempFilters.volume_max}
                  onChange={(e) => setTempFilters({ ...tempFilters, volume_max: e.target.value })}
                  className="input input-small"
                />
              </div>
              <div className="filter-range-group">
                <label>ABV (%):</label>
                <input
                  type="number"
                  placeholder="Мин"
                  value={tempFilters.abv_min}
                  onChange={(e) => setTempFilters({ ...tempFilters, abv_min: e.target.value })}
                  className="input input-small"
                  step="0.1"
                />
                <span>-</span>
                <input
                  type="number"
                  placeholder="Макс"
                  value={tempFilters.abv_max}
                  onChange={(e) => setTempFilters({ ...tempFilters, abv_max: e.target.value })}
                  className="input input-small"
                  step="0.1"
                />
              </div>
              <button
                className="button button-primary"
                onClick={handleApplyFilters}
                disabled={loading}
              >
                Применить фильтры
              </button>
              <button
                className="button button-danger"
                onClick={handleClearFilters}
                disabled={loading}
              >
                Очистить
              </button>
            </div>
            </motion.div>

            {/* Статистика по пивоварням */}
            {items.length > 0 && (
              <div className="brewery-stats-summary">
                <button
                  className="button button-secondary"
                  onClick={() => setShowBreweryStats(!showBreweryStats)}
                  style={{ marginBottom: '10px' }}
                >
                  {showBreweryStats ? '▼' : '▶'} Статистика по пивоварням ({breweryStats.length})
                </button>
                {showBreweryStats && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="brewery-stats-table"
                  >
                    <table className="stats-table">
                      <thead>
                        <tr>
                          <th>Пивоварня</th>
                          <th>Позиций</th>
                          <th>С ценой</th>
                          <th>Средняя цена</th>
                        </tr>
                      </thead>
                      <tbody>
                        {breweryStats.slice(0, 10).map((stat, idx) => (
                          <tr key={stat.name}>
                            <td>{stat.name}</td>
                            <td>{stat.count}</td>
                            <td>{stat.withPrice}</td>
                            <td>{stat.avgPrice > 0 ? stat.avgPrice.toFixed(2) : '—'} ₽</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {breweryStats.length > 10 && (
                      <p className="stats-hint">Показано топ-10 из {breweryStats.length} пивоварен</p>
                    )}
                  </motion.div>
                )}
              </div>
            )}

            {selectedItems.length > 0 && (
              <BulkActions
                selectedItems={selectedItems}
                onSuccess={() => {
                  loadItems();
                  onDeselectAll();
                }}
                onCancel={onDeselectAll}
              />
            )}

            <div className="table-actions">
              <div className="table-actions-left">
              <label>
                <input
                  type="checkbox"
                  checked={items.length > 0 && items.every(item => selectedItems.includes(item.id))}
                  onChange={handleSelectAllChange}
                />
                Выбрать все
              </label>
              <span className="selected-count">
                Выбрано в текущем листе: {items.filter(item => selectedItems.includes(item.id)).length} из {items.length}
              </span>
              <span className="selected-count-total">
                Всего выбрано: {selectedItems.length}
              </span>
            </div>
              <div className="table-actions-right">
                <select
                  value={groupBy || ''}
                  onChange={(e) => {
                    setGroupBy(e.target.value || null);
                    setCurrentPage(1);
                    setExpandedGroups(new Set());
                  }}
                  className="input"
                  style={{ minWidth: '150px' }}
                  title="Группировать по"
                >
                  <option value="">Без группировки</option>
                  <option value="brewery">По пивоварне</option>
                  <option value="style">По стилю</option>
                  <option value="format_type">По формату</option>
                </select>
                <button
                  className="button button-secondary"
                  onClick={() => setShowColumnSettings(!showColumnSettings)}
                  title="Настройки колонок"
                >
                  ⚙️ Колонки
                </button>
                <div className="export-controls">
                  <label className="checkbox-inline">
                    <input
                      type="checkbox"
                      checked={exportOnlySelected}
                      onChange={(e) => setExportOnlySelected(e.target.checked)}
                    />
                    <span>Экспорт только выбранных</span>
                  </label>
                  <ExportButton
                    data={exportOnlySelected ? items.filter(i => selectedItems.includes(i.id)) : items}
                    filename={`items_${selectedSheet || 'all'}_${new Date().toISOString().split('T')[0]}`}
                    formats={['csv', 'json']}
                  />
                </div>
              </div>
            </div>

            {showColumnSettings && (
              <ColumnSettings
                columns={columns}
                visibleColumns={visibleColumns}
                onToggleVisibility={toggleColumnVisibility}
                onReorder={reorderColumns}
                onReset={resetColumns}
              />
            )}

            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th></th>
                    {getVisibleColumns().map(column => {
                      const config = columnConfig[column.key];
                      if (!config) return null;
                      
                      return isColumnSortable(column.key) ? (
                        <SortableHeader
                          key={column.key}
                          column={column}
                          sortConfig={sortConfig}
                          onSort={handleSort}
                        >
                          {config.label}
                        </SortableHeader>
                      ) : (
                        <th key={column.key}>{config.label}</th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {displayItems.length === 0 && (!groupBy || groups.length === 0) ? (
                    <tr>
                      <td colSpan={getVisibleColumns().length + 2} className="empty">Нет данных</td>
                    </tr>
                  ) : groupBy && groups.length > 0 ? (
                          <>
                      {groups.map((group) => {
                        const isExpanded = expandedGroups.has(group.key);
                        return (
                          <GroupedTableRow
                            key={group.key}
                            group={group}
                            isExpanded={isExpanded}
                            onToggle={() => {
                              setExpandedGroups(prev => {
                                const newSet = new Set(prev);
                                if (newSet.has(group.key)) {
                                  newSet.delete(group.key);
                                } else {
                                  newSet.add(group.key);
                                }
                                return newSet;
                              });
                            }}
                            renderRow={(item, index) => renderTableRow(item, index)}
                          />
                        );
                      })}
                      {ungrouped.length > 0 && (
                        <>
                          {ungrouped.map((item, index) => renderTableRow(item, index))}
                        </>
                      )}
                          </>
                        ) : (
                    displayItems.map((item, index) => renderTableRow(item, index))
                  )}
                </tbody>
              </table>
            </div>
            
            {sortedItems.length > 0 && !groupBy && (
              <Pagination
                currentPage={currentPage}
                totalPages={totalPages}
                onPageChange={setCurrentPage}
                itemsPerPage={itemsPerPage}
                onItemsPerPageChange={(newItemsPerPage) => {
                  setItemsPerPage(newItemsPerPage);
                  setCurrentPage(1);
                }}
              />
            )}
            {groupBy && groups.length > 0 && (
              <div className="grouping-info">
                <span>Группировка активна: {groups.length} групп, {ungrouped.length} позиций без группы</span>
              </div>
            )}
          </>
        )}

        {sheets.length === 0 && !loading && fileId && (
          <div className="empty">
            {items.length > 0 
              ? `Загружено позиций: ${items.length}` 
              : 'Загрузка позиций...'}
          </div>
        )}

        {contextMenu.show && (
          <ContextMenu
            x={contextMenu.x}
            y={contextMenu.y}
            items={[
              {
                label: selectedItems.includes(contextMenu.item.id) ? 'Снять выбор' : 'Выбрать',
                icon: selectedItems.includes(contextMenu.item.id) ? '☐' : '☑️',
                onClick: () => handleCheckboxChange(contextMenu.item.id, !selectedItems.includes(contextMenu.item.id)),
                shortcut: 'Space',
              },
              {
                label: 'Копировать название',
                icon: '📋',
                onClick: () => {
                  navigator.clipboard.writeText(contextMenu.item.beer_name || '');
                  toast.success('Название скопировано');
                },
              },
              {
                label: 'Экспортировать',
                icon: '📥',
                onClick: () => {
                  // Экспорт одной позиции
                  const exportData = [contextMenu.item];
                  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
                  const url = URL.createObjectURL(blob);
                  const link = document.createElement('a');
                  link.href = url;
                  link.download = `item_${contextMenu.item.id}.json`;
                  link.click();
                  URL.revokeObjectURL(url);
                  toast.success('Позиция экспортирована');
                },
              },
            ]}
            onClose={() => setContextMenu({ show: false, x: 0, y: 0, item: null })}
          />
        )}
      </div>
    </div>
  );
});

export default ParsedTable;

