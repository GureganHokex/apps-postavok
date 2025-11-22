/**
 * Виртуализированная таблица для больших списков
 */

import React, { useRef, useMemo } from 'react';
import { FixedSizeList as List } from 'react-window';
import './VirtualizedTable.css';

function VirtualizedTable({ 
  columns, 
  data, 
  rowHeight = 50,
  headerHeight = 50,
  onRowClick,
  selectedRows = []
}) {
  const listRef = useRef(null);
  
  const Row = ({ index, style }) => {
    const row = data[index];
    const isSelected = selectedRows.includes(row.id);
    
    return (
      <div
        style={style}
        className={`virtualized-row ${isSelected ? 'selected' : ''}`}
        onClick={() => onRowClick && onRowClick(row, index)}
      >
        {columns.map((column, colIndex) => (
          <div
            key={colIndex}
            className="virtualized-cell"
            style={{ width: column.width || 'auto', flex: column.flex || 'none' }}
          >
            {column.render ? column.render(row, index) : row[column.key]}
          </div>
        ))}
      </div>
    );
  };

  const Header = () => (
    <div className="virtualized-header">
      {columns.map((column, colIndex) => (
        <div
          key={colIndex}
          className="virtualized-header-cell"
          style={{ width: column.width || 'auto', flex: column.flex || 'none' }}
        >
          {column.header}
        </div>
      ))}
    </div>
  );

  return (
    <div className="virtualized-table-container">
      <Header />
      <List
        ref={listRef}
        height={600}
        itemCount={data.length}
        itemSize={rowHeight}
        width="100%"
      >
        {Row}
      </List>
    </div>
  );
}

export default VirtualizedTable;

