/**
 * Компонент истории заказов
 */

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import { getOrders, downloadOrder, getOrder } from '../api';
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

