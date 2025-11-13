/**
 * Компонент для формирования заказа.
 */

import React, { useState, useEffect } from 'react';
import { getFileItems, createOrder, downloadOrder } from '../api';
import './OrderForm.css';

function OrderForm({ fileId, selectedItems, items }) {
  const [orderItems, setOrderItems] = useState([]);
  const [quantities, setQuantities] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [exportFormat, setExportFormat] = useState('excel');
  const [createdOrder, setCreatedOrder] = useState(null);
  const [loadingItems, setLoadingItems] = useState(false);

  useEffect(() => {
    // Загружаем все выбранные позиции из всех листов
    const loadSelectedItems = async () => {
      if (selectedItems.length === 0) {
        setOrderItems([]);
        setQuantities({});
        return;
      }

      try {
        setLoadingItems(true);
        
        // Загружаем все позиции без фильтра по листу для получения всех выбранных
        // Используем пустые фильтры, чтобы получить все позиции, затем фильтруем по selectedItems
        const allItems = await getFileItems(fileId, {});
        const itemsToShow = allItems.filter(item => selectedItems.includes(item.id));
        
        setOrderItems(itemsToShow);
        
        // Инициализируем количества только для новых элементов
        setQuantities(prevQuantities => {
          const newQuantities = { ...prevQuantities };
          itemsToShow.forEach(item => {
            if (!(item.id in newQuantities)) {
              newQuantities[item.id] = 1;
            }
          });
          // Удаляем количества для элементов, которые больше не выбраны
          Object.keys(newQuantities).forEach(itemId => {
            if (!itemsToShow.find(item => item.id === parseInt(itemId))) {
              delete newQuantities[itemId];
            }
          });
          return newQuantities;
        });
      } catch (err) {
        setError(`Ошибка загрузки позиций: ${err.message}`);
      } finally {
        setLoadingItems(false);
      }
    };

    loadSelectedItems();
  }, [selectedItems, fileId]);

  const handleQuantityChange = (itemId, value) => {
    const numValue = parseInt(value) || 0;
    if (numValue >= 0) {
      setQuantities({ ...quantities, [itemId]: numValue });
    }
  };

  const handleCreateOrder = async () => {
    try {
      setLoading(true);
      setError(null);
      setSuccess(null);

      // Формируем список позиций с количествами
      const orderItemsList = orderItems
        .filter(item => quantities[item.id] > 0)
        .map(item => ({
          item_id: item.id,
          quantity: quantities[item.id],
        }));

      if (orderItemsList.length === 0) {
        setError('Выберите хотя бы одну позицию с количеством больше 0');
        return;
      }

      // Создаем заказ
      const order = await createOrder(orderItemsList, exportFormat);
      setCreatedOrder(order);
      setSuccess(`Заказ #${order.id} успешно создан`);

      // Автоматически экспортируем заказ
      setTimeout(() => {
        handleExport(order.id);
      }, 1000);
    } catch (err) {
      setError(`Ошибка создания заказа: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async (orderId) => {
    try {
      await downloadOrder(orderId);
    } catch (err) {
      setError(`Ошибка экспорта заказа: ${err.message}`);
    }
  };

  const totalItems = orderItems.reduce((sum, item) => {
    return sum + (quantities[item.id] || 0);
  }, 0);

  const totalPrice = orderItems.reduce((sum, item) => {
    const qty = quantities[item.id] || 0;
    const price = parseFloat(item.price) || 0;
    return sum + (qty * price);
  }, 0);

  return (
    <div className="OrderForm">
      <div className="card">
        <h2>Формирование заказа</h2>

        <div className="order-controls">
          <div className="format-selector">
            <label>
              Формат экспорта:
              <select
                value={exportFormat}
                onChange={(e) => setExportFormat(e.target.value)}
                className="input"
              >
                <option value="excel">Excel</option>
                <option value="pdf">PDF</option>
              </select>
            </label>
          </div>

          <div className="order-summary">
            <div className="summary-item">
              <span className="label">Позиций в заказе:</span>
              <span className="value">{orderItems.length}</span>
            </div>
            <div className="summary-item">
              <span className="label">Общее количество:</span>
              <span className="value">{totalItems}</span>
            </div>
            <div className="summary-item">
              <span className="label">Общая стоимость:</span>
              <span className="value">{totalPrice.toFixed(2)} ₽</span>
            </div>
          </div>
        </div>

        {error && <div className="error">{error}</div>}
        {success && <div className="success">{success}</div>}

        {loadingItems ? (
          <div className="loading">Загрузка выбранных позиций...</div>
        ) : orderItems.length === 0 ? (
          <div className="empty-message">
            <p>Выберите позиции для заказа на вкладке "Позиции"</p>
          </div>
        ) : (
          <>
            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th>Пивоварня</th>
                    <th>Название</th>
                    <th>Стиль</th>
                    <th>Цена</th>
                    <th>Валюта</th>
                    <th>Объём</th>
                    <th>Формат</th>
                    <th>Количество</th>
                    <th>Сумма</th>
                  </tr>
                </thead>
                <tbody>
                  {orderItems.map((item) => {
                    const qty = quantities[item.id] || 0;
                    const price = parseFloat(item.price) || 0;
                    const sum = qty * price;

                    return (
                      <tr key={item.id}>
                        <td>{item.brewery || '-'}</td>
                        <td>{item.beer_name || '-'}</td>
                        <td>{item.style || '-'}</td>
                        <td>{item.price || '-'}</td>
                        <td>{item.currency || '-'}</td>
                        <td>{item.volume || '-'}</td>
                        <td>{item.format_type || '-'}</td>
                        <td>
                          <input
                            type="number"
                            min="0"
                            value={qty}
                            onChange={(e) => handleQuantityChange(item.id, e.target.value)}
                            className="input input-small"
                          />
                        </td>
                        <td className="sum">{sum.toFixed(2)}</td>
                      </tr>
                    );
                  })}
                </tbody>
                <tfoot>
                  <tr>
                    <td colSpan="7" className="total-label">Итого:</td>
                    <td className="total-value">{totalItems}</td>
                    <td className="total-value">{totalPrice.toFixed(2)} ₽</td>
                  </tr>
                </tfoot>
              </table>
            </div>

            <div className="order-actions">
              <button
                className="button button-success"
                onClick={handleCreateOrder}
                disabled={loading || totalItems === 0}
              >
                {loading ? 'Создание заказа...' : 'Создать заказ'}
              </button>

              {createdOrder && (
                <button
                  className="button button-primary"
                  onClick={() => handleExport(createdOrder.id)}
                >
                  Скачать заказ
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default OrderForm;

