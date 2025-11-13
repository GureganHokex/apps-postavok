/**
 * Компонент для отображения таблицы распарсенных позиций.
 */

import React, { useState, useEffect } from 'react';
import { getFileItems, updateItem, getFileSheets } from '../api';
import './ParsedTable.css';

function ParsedTable({
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

  useEffect(() => {
    loadSheets();
  }, [fileId]);

  useEffect(() => {
    if (selectedSheet !== null) {
      loadItems();
    }
  }, [fileId, activeFilters, selectedSheet]);

  const loadSheets = async () => {
    try {
      const data = await getFileSheets(fileId);
      setSheets(data.sheets || []);
      // Автоматически выбираем первый лист
      if (data.sheets && data.sheets.length > 0 && selectedSheet === null) {
        setSelectedSheet(data.sheets[0].name);
      }
    } catch (err) {
      setError(`Ошибка загрузки листов: ${err.message}`);
    }
  };

  const loadItems = async () => {
    try {
      setLoading(true);
      const filters = { ...activeFilters };
      if (selectedSheet) {
        filters.sheet = selectedSheet;
      }
      const data = await getFileItems(fileId, filters);
      setItems(data);
      if (onItemsUpdate) {
        onItemsUpdate(data);
      }
    } catch (err) {
      setError(`Ошибка загрузки позиций: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleApplyFilters = () => {
    setActiveFilters({ ...tempFilters });
  };

  const handleClearFilters = () => {
    const clearedFilters = {
      brewery: '',
      beer_name: '',
      style: '',
    };
    setTempFilters(clearedFilters);
    setActiveFilters(clearedFilters);
  };

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

  const handleSave = async (itemId) => {
    try {
      const updatedItem = await updateItem(itemId, editData);
      setItems(items.map(item => item.id === itemId ? updatedItem : item));
      if (onItemsUpdate) {
        onItemsUpdate(items.map(item => item.id === itemId ? updatedItem : item));
      }
      setEditingId(null);
      setEditData({});
    } catch (err) {
      setError(`Ошибка сохранения: ${err.message}`);
    }
  };

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
    return <div className="loading">Загрузка позиций...</div>;
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
            <div className="filters">
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

            <div className="table-actions">
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
                    items.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <input
                            type="checkbox"
                            checked={selectedItems.includes(item.id)}
                            onChange={(e) => handleCheckboxChange(item.id, e.target.checked)}
                          />
                        </td>
                        {editingId === item.id ? (
                          <>
                            <td>
                              <input
                                type="text"
                                value={editData.brewery}
                                onChange={(e) => setEditData({ ...editData, brewery: e.target.value })}
                                className="input input-small"
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
                      </tr>
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
}

export default ParsedTable;

