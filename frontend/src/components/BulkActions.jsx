/**
 * Компонент для массовых операций
 */

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import { bulkUpdateItems, bulkDeleteItems } from '../api';
import './BulkActions.css';

function BulkActions({ selectedItems, onSuccess, onCancel }) {
  const [action, setAction] = useState(null);
  const [updateData, setUpdateData] = useState({
    price: '',
    currency: 'RUB',
    stock: '',
  });
  const [priceChangeType, setPriceChangeType] = useState('fixed'); // 'fixed' или 'percent'
  const [priceChangeValue, setPriceChangeValue] = useState('');

  const handleBulkUpdate = async () => {
    if (!updateData.price && !updateData.stock && !updateData.currency) {
      toast.error('Заполните хотя бы одно поле для обновления');
      return;
    }

    try {
      const dataToUpdate = { ...updateData };
      
      // Обрабатываем изменение цены
      if (priceChangeValue) {
        if (priceChangeType === 'percent') {
          dataToUpdate.price_change_percent = parseFloat(priceChangeValue);
        } else {
          dataToUpdate.price = parseFloat(priceChangeValue);
        }
      }

      await bulkUpdateItems(selectedItems, dataToUpdate);
      toast.success(`Обновлено позиций: ${selectedItems.length}`);
      if (onSuccess) onSuccess();
      setAction(null);
    } catch (err) {
      toast.error(`Ошибка обновления: ${err.message}`);
    }
  };

  const handleBulkDelete = async () => {
    if (!window.confirm(`Вы уверены, что хотите удалить ${selectedItems.length} позиций?`)) {
      return;
    }

    try {
      await bulkDeleteItems(selectedItems);
      toast.success(`Удалено позиций: ${selectedItems.length}`);
      if (onSuccess) onSuccess();
      setAction(null);
    } catch (err) {
      toast.error(`Ошибка удаления: ${err.message}`);
    }
  };

  if (selectedItems.length === 0) {
    return null;
  }

  return (
    <div className="BulkActions">
      <AnimatePresence>
        {action === null ? (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="bulk-actions-bar"
          >
            <div className="bulk-info">
              <span className="bulk-count">Выбрано: {selectedItems.length}</span>
            </div>
            <div className="bulk-buttons">
              <button
                className="button button-primary"
                onClick={() => setAction('update')}
              >
                Массовое редактирование
              </button>
              <button
                className="button button-danger"
                onClick={() => setAction('delete')}
              >
                Удалить выбранные
              </button>
              {onCancel && (
                <button
                  className="button"
                  onClick={onCancel}
                >
                  Отменить выбор
                </button>
              )}
            </div>
          </motion.div>
        ) : action === 'update' ? (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="bulk-update-form"
          >
            <h3>Массовое редактирование ({selectedItems.length} позиций)</h3>
            
            <div className="form-group">
              <label>Изменение цены:</label>
              <div className="price-change-controls">
                <select
                  value={priceChangeType}
                  onChange={(e) => setPriceChangeType(e.target.value)}
                  className="input"
                >
                  <option value="fixed">Фиксированная сумма</option>
                  <option value="percent">Процент</option>
                </select>
                <input
                  type="number"
                  placeholder={priceChangeType === 'percent' ? 'Процент (%)' : 'Новая цена'}
                  value={priceChangeValue}
                  onChange={(e) => setPriceChangeValue(e.target.value)}
                  className="input"
                />
              </div>
            </div>

            <div className="form-group">
              <label>Валюта:</label>
              <select
                value={updateData.currency}
                onChange={(e) => setUpdateData({ ...updateData, currency: e.target.value })}
                className="input"
              >
                <option value="RUB">RUB</option>
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
              </select>
            </div>

            <div className="form-group">
              <label>Остатки:</label>
              <input
                type="text"
                placeholder="Новое значение остатков"
                value={updateData.stock}
                onChange={(e) => setUpdateData({ ...updateData, stock: e.target.value })}
                className="input"
              />
            </div>

            <div className="form-actions">
              <button
                className="button button-success"
                onClick={handleBulkUpdate}
              >
                Применить
              </button>
              <button
                className="button"
                onClick={() => setAction(null)}
              >
                Отмена
              </button>
            </div>
          </motion.div>
        ) : action === 'delete' ? (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="bulk-delete-confirm"
          >
            <h3>Подтверждение удаления</h3>
            <p>Вы уверены, что хотите удалить {selectedItems.length} выбранных позиций?</p>
            <div className="form-actions">
              <button
                className="button button-danger"
                onClick={handleBulkDelete}
              >
                Удалить
              </button>
              <button
                className="button"
                onClick={() => setAction(null)}
              >
                Отмена
              </button>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

export default BulkActions;

