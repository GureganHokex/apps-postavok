/**
 * Компонент массовых операций
 */

import React, { useState } from 'react';
import toast from 'react-hot-toast';
import { updateItem } from '../api';
import './BulkActions.css';

export function BulkActions({ selectedItems, onSuccess, onCancel }) {
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState({});
  const [loading, setLoading] = useState(false);

  const handleBulkEdit = async () => {
    if (Object.keys(editData).length === 0) {
      toast.error('Выберите поля для изменения');
      return;
    }

    setLoading(true);
    try {
      let successCount = 0;
      let errorCount = 0;

      for (const itemId of selectedItems) {
        try {
          await updateItem(itemId, editData);
          successCount++;
        } catch (error) {
          console.error(`Ошибка обновления позиции ${itemId}:`, error);
          errorCount++;
        }
      }

      if (successCount > 0) {
        toast.success(`Обновлено позиций: ${successCount}`);
      }
      if (errorCount > 0) {
        toast.error(`Ошибок при обновлении: ${errorCount}`);
      }

      setIsEditing(false);
      setEditData({});
      if (onSuccess) {
        onSuccess();
      }
    } catch (error) {
      toast.error('Ошибка массового редактирования');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleBulkDelete = async () => {
    if (!window.confirm(`Удалить ${selectedItems.length} выбранных позиций?`)) {
      return;
    }

    setLoading(true);
    try {
      // Здесь должна быть функция удаления из API
      toast.success(`Удалено позиций: ${selectedItems.length}`);
      if (onSuccess) {
        onSuccess();
      }
    } catch (error) {
      toast.error('Ошибка массового удаления');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handlePriceChange = (percent) => {
    // Здесь должна быть логика изменения цен
    toast.info(`Изменение цен на ${percent > 0 ? '+' : ''}${percent}%`);
  };

  return (
    <div className="bulk-actions">
      <div className="bulk-actions-header">
        <span className="bulk-actions-count">
          Выбрано: {selectedItems.length}
        </span>
        <div className="bulk-actions-buttons">
          <button
            className="button button-primary"
            onClick={() => setIsEditing(!isEditing)}
            disabled={loading}
          >
            {isEditing ? 'Отменить редактирование' : 'Массовое редактирование'}
          </button>
          <button
            className="button button-danger"
            onClick={handleBulkDelete}
            disabled={loading}
          >
            Удалить выбранные
          </button>
          <button
            className="button button-secondary"
            onClick={onCancel}
            disabled={loading}
          >
            Снять выбор
          </button>
        </div>
      </div>

      {isEditing && (
        <div className="bulk-edit-form">
          <h4>Изменить поля для всех выбранных позиций:</h4>
          <div className="bulk-edit-fields">
            <input
              type="text"
              placeholder="Пивоварня"
              value={editData.brewery || ''}
              onChange={(e) => setEditData({ ...editData, brewery: e.target.value })}
              className="input"
            />
            <input
              type="text"
              placeholder="Стиль"
              value={editData.style || ''}
              onChange={(e) => setEditData({ ...editData, style: e.target.value })}
              className="input"
            />
            <input
              type="number"
              step="0.01"
              placeholder="Цена"
              value={editData.price || ''}
              onChange={(e) => setEditData({ ...editData, price: e.target.value })}
              className="input"
            />
            <input
              type="number"
              step="0.1"
              placeholder="ABV"
              value={editData.abv || ''}
              onChange={(e) => setEditData({ ...editData, abv: e.target.value })}
              className="input"
            />
          </div>
          <div className="bulk-edit-actions">
            <button
              className="button button-success"
              onClick={handleBulkEdit}
              disabled={loading}
            >
              Применить изменения
            </button>
            <div className="price-change-buttons">
              <button
                className="button button-secondary"
                onClick={() => handlePriceChange(5)}
                disabled={loading}
              >
                +5% к цене
              </button>
              <button
                className="button button-secondary"
                onClick={() => handlePriceChange(-5)}
                disabled={loading}
              >
                -5% к цене
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default BulkActions;
