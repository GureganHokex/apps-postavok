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
  const [editingId, setEditingId] = useState(null);
  const [editData, setEditData] = useState({});
  const [sheets, setSheets] = useState([]);
  const [selectedSheet, setSelectedSheet] = useState(null);
  const [tempFilters, setTempFilters] = useState({
    brewery: '',
    beer_name: '',
    style: '',
  });
  const [savedFilters, setSavedFilters] = useLocalStorage('table_filters', {
    brewery: '',
    beer_name: '',
    style: '',
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
  
  // Группировка (если включена)
  const { groups, ungrouped } = useTableGrouping(sortedItems, groupBy);
  
  // Пагинация (только для негруппированных элементов)
  // При группировке показываем все группы, но пагинируем только ungrouped элементы
  const itemsToPaginate = groupBy ? ungrouped : sortedItems;
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

  // Debounce фильтров для оптимизации
  const debouncedTempFilters = useDebounce(tempFilters, 500);

  const loadSheets = useCallback(async () => {
    try {
      const data = await getFileSheets(fileId);
      setSheets(data.sheets || []);
      // Автоматически выбираем первый лист
      if (data.sheets && data.sheets.length > 0 && selectedSheet === null) {
        setSelectedSheet(data.sheets[0].name);
      }
    } catch (err) {
      const errorMsg = `Ошибка загрузки листов: ${err.message}`;
      toast.error(errorMsg);
      setError(errorMsg);
    }
  }, [fileId, selectedSheet]);

  useEffect(() => {
    loadSheets();
  }, [loadSheets]);

  useEffect(() => {
    if (selectedSheet !== null) {
      loadItems();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fileId, activeFilters, selectedSheet]);

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
    'ctrl+s': () => {
      // Сохранить текущее редактирование
      if (editingId) {
        handleSave(editingId);
      }
    },
    'escape': () => {
      // Отменить редактирование
      if (editingId) {
        handleCancel();
      }
      // Закрыть контекстное меню
      if (contextMenu.show) {
        setContextMenu({ show: false, x: 0, y: 0, item: null });
      }
    },
  });


  const loadItems = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const filters = { ...activeFilters };
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
      setItems(data);
      if (onItemsUpdate) {
        onItemsUpdate(data);
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
    };
    setTempFilters(clearedFilters);
    setActiveFilters(clearedFilters);
    toast.success('Фильтры очищены');
  }, []);

  const handleEdit = (item) => {
    setEditingId(item.id);
    setEditData({
      brewery: item.brewery || '',
      beer_name: item.beer_name || '',
      style: item.style || '',
      abv: item.abv || '',
      ibu: item.ibu || '',
      price: item.price || '',
      currency: item.currency || 'RUB',
      volume: item.volume || '',
      format_type: item.format_type || '',
      stock: item.stock || '',
      description: item.description || '',
    });
  };

  const handleSave = useCallback(async (itemId) => {
    try {
      const updatedItem = await retry(
        () => updateItem(itemId, editData),
        {
          maxRetries: 2,
          delay: 500,
        }
      );
      const updatedItems = items.map(item => item.id === itemId ? updatedItem : item);
      setItems(updatedItems);
      if (onItemsUpdate) {
        onItemsUpdate(updatedItems);
      }
      setEditingId(null);
      setEditData({});
      toast.success('Позиция успешно сохранена');
    } catch (err) {
      handleApiError(err);
      const errorMsg = `Ошибка сохранения: ${err.message}`;
      setError(errorMsg);
    }
  }, [items, editData, onItemsUpdate]);

  const handleCancel = () => {
    setEditingId(null);
    setEditData({});
  };

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
      className={editingId === item.id ? 'editing' : selectedItems.includes(item.id) ? 'selected' : ''}
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
      {editingId === item.id ? (
        <>
          <td className="editing-cell">
            <input
              type="text"
              value={editData.brewery}
              onChange={(e) => setEditData({ ...editData, brewery: e.target.value })}
              className="input input-small"
              autoFocus
            />
          </td>
          <td>
            <input
              type="text"
              value={editData.beer_name}
              onChange={(e) => setEditData({ ...editData, beer_name: e.target.value })}
              className="input input-small"
            />
          </td>
          <td>
            <input
              type="text"
              value={editData.style}
              onChange={(e) => setEditData({ ...editData, style: e.target.value })}
              className="input input-small"
            />
          </td>
          <td>
            <input
              type="number"
              step="0.1"
              value={editData.abv}
              onChange={(e) => setEditData({ ...editData, abv: e.target.value })}
              className="input input-small"
            />
          </td>
          <td>
            <input
              type="text"
              value={editData.ibu}
              onChange={(e) => setEditData({ ...editData, ibu: e.target.value })}
              className="input input-small"
            />
          </td>
          <td>
            <input
              type="number"
              step="0.01"
              value={editData.price}
              onChange={(e) => setEditData({ ...editData, price: e.target.value })}
              className="input input-small"
            />
          </td>
          <td>
            <input
              type="text"
              value={editData.currency}
              onChange={(e) => setEditData({ ...editData, currency: e.target.value })}
              className="input input-small"
            />
          </td>
          <td>
            <input
              type="number"
              step="0.01"
              value={editData.volume}
              onChange={(e) => setEditData({ ...editData, volume: e.target.value })}
              className="input input-small"
            />
          </td>
          <td>
            <input
              type="text"
              value={editData.format_type}
              onChange={(e) => setEditData({ ...editData, format_type: e.target.value })}
              className="input input-small"
            />
          </td>
          <td>
            <input
              type="text"
              value={editData.stock}
              onChange={(e) => setEditData({ ...editData, stock: e.target.value })}
              className="input input-small"
            />
          </td>
          <td>
            <textarea
              value={editData.description}
              onChange={(e) => setEditData({ ...editData, description: e.target.value })}
              className="input"
              rows="3"
              style={{minWidth: '200px'}}
            />
          </td>
          <td>
            <button
              className="button button-success"
              onClick={() => handleSave(item.id)}
            >
              Сохранить
            </button>
            <button
              className="button button-danger"
              onClick={handleCancel}
            >
              Отмена
            </button>
          </td>
        </>
      ) : (
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
          <td>
            <button
              className="button button-primary"
              onClick={() => handleEdit(item)}
            >
              Редактировать
            </button>
          </td>
        </>
      )}
    </motion.tr>
  ), [editingId, editData, selectedItems, handleCheckboxChange, handleEdit, handleSave, handleCancel, getVisibleColumns, setEditData, setContextMenu]);

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
            {sheets.map((sheet) => (
              <button
                key={sheet.name}
                className={`sheet-tab ${selectedSheet === sheet.name ? 'active' : ''}`}
                onClick={() => setSelectedSheet(sheet.name)}
              >
                {sheet.name} ({sheet.count})
              </button>
            ))}
          </div>
        )}

            {selectedSheet && (
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
                <ExportButton
                  data={items}
                  filename={`items_${selectedSheet || 'all'}_${new Date().toISOString().split('T')[0]}`}
                  formats={['csv', 'json']}
                />
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
                    <th>Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {displayItems.length === 0 && (!groupBy || groups.length === 0) ? (
                    <tr>
                      <td colSpan={getVisibleColumns().length + 3} className="empty">Нет данных</td>
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

        {sheets.length === 0 && !loading && (
          <div className="empty">Загрузка листов...</div>
        )}

        {contextMenu.show && (
          <ContextMenu
            x={contextMenu.x}
            y={contextMenu.y}
            items={[
              {
                label: 'Редактировать',
                icon: '✏️',
                onClick: () => handleEdit(contextMenu.item),
                shortcut: 'Enter',
              },
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

