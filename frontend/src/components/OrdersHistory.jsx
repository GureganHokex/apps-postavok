/**
 * Компонент истории заказов и расширенной статистики по заказам.
 */

import React, { useState, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import { getOrders, downloadOrder, getOrder, createOrder, getOrderStatistics } from '../api';
import { useQuery } from '@tanstack/react-query';
import './OrdersHistory.css';

function OrdersHistory() {
  const [filters, setFilters] = useState({
    date_from: '',
    date_to: '',
    search: '',
  });
  const [selectedOrder, setSelectedOrder] = useState(null);

  const { data: ordersData, isLoading, error, refetch } = useQuery({
    queryKey: ['orders', filters],
    queryFn: () => getOrders(filters),
    staleTime: 30000, // 30 секунд
  });

  const orders = ordersData?.results || ordersData || [];

  const handleDownload = useCallback(async (orderId) => {
    try {
      await downloadOrder(orderId);
      toast.success('Заказ успешно скачан');
    } catch (err) {
      toast.error(`Ошибка скачивания: ${err.message}`);
    }
  }, []);

  const handleViewDetails = useCallback(async (orderId) => {
    try {
      const order = await getOrder(orderId);
      setSelectedOrder(order);
    } catch (err) {
      toast.error(`Ошибка загрузки деталей: ${err.message}`);
    }
  }, []);

  const handleDuplicateOrder = useCallback(async (orderId) => {
    try {
      const order = await getOrder(orderId);
      if (!order.items || order.items.length === 0) {
        toast.error('Заказ не содержит позиций');
        return;
      }
      
      // Извлекаем item_id и quantity из заказа
      const orderItems = order.items.map(item => ({
        item_id: item.item_id || item.id,
        quantity: item.quantity || 1,
      }));
      
      // Создаем новый заказ с теми же позициями
      const newOrder = await createOrder(orderItems, order.export_format || 'excel');
      toast.success(`Заказ #${order.id} продублирован как заказ #${newOrder.id}`);
      
      // Обновляем список заказов
      refetch();
      
      // Автоматически скачиваем новый заказ
      setTimeout(() => {
        downloadOrder(newOrder.id);
      }, 500);
    } catch (err) {
      toast.error(`Ошибка дублирования заказа: ${err.message}`);
    }
  }, [refetch]);

  /** Дата и время для карточек заказов */
  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleString('ru-RU', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  /** Только дата в формате ДД.ММ.ГГГГ для статистики */
  const formatDateOnly = (isoDate) => {
    if (!isoDate) return '—';
    const [y, m, d] = String(isoDate).split('-');
    return [d, m, y].filter(Boolean).join('.') || '—';
  };

  const { data: statsData, isLoading: statsLoading, error: statsError } = useQuery({
    queryKey: ['order-statistics', filters.date_from, filters.date_to],
    queryFn: () => getOrderStatistics({
      date_from: filters.date_from || undefined,
      date_to: filters.date_to || undefined,
    }),
    staleTime: 60000,
    enabled: true,
  });
  const stats = statsData || null;

  const calculateTotalPrice = (order) => {
    // Здесь нужно будет получать детали позиций для расчета
    return 'N/A';
  };

  const filteredOrders = useMemo(() => {
    return orders.filter(order => {
      if (filters.search) {
        const searchLower = filters.search.toLowerCase();
        return (
          order.id.toString().includes(searchLower) ||
          formatDate(order.created_at).toLowerCase().includes(searchLower)
        );
      }
      return true;
    });
  }, [orders, filters]);

  if (isLoading) {
    return (
      <div className="loading-container">
        <div className="loading-spinner">
          <div className="spinner-ring"></div>
          <div className="spinner-ring"></div>
          <div className="spinner-ring"></div>
        </div>
        <p>Загрузка истории заказов...</p>
      </div>
    );
  }

  if (error) {
    return <div className="error">Ошибка загрузки заказов: {error.message}</div>;
  }

  return (
    <div className="OrdersHistory">
      <div className="card">
        <h2>История заказов</h2>

        <div className="orders-filters">
          <input
            type="text"
            placeholder="Поиск по номеру заказа или дате..."
            value={filters.search}
            onChange={(e) => setFilters({ ...filters, search: e.target.value })}
            className="input"
          />
          <input
            type="date"
            placeholder="От"
            value={filters.date_from}
            onChange={(e) => setFilters({ ...filters, date_from: e.target.value })}
            className="input"
          />
          <input
            type="date"
            placeholder="До"
            value={filters.date_to}
            onChange={(e) => setFilters({ ...filters, date_to: e.target.value })}
            className="input"
          />
          <button
            className="button button-primary"
            onClick={() => refetch()}
          >
            Обновить
          </button>
        </div>

        <div className="orders-stats">
          <div className="stat-item">
            <span className="stat-label">Всего заказов:</span>
            <span className="stat-value">{orders.length}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Отфильтровано:</span>
            <span className="stat-value">{filteredOrders.length}</span>
          </div>
        </div>

        {statsLoading && (
          <div className="stats-loading">Загрузка расширенной статистики...</div>
        )}
        {!statsLoading && statsError && (
          <div className="stats-error">
            Не удалось загрузить статистику: {statsError.message}. Проверьте, что бэкенд запущен (порт 8000).
          </div>
        )}
        {!statsLoading && !statsError && stats && (
          <div className="orders-extended-stats">
            <h3>Расширенная статистика заказов</h3>
            <p className="stats-period">
              Период: {filters.date_from ? formatDateOnly(filters.date_from) : 'все время'}
              {filters.date_to ? ` — ${formatDateOnly(filters.date_to)}` : ''}
            </p>

            <div className="stats-summary">
              <div className="stats-summary-row">
                <span>Заказов</span>
                <strong>{stats.total_orders}</strong>
              </div>
              <div className="stats-summary-row">
                <span>Позиций (шт)</span>
                <strong>{stats.total_positions}</strong>
              </div>
              <div className="stats-summary-row">
                <span>Средний чек (руб)</span>
                <strong>{Number(stats.average_order_sum || 0).toLocaleString('ru-RU')}</strong>
              </div>
            </div>

            <div className="stats-period-sum">
              <strong>Сумма за период:</strong>{' '}
              {Number(stats.total_sum).toLocaleString('ru-RU')} ₽
              {stats.price_increase_sum != null && stats.price_increase_sum !== 0 && (
                <span className={stats.price_increase_sum > 0 ? 'price-increase' : 'price-decrease'}>
                  {' '}({stats.price_increase_sum > 0 ? '+' : ''}{Number(stats.price_increase_sum).toLocaleString('ru-RU')} ₽ за счёт изменения цен за период)
                </span>
              )}
              {stats.sum_at_period_start != null && stats.sum_at_period_start > 0 && (
                <div className="stats-period-hint">
                  В ценах на начало периода: {Number(stats.sum_at_period_start).toLocaleString('ru-RU')} ₽
                </div>
              )}
            </div>

            {(stats.by_format && stats.by_format.length > 0) && (
              <section className="stats-section">
                <h4>По форматам (банки, кеги)</h4>
                <div className="stats-table-wrap">
                  <table className="stats-table">
                    <thead>
                      <tr>
                        <th>Формат</th>
                        <th>Кол-во, шт</th>
                        <th>Позиций</th>
                        <th>Сумма, руб</th>
                      </tr>
                    </thead>
                    <tbody>
                      {stats.by_format.map((row, idx) => (
                        <tr key={row.format || idx}>
                          <td>{row.format}</td>
                          <td>{row.quantity}</td>
                          <td>{row.count}</td>
                          <td>{Number(row.sum || 0).toLocaleString('ru-RU')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}

            <section className="stats-section">
              <h4>Сводка по позициям (одинаковые позиции в сумме)</h4>
              <div className="stats-table-wrap">
                <table className="stats-table">
                  <thead>
                    <tr>
                      <th>Позиция</th>
                      <th>Заказано, шт</th>
                      <th>Сумма, руб</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(stats.ranking_with_dates || []).slice(0, 100).map((row) => (
                      <tr key={row.item_id}>
                        <td>{row.name}</td>
                        <td>{row.total_quantity}</td>
                        <td>{Number(row.total_sum || 0).toLocaleString('ru-RU')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {(stats.ranking_with_dates || []).length === 0 && (
                <p className="stats-empty">Нет данных за выбранный период</p>
              )}
            </section>

            <section className="stats-section">
              <h4>Изменение цен</h4>
              <div className="stats-table-wrap">
                <table className="stats-table">
                  <thead>
                    <tr>
                      <th>Позиция</th>
                      <th>Была цена (дата)</th>
                      <th>Стала цена (дата)</th>
                      <th>Изменение, %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(stats.price_trend || []).map((row) => (
                      <tr key={row.item_id}>
                        <td>{row.name}</td>
                        <td>{row.first_price} ({formatDateOnly(row.first_date)})</td>
                        <td>{row.last_price} ({formatDateOnly(row.last_date)})</td>
                        <td className={row.change_percent > 0 ? 'price-up' : row.change_percent < 0 ? 'price-down' : ''}>
                          {row.change_percent > 0 ? '+' : ''}{row.change_percent}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {(stats.price_trend || []).length === 0 && (
                <p className="stats-empty">Нет данных об изменении цен (нужно минимум 2 цены по позиции)</p>
              )}
            </section>
          </div>
        )}

        <div className="orders-list">
          <AnimatePresence>
            {filteredOrders.length === 0 ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="empty-message"
              >
                Заказы не найдены
              </motion.div>
            ) : (
              filteredOrders.map((order, index) => (
                <motion.div
                  key={order.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  transition={{ delay: index * 0.05 }}
                  className="order-card"
                >
                  <div className="order-header">
                    <div className="order-info">
                      <h3>Заказ #{order.id}</h3>
                      {order.export_file_path && (
                        <span className="order-filename">
                          {order.export_file_path.split('/').pop()}
                        </span>
                      )}
                      <span className="order-date">{formatDate(order.created_at)}</span>
                    </div>
                    <div className="order-format">
                      <span className={`format-badge ${order.export_format}`}>
                        {order.export_format.toUpperCase()}
                      </span>
                    </div>
                  </div>
                  
                  <div className="order-details">
                    <div className="detail-item">
                      <span className="detail-label">Позиций:</span>
                      <span className="detail-value">{order.items?.length || 0}</span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Формат:</span>
                      <span className="detail-value">{order.export_format}</span>
                    </div>
                  </div>

                  <div className="order-actions">
                    <button
                      className="button button-primary"
                      onClick={() => handleViewDetails(order.id)}
                    >
                      Детали
                    </button>
                    <button
                      className="button button-secondary"
                      onClick={() => handleDuplicateOrder(order.id)}
                      title="Создать копию этого заказа"
                    >
                      🔄 Повторить
                    </button>
                    <button
                      className="button button-success"
                      onClick={() => handleDownload(order.id)}
                    >
                      Скачать
                    </button>
                  </div>
                </motion.div>
              ))
            )}
          </AnimatePresence>
        </div>

        {selectedOrder && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="order-modal"
            onClick={() => setSelectedOrder(null)}
          >
            <motion.div
              initial={{ scale: 0.9 }}
              animate={{ scale: 1 }}
              className="order-modal-content"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="modal-header">
                <h2>Детали заказа #{selectedOrder.id}</h2>
                <button
                  className="modal-close"
                  onClick={() => setSelectedOrder(null)}
                >
                  ✕
                </button>
              </div>
              <div className="modal-body">
                <p><strong>Дата создания:</strong> {formatDate(selectedOrder.created_at)}</p>
                <p><strong>Формат:</strong> {selectedOrder.export_format}</p>
                <p><strong>Позиций:</strong> {selectedOrder.items?.length || 0}</p>
                {selectedOrder.items && selectedOrder.items.length > 0 && (
                  <div className="order-items-list">
                    <h3>Позиции заказа:</h3>
                    <ul>
                      {selectedOrder.items.map((item, idx) => (
                        <li key={idx}>
                          ID: {item.item_id}, Количество: {item.quantity}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </div>
    </div>
  );
}

export default OrdersHistory;

