/**
 * Компонент сортируемого заголовка таблицы
 */

import React from 'react';
import { motion } from 'framer-motion';
import './SortableHeader.css';

function SortableHeader({ columnKey, label, sortConfig, onSort, children }) {
  const isSorted = sortConfig && sortConfig.key === columnKey;
  const sortDirection = isSorted ? sortConfig.direction : null;

  return (
    <th
      className={`sortable-header ${isSorted ? 'sorted' : ''}`}
      onClick={() => onSort(columnKey)}
    >
      <div className="header-content">
        {children || label}
        <motion.span
          className="sort-indicator"
          initial={false}
          animate={{
            opacity: isSorted ? 1 : 0.3,
            rotate: sortDirection === 'desc' ? 180 : 0,
          }}
        >
          {sortDirection === 'asc' ? '↑' : sortDirection === 'desc' ? '↓' : '⇅'}
        </motion.span>
      </div>
    </th>
  );
}

export default SortableHeader;

