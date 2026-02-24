/**
 * Компонент для формирования заказа.
 */

import React, { useState, useEffect, useMemo, useCallback, memo } from 'react';
import { DndProvider, useDrag, useDrop } from 'react-dnd';
import { HTML5Backend } from 'react-dnd-html5-backend';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import { getFileItems, createOrder, downloadOrder, getLocations, bulkCreateAvailableBeers } from '../api';
import { quantitySchema } from '../utils/validation';
import DraggableOrderItem from './DraggableOrderItem';
import OrderTemplates from './OrderTemplates';
import './OrderForm.css';

// Порог, выше которого считаем цену как за кегу (а не за литр) при отсутствии точной метки
const KEG_PER_LITER_THRESHOLD = 2000;

const OrderFormContent = memo(function OrderFormContent({ fileId, selectedItems, items }) {
  const [orderItems, setOrderItems] = useState([]);
  const [quantities, setQuantities] = useState({});
  const [showOnlyWithQty, setShowOnlyWithQty] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [exportFormat, setExportFormat] = useState('excel');
  const [createdOrder, setCreatedOrder] = useState(null);
  const [loadingItems, setLoadingItems] = useState(false);
  const [showTapsModal, setShowTapsModal] = useState(false);
  const [locations, setLocations] = useState([]);
  const [selectedLocationId, setSelectedLocationId] = useState(null);
  const [autoSendToTaps, setAutoSendToTaps] = useState(false);

  // Определяем, похоже ли на кегу
  const isKeg = useCallback((item) => {
    const volume = parseFloat(item.volume) || 0;
    const format = (item.format_type || '').toLowerCase();
    return format.includes('кег') || format.includes('keg') || volume >= 10;
  }, []);

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
              // По умолчанию: кеги = 1, фасовка/банка/бутылка = 10
              newQuantities[item.id] = isKeg(item) ? 1 : 10;
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

      // Автоматически отправляем кеги на краны, если включена опция
      if (autoSendToTaps && selectedLocationId) {
        try {
          const kegsToSend = orderItems
            .filter(item => {
              const qty = quantities[item.id] || 0;
              if (qty <= 0) return false;
              const format = (item.format_type || '').toLowerCase();
              const volume = parseFloat(item.volume) || 0;
              return format.includes('кег') || format.includes('keg') || volume >= 10;
            })
            .map(item => ({
              brewery: item.brewery || '',
              beer_name: item.beer_name || '',
              price_per_liter: item.price || null,
            }));

          if (kegsToSend.length > 0) {
            await bulkCreateAvailableBeers(selectedLocationId, kegsToSend);
            toast.success(`${kegsToSend.length} кег автоматически добавлено в доступные`);
          }
        } catch (err) {
          console.error('Ошибка автоматической отправки кегов:', err);
          toast.error('Не удалось автоматически отправить кеги на краны');
        }
      }

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

  /**
   * Проверяем, что позиция выглядит как кега.
   */
  const isKegFormat = useCallback((item) => {
    const volume = parseFloat(item.volume) || 0;
    const format = (item.format_type || '').toLowerCase();
    return format.includes('кег') || format.includes('keg') || volume >= 10;
  }, []);

  /**
   * Считает стоимость позиции с учётом кег:
   * - если price_unit = keg/liter, используем его;
   * - иначе эвристика: для кег цена < порога считается ценой за литр и умножается на объём.
   */
  const getItemTotal = useCallback((item, qty) => {
    const quantity = qty ?? quantities[item.id] ?? 0;
    const price = parseFloat(item.price) || 0;
    const volume = parseFloat(item.volume) || 0;
    const keg = isKegFormat(item);
    const priceUnit = (item.price_unit || '').toLowerCase();

    if (keg && volume > 0) {
      if (priceUnit === 'keg') {
        return quantity * price;
      }
      if (priceUnit === 'liter') {
        return quantity * price * volume;
      }

      const priceLooksPerLiter = price > 0 && price < KEG_PER_LITER_THRESHOLD;
      const kegPrice = priceLooksPerLiter ? price * volume : price;
      return quantity * kegPrice;
    }

    return quantity * price;
  }, [isKegFormat, quantities]);

  const totalPrice = useMemo(() => {
    return orderItems.reduce((sum, item) => {
    return sum + getItemTotal(item);
  }, 0);
  }, [orderItems, getItemTotal]);

  // Видимые элементы с учётом фильтра "только с количеством > 0"
  const visibleOrderItems = useMemo(() => {
    if (!showOnlyWithQty) return orderItems;
    return orderItems.filter((item) => (quantities[item.id] || 0) > 0);
  }, [orderItems, quantities, showOnlyWithQty]);

  const handleApplyTemplate = useCallback((template) => {
    // Применяем шаблон к текущему заказу
    const templateQuantities = {};
    template.items.forEach(item => {
      templateQuantities[item.item_id] = item.quantity;
    });
    setQuantities(prev => ({ ...prev, ...templateQuantities }));
    toast.success(`Шаблон "${template.name}" применен`);
  }, []);

  const handleSaveAsTemplate = useCallback(() => {
    // Сохраняем текущий заказ как шаблон
    const templateName = prompt('Введите название шаблона:');
    if (!templateName) return;

    const template = {
      id: Date.now(),
      name: templateName,
      items: orderItems.map(item => ({
        item_id: item.id,
        quantity: quantities[item.id] || 0,
        brewery: item.brewery,
        beer_name: item.beer_name,
        price: item.price,
      })),
      created_at: new Date().toISOString(),
    };

    const templates = JSON.parse(localStorage.getItem('order_templates') || '[]');
    templates.push(template);
    localStorage.setItem('order_templates', JSON.stringify(templates));
    toast.success('Шаблон сохранен');
  }, [orderItems, quantities]);

  // Загрузка локаций для модалки
  const loadLocationsForTaps = useCallback(async () => {
    try {
      const data = await getLocations();
      const locationsList = data.results || data;
      setLocations(locationsList);
      if (locationsList.length > 0) {
        setSelectedLocationId(locationsList[0].id);
      }
    } catch (err) {
      toast.error('Ошибка загрузки локаций');
    }
  }, []);

  // Отправка кег на краны
  const handleSendToTaps = useCallback(async () => {
    if (!selectedLocationId) {
      toast.error('Выберите локацию');
      return;
    }

    // Фильтруем только кеги (format_type содержит 'кег' или 'keg' или объем >= 10л)
    const kegsToSend = orderItems
      .filter(item => {
        const qty = quantities[item.id] || 0;
        if (qty <= 0) return false;
        const format = (item.format_type || '').toLowerCase();
        const volume = parseFloat(item.volume) || 0;
        // Только кеги: содержит "кег" или "keg" или объем >= 10 литров
        return format.includes('кег') || format.includes('keg') || volume >= 10;
      })
      .map(item => ({
        brewery: item.brewery || '',
        beer_name: item.beer_name || '',
        price_per_liter: item.price || null,
      }));

    if (kegsToSend.length === 0) {
      toast.error('Нет кег для отправки на краны');
      return;
    }

    try {
      await bulkCreateAvailableBeers(selectedLocationId, kegsToSend);
      toast.success(`${kegsToSend.length} кег добавлено в доступные`);
      setShowTapsModal(false);
    } catch (err) {
      console.error('Ошибка отправки на краны:', err);
      const errorMsg = err.response?.data?.error || err.message || 'Ошибка отправки на краны';
      toast.error(errorMsg);
    }
  }, [orderItems, quantities, selectedLocationId]);

  return (
    <div className="OrderForm">
      <div className="card">
        <h2>Формирование заказа</h2>

        <OrderTemplates 
          onApplyTemplate={handleApplyTemplate}
          currentItems={orderItems}
          currentQuantities={quantities}
        />

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

          <label className="checkbox-inline">
            <input
              type="checkbox"
              checked={showOnlyWithQty}
              onChange={(e) => setShowOnlyWithQty(e.target.checked)}
            />
            <span>Показывать только с количеством &gt; 0</span>
          </label>

            {orderItems.length > 0 && (
              <button
                className="button button-secondary"
                onClick={handleSaveAsTemplate}
              >
                💾 Сохранить как шаблон
              </button>
            )}

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
                  {visibleOrderItems.map((item, index) => (
                    <DraggableOrderItem
                      key={item.id}
                      item={item}
                      index={index}
                      quantity={quantities[item.id] || 0}
                      quantityErrors={quantityErrors}
                      onQuantityChange={handleQuantityChange}
                      getItemTotal={getItemTotal}
                    />
                  ))}
                </tbody>
                <tfoot>
                  <motion.tr
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                  >
                    <td colSpan="7" className="total-label">Итого:</td>
                    <td className="total-value">{totalItems}</td>
                    <td className="total-value">{totalPrice.toFixed(2)} ₽</td>
                  </motion.tr>
                </tfoot>
              </table>
            </div>

            <div className="order-actions">
              {/* Автоматическая отправка кегов на краны */}
              {totalItems > 0 && (
                <div className="auto-send-option">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={autoSendToTaps}
                      onChange={(e) => {
                        setAutoSendToTaps(e.target.checked);
                        if (e.target.checked && !selectedLocationId && locations.length > 0) {
                          setSelectedLocationId(locations[0].id);
                          loadLocationsForTaps();
                        } else if (e.target.checked && locations.length === 0) {
                          loadLocationsForTaps();
                        }
                      }}
                    />
                    <span>Автоматически добавить кеги на краны после создания заказа</span>
                  </label>
                  {autoSendToTaps && (
                    <select
                      value={selectedLocationId || ''}
                      onChange={(e) => setSelectedLocationId(parseInt(e.target.value))}
                      className="input input-small"
                      style={{ marginLeft: '10px', marginTop: '5px' }}
                    >
                      {locations.length === 0 && <option value="">Загрузка...</option>}
                      {locations.map(loc => (
                        <option key={loc.id} value={loc.id}>{loc.name}</option>
                      ))}
                    </select>
                  )}
                </div>
              )}
              
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

              <button
                className="button button-secondary"
                onClick={() => {
                  loadLocationsForTaps();
                  setShowTapsModal(true);
                }}
                disabled={totalItems === 0}
                title="Отправить кеги в список доступных для кранов"
              >
                🍺 На краны
              </button>
            </div>

            {/* Модальное окно для отправки на краны */}
            {showTapsModal && (
              <div className="modal-overlay" onClick={() => setShowTapsModal(false)}>
                <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                  <h3>Отправить кеги на краны</h3>
                  <p className="modal-hint">Кеги будут добавлены в список доступных позиций для распределения по кранам</p>
                  
                  <div className="modal-field">
                    <label>Локация:</label>
                    <select
                      value={selectedLocationId || ''}
                      onChange={(e) => setSelectedLocationId(parseInt(e.target.value))}
                      className="input"
                    >
                      {locations.map(loc => (
                        <option key={loc.id} value={loc.id}>{loc.name}</option>
                      ))}
                    </select>
                  </div>

                  <div className="modal-preview">
                    <strong>Будут добавлены кеги:</strong>
                    <ul>
                      {orderItems
                        .filter(item => {
                          const qty = quantities[item.id] || 0;
                          if (qty <= 0) return false;
                          const format = (item.format_type || '').toLowerCase();
                          const volume = parseFloat(item.volume) || 0;
                          return format.includes('кег') || format.includes('keg') || volume >= 10;
                        })
                        .map(item => (
                          <li key={item.id}>
                            {item.brewery} | {item.beer_name}
                            {item.price && `(${Math.round(item.price)})`}
                          </li>
                        ))
                      }
                    </ul>
                  </div>

                  <div className="modal-actions">
                    <button className="button button-secondary" onClick={() => setShowTapsModal(false)}>
                      Отмена
                    </button>
                    <button className="button button-success" onClick={handleSendToTaps}>
                      Добавить
                    </button>
                  </div>
                </div>
              </div>
            )}
          </>
          </AnimatePresence>
        )}
      </div>
    </div>
  );
});

const OrderForm = memo(function OrderForm({ fileId, selectedItems, items }) {
  return (
    <DndProvider backend={HTML5Backend}>
      <OrderFormContent fileId={fileId} selectedItems={selectedItems} items={items} />
    </DndProvider>
  );
});

export default OrderForm;
