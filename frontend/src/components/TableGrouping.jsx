/**
 * Компонент для группировки строк в таблице
 */

import React, { useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import './TableGrouping.css';

export function useTableGrouping(data, groupBy) {
  const groupedData = useMemo(() => {
    const rows = Array.isArray(data) ? data : [];
    if (!groupBy || rows.length === 0) {
      return { groups: [], ungrouped: rows };
    }

    const groups = {};
    const ungrouped = [];

    rows.forEach(item => {
      const groupValue = item[groupBy];
      if (groupValue && groupValue !== '-' && groupValue !== '') {
        if (!groups[groupValue]) {
          groups[groupValue] = [];
        }
        groups[groupValue].push(item);
      } else {
        ungrouped.push(item);
      }
    });

    const groupArray = Object.entries(groups).map(([key, items]) => ({
      key,
      label: key,
      items,
      count: items.length,
    })).sort((a, b) => b.count - a.count);

    return { groups: groupArray, ungrouped };
  }, [data, groupBy]);

  return groupedData;
}

export function GroupedTableRow({ group, isExpanded, onToggle, renderRow }) {
  return (
    <>
      <motion.tr
        className="group-header-row"
        onClick={onToggle}
        whileHover={{ backgroundColor: 'var(--bg-hover, rgba(0, 0, 0, 0.05))' }}
      >
        <td colSpan="100%" className="group-header-cell">
          <div className="group-header-content">
            <span className="group-toggle-icon">{isExpanded ? '▼' : '▶'}</span>
            <span className="group-label">{group.label}</span>
            <span className="group-count">({group.count} позиций)</span>
          </div>
        </td>
      </motion.tr>
      {isExpanded && (
        <AnimatePresence>
          {group.items.map((item, index) => (
            <motion.tr
              key={item.id || index}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0 }}
              transition={{ delay: index * 0.02 }}
              className="group-item-row"
            >
              {renderRow(item)}
            </motion.tr>
          ))}
        </AnimatePresence>
      )}
    </>
  );
}

export default useTableGrouping;

