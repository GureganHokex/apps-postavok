/**
 * Компонент для формирования заказа.
 */

import React, { useState, useEffect, useMemo, useCallback, memo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import { getFileItems, createOrder, downloadOrder } from '../api';
import { quantitySchema } from '../utils/validation';
import './OrderForm.css';

const OrderForm = memo(function OrderForm({ fileId, selectedItems, items }) {
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
        const errorMsg = `Ошибка загрузки позиций: ${err.message}`;
        toast.error(errorMsg);
        setError(errorMsg);
      } finally {
        setLoadingItems(false);
      }
    };

    loadSelectedItems();
  }, [selectedItems, fileId]);

  const [quantityErrors, setQuantityErrors] = useState({});

  const handleQuantityChange = useCallback((itemId, value) => {
    const numValue = parseInt(value) || 0;
    
    // Валидация
    try {
      quantitySchema.parse({ quantity: numValue });
      setQuantityErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[itemId];
        return newErrors;
      });
    } catch (error) {
      if (error.errors && error.errors[0]) {
        setQuantityErrors(prev => ({
          ...prev,
          [itemId]: error.errors[0].message,
        }));
      }
    }
    
    if (numValue >= 0) {
      setQuantities(prev => ({ ...prev, [itemId]: numValue }));
    }
  }, []);

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
        const errorMsg = 'Выберите хотя бы одну позицию с количеством больше 0';
        toast.error(errorMsg);
        setError(errorMsg);
        return;
      }

      // Проверяем наличие ошибок валидации
      const hasErrors = Object.keys(quantityErrors).length > 0;
      if (hasErrors) {
        const errorMsg = 'Исправьте ошибки в количестве товаров';
        toast.error(errorMsg);
        setError(errorMsg);
        return;
      }

      // Создаем заказ
      const order = await createOrder(orderItemsList, exportFormat);
      setCreatedOrder(order);
      const successMsg = `Заказ #${order.id} успешно создан`;
      toast.success(successMsg);
      setSuccess(successMsg);

      // Автоматически экспортируем заказ
      setTimeout(() => {
        handleExport(order.id);
      }, 1000);
    } catch (err) {
      const errorMsg = `Ошибка создания заказа: ${err.message}`;
      toast.error(errorMsg);
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleExport = useCallback(async (orderId) => {
    try {
      await downloadOrder(orderId);
      toast.success('Заказ успешно скачан');
    } catch (err) {
      const errorMsg = `Ошибка экспорта заказа: ${err.message}`;
      toast.error(errorMsg);
      setError(errorMsg);
    }
  }, []);

  const totalItems = useMemo(() => {
    return orderItems.reduce((sum, item) => {
      return sum + (quantities[item.id] || 0);
    }, 0);
  }, [orderItems, quantities]);

  const totalPrice = useMemo(() => {
    return orderItems.reduce((sum, item) => {
      const qty = quantities[item.id] || 0;
      const price = parseFloat(item.price) || 0;
      return sum + (qty * price);
    }, 0);
  }, [orderItems, quantities]);

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
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="loading"
          >
            Загрузка выбранных позиций...
          </motion.div>
        ) : orderItems.length === 0 ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="empty-message"
          >
            <p>Выберите позиции для заказа на вкладке "Позиции"</p>
          </motion.div>
        ) : (
          <AnimatePresence>
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
                  {orderItems.map((item, index) => {
                    const qty = quantities[item.id] || 0;
                    const price = parseFloat(item.price) || 0;
                    const sum = qty * price;

                    return (
                      <motion.tr
                        key={item.id}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: index * 0.05 }}
                      >
                        <td>{item.brewery || '-'}</td>
                        <td>{item.beer_name || '-'}</td>
                        <td>{item.style || '-'}</td>
                        <td>{item.price || '-'}</td>
                        <td>{item.currency || '-'}</td>
                        <td>{item.volume || '-'}</td>
                        <td>{item.format_type || '-'}</td>
                        <td>
                          <div className="quantity-input-wrapper">
                            <input
                              type="number"
                              min="0"
                              max="10000"
                              value={qty}
                              onChange={(e) => handleQuantityChange(item.id, e.target.value)}
                              className={`input input-small ${quantityErrors[item.id] ? 'input-error' : ''}`}
                              aria-label={`Количество для ${item.beer_name || item.id}`}
                            />
                            {quantityErrors[item.id] && (
                              <motion.div
                                initial={{ opacity: 0, y: -5 }}
                                animate={{ opacity: 1, y: 0 }}
                                className="input-error-message"
                              >
                                {quantityErrors[item.id]}
                              </motion.div>
                            )}
                          </div>
                        </td>
                        <td className="sum">{sum.toFixed(2)}</td>
                      </motion.tr>
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
          </AnimatePresence>
        )}
      </div>
    </div>
  );
});

export default OrderForm;

