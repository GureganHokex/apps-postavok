/**
 * Компонент для отображения таблицы распарсенных позиций.
 */

import React, { useState, useEffect, useCallback, memo, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import { getFileItems, updateItem, getFileSheets } from '../api';
import { useDebounce } from '../hooks/useDebounce';
import { retry, handleApiError } from '../utils/errorHandler';
import SearchInput from './SearchInput';
import ExportButton from './ExportButton';
import './ParsedTable.css';

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
  const [activeFilters, setActiveFilters] = useState({
    brewery: '',
    beer_name: '',
    style: '',
  });
  const [searchQuery, setSearchQuery] = useState('');
  
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

  const handleCheckboxChange = (itemId, checked) => {
    if (onItemSelect) {
      onItemSelect(itemId, checked);
    }
  };

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
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="filters"
            >
              <div className="search-section">
                <SearchInput
                  placeholder="Быстрый поиск по всем полям..."
                  onSearch={(query) => {
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
                <ExportButton
                  data={items}
                  filename={`items_${selectedSheet || 'all'}_${new Date().toISOString().split('T')[0]}`}
                  formats={['csv', 'json']}
                />
              </div>
            </div>

            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th></th>
                    <th>Пивоварня</th>
                    <th>Название</th>
                    <th>Стиль</th>
                    <th>Крепость (%)</th>
                    <th>IBU</th>
                    <th>Цена</th>
                    <th>Валюта</th>
                    <th>Объём (л)</th>
                    <th>Формат</th>
                    <th>Остатки</th>
                    <th>Описание</th>
                    <th>Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {items.length === 0 ? (
                    <tr>
                      <td colSpan="13" className="empty">Нет данных</td>
                    </tr>
                  ) : (
                    items.map((item, index) => (
                      <motion.tr
                        key={item.id}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: index * 0.02 }}
                        className={editingId === item.id ? 'editing' : selectedItems.includes(item.id) ? 'selected' : ''}
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
                            <td>{item.brewery || '-'}</td>
                            <td>{item.beer_name || '-'}</td>
                            <td>{item.style || '-'}</td>
                            <td>{item.abv ? (typeof item.abv === 'number' ? item.abv.toFixed(1) : item.abv) : '-'}</td>
                            <td>{item.ibu || '-'}</td>
                            <td>{item.price ? (typeof item.price === 'number' ? item.price.toFixed(2) : item.price) : '-'}</td>
                            <td>{item.currency || 'RUB'}</td>
                            <td>{item.volume ? (typeof item.volume === 'number' ? item.volume.toFixed(2) : item.volume) : '-'}</td>
                            <td>{item.format_type || '-'}</td>
                            <td>{item.stock || '-'}</td>
                            <td className="description-cell">
                              {item.description ? (
                                <div className="description-text" title={item.description}>
                                  {item.description.length > 100 
                                    ? `${item.description.substring(0, 100)}...` 
                                    : item.description}
                                </div>
                              ) : '-'}
                            </td>
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
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}

        {sheets.length === 0 && !loading && (
          <div className="empty">Загрузка листов...</div>
        )}
      </div>
    </div>
  );
});

export default ParsedTable;

