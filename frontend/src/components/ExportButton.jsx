/**
 * Компонент кнопки экспорта данных
 */

import React, { useState } from 'react';
import './ExportButton.css';

export function ExportButton({ data, filename = 'export', formats = ['csv', 'json'] }) {
  const [isOpen, setIsOpen] = useState(false);

  const exportToCSV = () => {
    if (!data || data.length === 0) {
      alert('Нет данных для экспорта');
      return;
    }

    const headers = Object.keys(data[0]);
    const csvContent = [
      headers.join(','),
      ...data.map(row => 
        headers.map(header => {
          const value = row[header];
          if (value == null) return '';
          const stringValue = String(value);
          // Экранируем кавычки и оборачиваем в кавычки, если содержит запятую или перенос строки
          if (stringValue.includes(',') || stringValue.includes('\n')) {
            return `"${stringValue.replace(/"/g, '""')}"`;
          }
          return stringValue;
        }).join(',')
      )
    ].join('\n');

    const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${filename}.csv`;
    link.click();
    URL.revokeObjectURL(url);
    setIsOpen(false);
  };

  const exportToJSON = () => {
    if (!data || data.length === 0) {
      alert('Нет данных для экспорта');
      return;
    }

    const jsonContent = JSON.stringify(data, null, 2);
    const blob = new Blob([jsonContent], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${filename}.json`;
    link.click();
    URL.revokeObjectURL(url);
    setIsOpen(false);
  };

  if (formats.length === 0) return null;

  return (
    <div className="export-button-wrapper">
      <button
        className="button button-secondary export-button"
        onClick={() => setIsOpen(!isOpen)}
        title="Экспорт данных"
      >
        📥 Экспорт
      </button>
      {isOpen && (
        <div className="export-menu">
          {formats.includes('csv') && (
            <button onClick={exportToCSV} className="export-option">
              Экспорт в CSV
            </button>
          )}
          {formats.includes('json') && (
            <button onClick={exportToJSON} className="export-option">
              Экспорт в JSON
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default ExportButton;
