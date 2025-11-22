/**
 * Компонент расширенного поиска
 */

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import './AdvancedSearch.css';

function AdvancedSearch({ onSearch, onClose }) {
  const [searchMode, setSearchMode] = useState('simple'); // 'simple' или 'advanced'
  const [query, setQuery] = useState('');
  const [field, setField] = useState('all'); // 'all', 'brewery', 'beer_name', 'style'
  const [operator, setOperator] = useState('contains'); // 'contains', 'equals', 'starts', 'ends'
  const [savedSearches, setSavedSearches] = useState(() => {
    return JSON.parse(localStorage.getItem('saved_searches') || '[]');
  });

  const handleSearch = () => {
    if (!query.trim()) {
      toast.error('Введите поисковый запрос');
      return;
    }

    const searchParams = {
      mode: searchMode,
      query: query.trim(),
      field: field !== 'all' ? field : null,
      operator,
    };

    if (onSearch) {
      onSearch(searchParams);
    }
  };

  const handleSaveSearch = () => {
    if (!query.trim()) {
      toast.error('Введите поисковый запрос');
      return;
    }

    const searchName = prompt('Введите название для сохранения поиска:');
    if (!searchName) return;

    const savedSearch = {
      id: Date.now(),
      name: searchName,
      mode: searchMode,
      query,
      field,
      operator,
      created_at: new Date().toISOString(),
    };

    const updated = [...savedSearches, savedSearch];
    setSavedSearches(updated);
    localStorage.setItem('saved_searches', JSON.stringify(updated));
    toast.success('Поиск сохранен');
  };

  const handleLoadSearch = (savedSearch) => {
    setQuery(savedSearch.query);
    setField(savedSearch.field || 'all');
    setOperator(savedSearch.operator || 'contains');
    setSearchMode(savedSearch.mode || 'simple');
    toast.success(`Поиск "${savedSearch.name}" загружен`);
  };

  const handleDeleteSearch = (searchId) => {
    const updated = savedSearches.filter(s => s.id !== searchId);
    setSavedSearches(updated);
    localStorage.setItem('saved_searches', JSON.stringify(updated));
    toast.success('Поиск удален');
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="AdvancedSearch"
    >
      <div className="search-header">
        <h3>Расширенный поиск</h3>
        {onClose && (
          <button
            className="close-btn"
            onClick={onClose}
            aria-label="Закрыть"
          >
            ✕
          </button>
        )}
      </div>

      <div className="search-mode-toggle">
        <button
          className={`mode-btn ${searchMode === 'simple' ? 'active' : ''}`}
          onClick={() => setSearchMode('simple')}
        >
          Простой поиск
        </button>
        <button
          className={`mode-btn ${searchMode === 'advanced' ? 'active' : ''}`}
          onClick={() => setSearchMode('advanced')}
        >
          Расширенный поиск
        </button>
      </div>

      {searchMode === 'simple' ? (
        <div className="simple-search">
          <input
            type="text"
            placeholder="Введите поисковый запрос..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            className="input"
            autoFocus
          />
          <div className="search-actions">
            <button
              className="button button-primary"
              onClick={handleSearch}
            >
              Найти
            </button>
            <button
              className="button button-secondary"
              onClick={handleSaveSearch}
            >
              Сохранить поиск
            </button>
          </div>
        </div>
      ) : (
        <div className="advanced-search">
          <div className="search-field-group">
            <label>Поле поиска:</label>
            <select
              value={field}
              onChange={(e) => setField(e.target.value)}
              className="input"
            >
              <option value="all">Все поля</option>
              <option value="brewery">Пивоварня</option>
              <option value="beer_name">Название</option>
              <option value="style">Стиль</option>
              <option value="description">Описание</option>
            </select>
          </div>

          <div className="search-field-group">
            <label>Оператор:</label>
            <select
              value={operator}
              onChange={(e) => setOperator(e.target.value)}
              className="input"
            >
              <option value="contains">Содержит</option>
              <option value="equals">Равно</option>
              <option value="starts">Начинается с</option>
              <option value="ends">Заканчивается на</option>
            </select>
          </div>

          <div className="search-field-group">
            <label>Запрос:</label>
            <input
              type="text"
              placeholder="Введите поисковый запрос..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              className="input"
            />
          </div>

          <div className="search-actions">
            <button
              className="button button-primary"
              onClick={handleSearch}
            >
              Найти
            </button>
            <button
              className="button button-secondary"
              onClick={handleSaveSearch}
            >
              Сохранить поиск
            </button>
          </div>
        </div>
      )}

      {savedSearches.length > 0 && (
        <div className="saved-searches">
          <h4>Сохраненные поиски:</h4>
          <div className="saved-searches-list">
            {savedSearches.map((savedSearch) => (
              <div key={savedSearch.id} className="saved-search-item">
                <span className="search-name" onClick={() => handleLoadSearch(savedSearch)}>
                  {savedSearch.name}
                </span>
                <button
                  className="delete-btn"
                  onClick={() => handleDeleteSearch(savedSearch.id)}
                  title="Удалить"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}

export default AdvancedSearch;

