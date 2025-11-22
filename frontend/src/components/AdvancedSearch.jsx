/**
 * Компонент расширенного поиска
 */

import React, { useState } from 'react';
import './AdvancedSearch.css';

export function AdvancedSearch({ onSearch, onClose }) {
  const [field, setField] = useState('all');
  const [query, setQuery] = useState('');
  const [operator, setOperator] = useState('contains');

  const fields = [
    { value: 'all', label: 'Все поля' },
    { value: 'brewery', label: 'Пивоварня' },
    { value: 'beer_name', label: 'Название' },
    { value: 'style', label: 'Стиль' },
    { value: 'description', label: 'Описание' },
  ];

  const operators = [
    { value: 'contains', label: 'Содержит' },
    { value: 'equals', label: 'Равно' },
    { value: 'starts_with', label: 'Начинается с' },
    { value: 'ends_with', label: 'Заканчивается на' },
  ];

  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch({
        field: field === 'all' ? null : field,
        query: query.trim(),
        operator,
      });
    }
  };

  return (
    <div className="advanced-search">
      <div className="advanced-search-header">
        <h3>Расширенный поиск</h3>
        <button onClick={onClose} className="close-button">✕</button>
      </div>
      <form onSubmit={handleSubmit} className="advanced-search-form">
        <div className="form-group">
          <label>Поле:</label>
          <select value={field} onChange={(e) => setField(e.target.value)}>
            {fields.map(f => (
              <option key={f.value} value={f.value}>{f.label}</option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label>Оператор:</label>
          <select value={operator} onChange={(e) => setOperator(e.target.value)}>
            {operators.map(op => (
              <option key={op.value} value={op.value}>{op.label}</option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label>Запрос:</label>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Введите текст для поиска..."
            autoFocus
          />
        </div>
        <div className="form-actions">
          <button type="submit" className="button button-primary">Найти</button>
          <button type="button" onClick={onClose} className="button button-secondary">Отмена</button>
        </div>
      </form>
    </div>
  );
}

export default AdvancedSearch;
