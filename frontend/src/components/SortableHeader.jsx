/**
 * Компонент сортируемого заголовка таблицы
 */

import React from 'react';
import './SortableHeader.css';

export function SortableHeader({ column, sortConfig, onSort, children }) {
  const isSortable = column.sortable !== false;
  const isSorted = sortConfig && sortConfig.key === column.key;
  const sortDirection = isSorted ? sortConfig.direction : null;

  const handleClick = () => {
    if (isSortable && onSort) {
      onSort(column.key);
    }
  };

  return (
    <th
      className={`sortable-header ${isSortable ? 'sortable' : ''} ${isSorted ? `sorted-${sortDirection}` : ''}`}
      onClick={handleClick}
    >
      <div className="header-content">
        <span>{children}</span>
        {isSortable && (
          <span className="sort-indicator">
            {sortDirection === 'asc' && '↑'}
            {sortDirection === 'desc' && '↓'}
            {!sortDirection && '⇅'}
          </span>
        )}
      </div>
    </th>
  );
}
