/**
 * Компонент для сохранения и применения избранных фильтров
 */

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import { useLocalStorage } from '../hooks/useLocalStorage';
import './SavedFilters.css';

export function SavedFilters({ currentFilters, onApplyFilter }) {
  const [savedFilters, setSavedFilters] = useLocalStorage('saved_filters', []);
  const [showModal, setShowModal] = useState(false);
  const [filterName, setFilterName] = useState('');

  const handleSaveCurrentFilter = () => {
    if (!filterName.trim()) {
      toast.error('Введите название фильтра');
      return;
    }

    const hasValues = Object.values(currentFilters).some(val => val && val.trim());
    if (!hasValues) {
      toast.error('Нет активных фильтров для сохранения');
      return;
    }

    const newFilter = {
      id: Date.now(),
      name: filterName,
      filters: { ...currentFilters },
      created_at: new Date().toISOString(),
    };

    setSavedFilters(prev => [...prev, newFilter]);
    setFilterName('');
    setShowModal(false);
    toast.success('Фильтр сохранен');
  };

  const handleDeleteFilter = (filterId) => {
    if (window.confirm('Удалить этот фильтр?')) {
      setSavedFilters(prev => prev.filter(f => f.id !== filterId));
      toast.success('Фильтр удален');
    }
  };

  const handleApplyFilter = (filter) => {
    if (onApplyFilter) {
      onApplyFilter(filter.filters);
      toast.success(`Фильтр "${filter.name}" применен`);
    }
  };

  return (
    <div className="saved-filters">
      <div className="saved-filters-header">
        <span className="saved-filters-label">Избранные фильтры:</span>
        <button
          className="button button-secondary button-small"
          onClick={() => setShowModal(true)}
          title="Сохранить текущие фильтры"
        >
          💾 Сохранить
        </button>
      </div>

      {savedFilters.length > 0 && (
        <div className="saved-filters-list">
          <AnimatePresence>
            {savedFilters.map((filter) => (
              <motion.div
                key={filter.id}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                className="saved-filter-item"
              >
                <button
                  className="saved-filter-button"
                  onClick={() => handleApplyFilter(filter)}
                  title={`Применить: ${Object.entries(filter.filters).filter(([_, v]) => v).map(([k, v]) => `${k}: ${v}`).join(', ')}`}
                >
                  {filter.name}
                </button>
                <button
                  className="saved-filter-delete"
                  onClick={() => handleDeleteFilter(filter.id)}
                  title="Удалить фильтр"
                >
                  ✕
                </button>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}

      {showModal && (
        <div className="saved-filters-modal-overlay" onClick={() => setShowModal(false)}>
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="saved-filters-modal"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <h3>Сохранить фильтр</h3>
              <button onClick={() => setShowModal(false)}>✕</button>
            </div>
            <div className="modal-content">
              <input
                type="text"
                placeholder="Название фильтра (например: IPA от 300₽)"
                value={filterName}
                onChange={(e) => setFilterName(e.target.value)}
                className="input"
                autoFocus
                onKeyPress={(e) => {
                  if (e.key === 'Enter') {
                    handleSaveCurrentFilter();
                  }
                }}
              />
              <div className="current-filters-preview">
                <strong>Текущие фильтры:</strong>
                <ul>
                  {Object.entries(currentFilters).map(([key, value]) => (
                    value && value.trim() && (
                      <li key={key}>
                        <strong>{key}:</strong> {value}
                      </li>
                    )
                  ))}
                </ul>
              </div>
            </div>
            <div className="modal-actions">
              <button
                className="button button-primary"
                onClick={handleSaveCurrentFilter}
                disabled={!filterName.trim()}
              >
                Сохранить
              </button>
              <button
                className="button button-secondary"
                onClick={() => {
                  setShowModal(false);
                  setFilterName('');
                }}
              >
                Отмена
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  );
}

export default SavedFilters;

