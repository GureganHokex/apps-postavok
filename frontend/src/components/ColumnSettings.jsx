/**
 * Компонент настроек колонок
 */

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useColumnSettings } from '../hooks/useColumnSettings';
import './ColumnSettings.css';

const columnLabels = {
  brewery: 'Пивоварня',
  beer_name: 'Название',
  style: 'Стиль',
  abv: 'Крепость',
  ibu: 'IBU',
  price: 'Цена',
  currency: 'Валюта',
  volume: 'Объём',
  format_type: 'Формат',
  stock: 'Остатки',
  description: 'Описание',
};

function ColumnSettings() {
  const { columns, visibleColumns, toggleColumn, reorderColumns, resetColumns } = useColumnSettings();

  const allColumns = Object.keys(columns).sort(
    (a, b) => columns[a].order - columns[b].order
  );

  return (
    <div className="ColumnSettings">
      <div className="column-settings-header">
        <h3>Настройка колонок</h3>
        <button
          className="button button-sm"
          onClick={resetColumns}
        >
          Сбросить
        </button>
      </div>

      <div className="column-list">
        {allColumns.map((columnKey, index) => (
          <motion.div
            key={columnKey}
            className={`column-item ${columns[columnKey].visible ? 'visible' : ''}`}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.05 }}
          >
            <label className="column-checkbox">
              <input
                type="checkbox"
                checked={columns[columnKey].visible}
                onChange={() => toggleColumn(columnKey)}
              />
              <span>{columnLabels[columnKey] || columnKey}</span>
            </label>
            <div className="column-order">
              {index > 0 && (
                <button
                  className="order-btn"
                  onClick={() => reorderColumns(index, index - 1)}
                  title="Переместить вверх"
                >
                  ↑
                </button>
              )}
              {index < allColumns.length - 1 && (
                <button
                  className="order-btn"
                  onClick={() => reorderColumns(index, index + 1)}
                  title="Переместить вниз"
                >
                  ↓
                </button>
              )}
            </div>
          </motion.div>
        ))}
      </div>

      <div className="column-info">
        Видимых колонок: {visibleColumns.length} из {allColumns.length}
      </div>
    </div>
  );
}

export default ColumnSettings;

