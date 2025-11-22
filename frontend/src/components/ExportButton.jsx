/**
 * Компонент для экспорта данных в разных форматах
 */

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import toast from 'react-hot-toast';
import './ExportButton.css';

function ExportButton({ data, filename = 'export', formats = ['csv', 'json', 'xlsx'] }) {
  const [exporting, setExporting] = useState(false);

  const exportToCSV = () => {
    if (!data || data.length === 0) {
      toast.error('Нет данных для экспорта');
      return;
    }

    try {
      const headers = Object.keys(data[0]);
      const csvContent = [
        headers.join(','),
        ...data.map(row => 
          headers.map(header => {
            const value = row[header];
            // Экранируем запятые и кавычки
            if (value === null || value === undefined) return '';
            const stringValue = String(value).replace(/"/g, '""');
            return `"${stringValue}"`;
          }).join(',')
        )
      ].join('\n');

      const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `${filename}.csv`;
      link.click();
      toast.success('Данные экспортированы в CSV');
    } catch (error) {
      toast.error(`Ошибка экспорта CSV: ${error.message}`);
    }
  };

  const exportToJSON = () => {
    if (!data || data.length === 0) {
      toast.error('Нет данных для экспорта');
      return;
    }

    try {
      const jsonContent = JSON.stringify(data, null, 2);
      const blob = new Blob([jsonContent], { type: 'application/json' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `${filename}.json`;
      link.click();
      toast.success('Данные экспортированы в JSON');
    } catch (error) {
      toast.error(`Ошибка экспорта JSON: ${error.message}`);
    }
  };

  const exportToXLSX = async () => {
    if (!data || data.length === 0) {
      toast.error('Нет данных для экспорта');
      return;
    }

    try {
      setExporting(true);
      // Для XLSX нужна библиотека, используем простой CSV как fallback
      toast.info('Экспорт в Excel через сервер...');
      // Здесь можно добавить вызов API для экспорта в Excel
      exportToCSV();
    } catch (error) {
      toast.error(`Ошибка экспорта Excel: ${error.message}`);
    } finally {
      setExporting(false);
    }
  };

  const handleExport = (format) => {
    switch (format) {
      case 'csv':
        exportToCSV();
        break;
      case 'json':
        exportToJSON();
        break;
      case 'xlsx':
        exportToXLSX();
        break;
      default:
        toast.error('Неподдерживаемый формат');
    }
  };

  if (formats.length === 0) return null;

  return (
    <div className="export-button-container">
      {formats.length === 1 ? (
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          className="button button-primary export-button"
          onClick={() => handleExport(formats[0])}
          disabled={exporting || !data || data.length === 0}
        >
          {exporting ? 'Экспорт...' : `Экспорт в ${formats[0].toUpperCase()}`}
        </motion.button>
      ) : (
        <div className="export-dropdown">
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="button button-primary export-button"
            disabled={exporting || !data || data.length === 0}
          >
            {exporting ? 'Экспорт...' : '📥 Экспорт данных'}
          </motion.button>
          <div className="export-menu">
            {formats.map(format => (
              <button
                key={format}
                className="export-menu-item"
                onClick={() => handleExport(format)}
                disabled={exporting}
              >
                Экспорт в {format.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default ExportButton;

