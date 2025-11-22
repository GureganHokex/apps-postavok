/**
 * Компонент настроек колонок таблицы
 */

import React, { useState } from 'react';
import './ColumnSettings.css';

export function ColumnSettings({ columns, visibleColumns, onToggleVisibility, onReorder, onReset }) {
  const [isOpen, setIsOpen] = useState(false);

  const handleDragStart = (e, index) => {
    e.dataTransfer.setData('text/plain', index);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleDrop = (e, dropIndex) => {
    e.preventDefault();
    const dragIndex = parseInt(e.dataTransfer.getData('text/plain'));
    if (dragIndex !== dropIndex && onReorder) {
      onReorder(dragIndex, dropIndex);
    }
  };

  return (
    <>
      <div className="column-settings">
        <button
          className="column-settings-toggle"
          onClick={() => setIsOpen(!isOpen)}
          title="Настройки колонок"
        >
          ⚙️
        </button>
      </div>
      {isOpen && (
        <>
          <div className="column-settings-overlay" onClick={() => setIsOpen(false)} />
          <div className="column-settings-panel">
            <div className="panel-header">
              <h3>Настройки колонок</h3>
              <button onClick={() => setIsOpen(false)}>✕</button>
            </div>
            <div className="panel-content">
              <div className="columns-list">
                {columns.map((col, index) => (
                  <div
                    key={col.key}
                    className="column-item"
                    draggable
                    onDragStart={(e) => handleDragStart(e, index)}
                    onDragOver={handleDragOver}
                    onDrop={(e) => handleDrop(e, index)}
                  >
                    <label>
                      <input
                        type="checkbox"
                        checked={visibleColumns.includes(col.key)}
                        onChange={() => onToggleVisibility(col.key)}
                      />
                      <span>{col.label || col.key}</span>
                    </label>
                  </div>
                ))}
              </div>
              <div className="panel-actions">
                <button onClick={onReset}>Сбросить</button>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
}
