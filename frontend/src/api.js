/**
 * API клиент для взаимодействия с backend.
 */

import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Загружает файл на сервер.
 * 
 * @param {File} file - Файл для загрузки
 * @returns {Promise} Promise с данными загруженного файла
 */
export const uploadFile = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  // Используем эндпоинт /api/upload/
  const response = await api.post('/upload/', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  
  return response.data;
};

/**
 * Запускает парсинг файла.
 * 
 * @param {number} fileId - ID файла
 * @returns {Promise} Promise с результатами парсинга
 */
export const parseFile = async (fileId) => {
  const response = await api.post(`/files/${fileId}/parse/`);
  return response.data;
};

/**
 * Получает список листов файла.
 * 
 * @param {number} fileId - ID файла
 * @returns {Promise} Promise со списком листов
 */
export const getFileSheets = async (fileId) => {
  const response = await api.get(`/files/${fileId}/sheets/`);
  return response.data;
};

/**
 * Получает список позиций файла.
 * 
 * @param {number} fileId - ID файла
 * @param {Object} filters - Фильтры поиска
 * @returns {Promise} Promise со списком позиций
 */
export const getFileItems = async (fileId, filters = {}) => {
  const response = await api.get(`/files/${fileId}/items/`, { params: filters });
  return response.data;
};

/**
 * Получает метаданные файла.
 * 
 * @param {number} fileId - ID файла
 * @returns {Promise} Promise с метаданными
 */
export const getFileMetadata = async (fileId) => {
  const response = await api.get(`/files/${fileId}/metadata/`);
  return response.data;
};

/**
 * Обновляет позицию.
 * 
 * @param {number} itemId - ID позиции
 * @param {Object} data - Данные для обновления
 * @returns {Promise} Promise с обновленной позицией
 */
export const updateItem = async (itemId, data) => {
  const response = await api.patch(`/items/${itemId}/`, data);
  return response.data;
};

/**
 * Создает заказ.
 * 
 * @param {Array} items - Список позиций [{item_id, quantity}, ...]
 * @param {string} exportFormat - Формат экспорта ('pdf' или 'excel')
 * @returns {Promise} Promise с созданным заказом
 */
export const createOrder = async (items, exportFormat = 'excel') => {
  const response = await api.post('/orders/', {
    items,
    export_format: exportFormat,
  });
  return response.data;
};

/**
 * Скачивает экспортированный заказ.
 * 
 * @param {number} orderId - ID заказа
 * @returns {Promise} Promise с blob файла
 */
export const downloadOrder = async (orderId) => {
  const response = await api.get(`/orders/${orderId}/export/`, {
    responseType: 'blob',
  });
  
  // Создаем ссылку для скачивания
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `order_${orderId}.${response.headers['content-type'].includes('pdf') ? 'pdf' : 'xlsx'}`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

/**
 * Получает список всех заказов.
 * 
 * @param {Object} filters - Фильтры поиска
 * @returns {Promise} Promise со списком заказов
 */
export const getOrders = async (filters = {}) => {
  const response = await api.get('/orders/', { params: filters });
  return response.data;
};

/**
 * Получает детали заказа.
 * 
 * @param {number} orderId - ID заказа
 * @returns {Promise} Promise с данными заказа
 */
export const getOrder = async (orderId) => {
  const response = await api.get(`/orders/${orderId}/`);
  return response.data;
};

/**
 * Удаляет позицию.
 * 
 * @param {number} itemId - ID позиции
 * @returns {Promise} Promise с результатом удаления
 */
export const deleteItem = async (itemId) => {
  const response = await api.delete(`/items/${itemId}/`);
  return response.data;
};

/**
 * Массовое обновление позиций.
 * 
 * @param {Array} itemIds - Массив ID позиций
 * @param {Object} data - Данные для обновления
 * @returns {Promise} Promise с результатами обновления
 */
export const bulkUpdateItems = async (itemIds, data) => {
  const response = await api.patch('/items/bulk_update/', {
    item_ids: itemIds,
    data: data,
  });
  return response.data;
};

/**
 * Массовое удаление позиций.
 * 
 * @param {Array} itemIds - Массив ID позиций
 * @returns {Promise} Promise с результатами удаления
 */
export const bulkDeleteItems = async (itemIds) => {
  const response = await api.post('/items/bulk_delete/', {
    item_ids: itemIds,
  });
  return response.data;
};

export default api;

