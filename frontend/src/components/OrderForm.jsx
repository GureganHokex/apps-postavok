/**
 * Компонент для формирования заказа.
 */

import React, { useState, useEffect, useMemo, useCallback, memo } from 'react';
import { DndProvider } from 'react-dnd';
import { HTML5Backend } from 'react-dnd-html5-backend';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import { getFileItems, createOrder, downloadOrder, getLocations, bulkCreateAvailableBeers, getApiErrorMessage } from '../api';
import { quantitySchema } from '../utils/validation';
import DraggableOrderItem from './DraggableOrderItem';
import OrderTemplates from './OrderTemplates';
import './OrderForm.css';

// Порог, выше которого считаем цену как за кегу (а не за литр) при отсутствии точной метки
const KEG_PER_LITER_THRESHOLD = 2000;
const NON_KEG_FORMAT_TOKENS = ['бан', 'can', 'бут', 'bottle', 'пэт', 'pet'];

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
  const [selectedKegIdsForTaps, setSelectedKegIdsForTaps] = useState([]);
  const [kegSelectionTouched, setKegSelectionTouched] = useState(false);

  // Определяем, похоже ли на кегу
  const isKeg = useCallback((item) => {
    const volume = parseFloat(item.volume) || 0;
    const format = (item.format_type || '').toLowerCase().trim();
    if (format.includes('кег') || format.includes('keg') || format.includes('draft') || format.includes('розлив')) {
      return true;
    }
    if (NON_KEG_FORMAT_TOKENS.some((token) => format.includes(token))) {
      return false;
    }
    return volume >= 15;
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

        const normalizeList = (raw) => {
          if (Array.isArray(raw)) return raw;
          if (raw && Array.isArray(raw.results)) return raw.results;
          return [];
        };

        const selectedSet = new Set(selectedItems.map(Number));

        // Сначала берём позиции из родителя (уже в памяти после парсинга / вкладки «Позиции»).
        // Повторный GET /files/:id/items/ после долгого парса иногда даёт 401 (сессия/прокси) — без лишнего запроса не падаем.
        let allItems = null;
        const parentList = normalizeList(items);
        if (parentList.length > 0) {
          const missing = [...selectedSet].some((id) => !parentList.some((it) => Number(it.id) === id));
          if (!missing) {
            allItems = parentList;
          }
        }
        if (allItems === null) {
          const raw = await getFileItems(fileId, {});
          allItems = normalizeList(raw);
        }

        const itemsToShow = allItems.filter((item) => selectedSet.has(Number(item.id)));
        
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
  }, [selectedItems, fileId, isKeg, items]);

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
          const kegsToSend = buildKegPayloadForTaps(selectedKegsForTaps);

          if (kegsToSend.length > 0) {
            await bulkCreateAvailableBeers(selectedLocationId, kegsToSend);
            toast.success(`${kegsToSend.length} кег автоматически добавлено в доступные`);
          } else {
            toast('Заказ создан, но кеги для кранов не выбраны');
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
      const errorMsg = `Ошибка экспорта заказа: ${getApiErrorMessage(err)}`;
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
    return isKeg(item);
  }, [isKeg]);

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

  const eligibleKegsForTaps = useMemo(() => {
    return orderItems.filter((item) => {
      const qty = quantities[item.id] || 0;
      return qty > 0 && isKeg(item);
    });
  }, [orderItems, quantities, isKeg]);

  const selectedKegsForTaps = useMemo(() => {
    const selectedSet = new Set(selectedKegIdsForTaps.map(Number));
    return eligibleKegsForTaps.filter((item) => selectedSet.has(Number(item.id)));
  }, [eligibleKegsForTaps, selectedKegIdsForTaps]);

  useEffect(() => {
    const eligibleIds = eligibleKegsForTaps.map((item) => Number(item.id));
    if (!kegSelectionTouched) {
      setSelectedKegIdsForTaps(eligibleIds);
      return;
    }
    setSelectedKegIdsForTaps((prev) => prev.filter((id) => eligibleIds.includes(Number(id))));
  }, [eligibleKegsForTaps, kegSelectionTouched]);

  const toggleKegForTaps = useCallback((itemId, checked) => {
    setKegSelectionTouched(true);
    setSelectedKegIdsForTaps((prev) => {
      const normalizedId = Number(itemId);
      if (checked) {
        return prev.includes(normalizedId) ? prev : [...prev, normalizedId];
      }
      return prev.filter((id) => Number(id) !== normalizedId);
    });
  }, []);

  const selectAllKegsForTaps = useCallback((checked) => {
    setKegSelectionTouched(true);
    setSelectedKegIdsForTaps(checked ? eligibleKegsForTaps.map((item) => Number(item.id)) : []);
  }, [eligibleKegsForTaps]);

  const buildKegPayloadForTaps = useCallback((kegs) => {
    const volumePriceFromItem = (item) => {
      const parts = [];
      if (item.volume != null && item.volume !== '') {
        const v = Number(item.volume);
        if (!Number.isNaN(v)) {
          parts.push(Number.isInteger(v) ? `${v} л` : `${v} л`);
        }
      }
      if (item.price != null && item.price !== '') {
        const p = Number(item.price);
        if (!Number.isNaN(p)) {
          parts.push(`${Math.round(p)} ₽`);
        }
      }
      if (item.format_type && String(item.format_type).trim()) {
        parts.push(String(item.format_type).trim());
      }
      return parts.join(' · ');
    };
    const abvFromItem = (item) => {
      if (item.abv == null || item.abv === '') return '';
      const a = Number(item.abv);
      if (Number.isNaN(a)) return String(item.abv).trim();
      return `${Number.isInteger(a) || Math.abs(a - Math.round(a)) < 1e-6 ? Math.round(a) : a} %`;
    };
    return kegs.map((item) => ({
      source_item_id: item.id,
      brewery: item.brewery || '',
      beer_name: item.beer_name || '',
      price_per_liter: item.price || null,
      description: item.description || '',
      volume_price_text: volumePriceFromItem(item),
      bitterness_ibu: (item.ibu && String(item.ibu).trim()) || '',
      abv_text: abvFromItem(item),
    }));
  }, []);

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
      console.error('loadLocationsForTaps', err);
      const r = err?.response;
      let suffix = '';
      if (!r && (err?.code === 'ERR_NETWORK' || err?.message === 'Network Error')) {
        suffix = ': нет ответа сервера';
      } else if (r?.data?.detail && typeof r.data.detail === 'string') {
        suffix = `: ${r.data.detail}`;
      } else if (r?.status) {
        suffix = ` (HTTP ${r.status})`;
      }
      toast.error(`Ошибка загрузки локаций${suffix}`);
    }
  }, []);

  // Отправка кег на краны
  const handleSendToTaps = useCallback(async () => {
    if (!selectedLocationId) {
      toast.error('Выберите локацию');
      return;
    }

    const kegsToSend = buildKegPayloadForTaps(selectedKegsForTaps);

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
  }, [selectedLocationId, selectedKegsForTaps, buildKegPayloadForTaps]);

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
                Сохранить как шаблон
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

            {eligibleKegsForTaps.length > 0 && (
              <div className="keg-selection-panel">
                <div className="keg-selection-header">
                  <div>
                    <h3>Кеги для добавления на краны</h3>
                    <p>
                      Отметьте только те кеги, которые должны попасть в список доступных позиций
                      на вкладке «Краны».
                    </p>
                  </div>
                  <label className="checkbox-inline">
                    <input
                      type="checkbox"
                      checked={
                        eligibleKegsForTaps.length > 0 &&
                        selectedKegsForTaps.length === eligibleKegsForTaps.length
                      }
                      onChange={(e) => selectAllKegsForTaps(e.target.checked)}
                    />
                    <span>Выбрать все</span>
                  </label>
                </div>
                <div className="keg-selection-list">
                  {eligibleKegsForTaps.map((item) => (
                    <label key={item.id} className="keg-selection-item">
                      <input
                        type="checkbox"
                        checked={selectedKegIdsForTaps.includes(Number(item.id))}
                        onChange={(e) => toggleKegForTaps(item.id, e.target.checked)}
                      />
                      <span className="keg-selection-title">
                        {(item.brewery || 'Без пивоварни')} | {(item.beer_name || 'Без названия')}
                      </span>
                      <span className="keg-selection-meta">
                        {item.volume ? `${item.volume} л` : 'Объём не указан'}
                        {item.price ? `, ${Math.round(item.price)} ₽` : ''}
                      </span>
                    </label>
                  ))}
                </div>
                <div className="keg-selection-summary">
                  Выбрано для кранов: {selectedKegsForTaps.length} из {eligibleKegsForTaps.length}
                </div>
              </div>
            )}

            <div className="order-actions">
              {/* Автоматическая отправка кегов на краны */}
              {eligibleKegsForTaps.length > 0 && (
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
                Добавить на краны
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
                    <strong>Выберите кеги для добавления:</strong>
                    {eligibleKegsForTaps.length === 0 ? (
                      <p>Нет кег с количеством больше 0.</p>
                    ) : (
                      <div className="modal-keg-list">
                        {eligibleKegsForTaps.map(item => (
                          <label key={item.id} className="modal-keg-item">
                            <input
                              type="checkbox"
                              checked={selectedKegIdsForTaps.includes(Number(item.id))}
                              onChange={(e) => toggleKegForTaps(item.id, e.target.checked)}
                            />
                            <span>
                              {item.brewery} | {item.beer_name}
                              {item.price && ` (${Math.round(item.price)} ₽)`}
                            </span>
                          </label>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="modal-actions">
                    <button className="button button-secondary" onClick={() => setShowTapsModal(false)}>
                      Отмена
                    </button>
                    <button
                      className="button button-success"
                      onClick={handleSendToTaps}
                      disabled={selectedKegsForTaps.length === 0}
                    >
                      Добавить выбранные
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
