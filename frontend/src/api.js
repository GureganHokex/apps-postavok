/**
 * API клиент для взаимодействия с backend.
 */

import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

const getApiErrorMessage = (error) => {
  const data = error.response?.data;

  if (typeof data === 'string') {
    return data;
  }

  if (data?.detail) {
    return Array.isArray(data.detail) ? data.detail.join(' ') : data.detail;
  }

  if (data?.error) {
    return Array.isArray(data.error) ? data.error.join(' ') : data.error;
  }

  if (data && typeof data === 'object') {
    const firstError = Object.values(data).flat().find(Boolean);
    if (firstError) {
      return String(firstError);
    }
  }

  if (error.response?.status === 403) {
    return 'Нет прав на это действие. Проверьте роль пользователя или перезайдите в аккаунт.';
  }

  return error.message;
};

// Обработка ответов: 401 — не авторизован (приложение покажет форму входа)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.code === 'ERR_NETWORK' || error.message === 'Network Error') {
      error.message = `Сервер недоступен. Запустите backend: cd backend && source venv/bin/activate && python manage.py runserver (или DJANGO_DEBUG=true для разработки).`;
    } else if (error.response) {
      error.message = getApiErrorMessage(error);
    }
    if (error.response?.status === 401) {
      window.dispatchEvent(new CustomEvent('api:unauthorized'));
    }
    return Promise.reject(error);
  }
);

// ==================== Auth API ====================

/**
 * Вход. Возвращает { user: { id, username, role }, is_admin }.
 */
export const authLogin = async (username, password) => {
  const response = await api.post('/auth/login/', { username, password });
  return response.data;
};

/**
 * Выход.
 */
export const authLogout = async () => {
  await api.post('/auth/logout/');
};

/**
 * Текущий пользователь. 401 если не авторизован.
 */
export const authMe = async () => {
  const response = await api.get('/auth/me/');
  return response.data;
};

// ==================== Users (админ-панель) ====================

/**
 * Список пользователей. Только админ.
 */
export const getUsers = async () => {
  const response = await api.get('/users/');
  return response.data;
};

/**
 * Создать пользователя. Только админ.
 */
export const createUser = async (data) => {
  const response = await api.post('/users/', data);
  return response.data;
};

/**
 * Обновить пользователя (роль, имена, пароль). Только админ.
 */
export const updateUser = async (id, data) => {
  const response = await api.patch(`/users/${id}/`, data);
  return response.data;
};

/**
 * Удалить пользователя. Только админ.
 */
export const deleteUser = async (id) => {
  await api.delete(`/users/${id}/`);
};

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
 * @param {Object} supplierInfo - Информация о поставщике {supplier_type: 'distributor'|'brewery', brewery_name?: string}
 * @returns {Promise} Promise с результатами парсинга
 */
export const parseFile = async (fileId, supplierInfo = null) => {
  const data = supplierInfo ? { ...supplierInfo } : {};
  const response = await api.post(`/files/${fileId}/parse/`, data);
  return response.data;
};

/**
 * Поставщики (настройки маппинга колонок)
 */
export const getSuppliers = async () => {
  const response = await api.get('/suppliers/');
  return response.data;
};

export const getSupplier = async (id) => {
  const response = await api.get(`/suppliers/${id}/`);
  return response.data;
};

export const createSupplier = async (data) => {
  const response = await api.post('/suppliers/', data);
  return response.data;
};

export const updateSupplier = async (id, data) => {
  const response = await api.patch(`/suppliers/${id}/`, data);
  return response.data;
};

export const deleteSupplier = async (id) => {
  const response = await api.delete(`/suppliers/${id}/`);
  return response.data;
};

/**
 * Получает прогресс парсинга файла.
 * 
 * @param {number} fileId - ID файла
 * @returns {Promise} Promise с данными о прогрессе
 */
export const getParseProgress = async (fileId) => {
  // Долгий timeout: при одном воркере Gunicorn GET может ждать в очереди, пока идёт тяжёлый POST /parse/.
  const response = await api.get(`/files/${fileId}/parse_progress/`, { timeout: 180000 });
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
  
  // Получаем имя файла из заголовка Content-Disposition
  let filename = `order_${orderId}.xlsx`;
  const contentDisposition = response.headers['content-disposition'];
  if (contentDisposition) {
    // Ищем filename*=UTF-8'' или filename=
    const utf8Match = contentDisposition.match(/filename\*=UTF-8''(.+)/i);
    const simpleMatch = contentDisposition.match(/filename="?([^";\n]+)"?/i);
    if (utf8Match) {
      filename = decodeURIComponent(utf8Match[1]);
    } else if (simpleMatch) {
      filename = simpleMatch[1];
    }
  }
  
  // Создаем ссылку для скачивания
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
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
 * Получает расширенную статистику по заказам за период.
 * @param {Object} params - date_from, date_to (YYYY-MM-DD)
 * @returns {Promise} total_orders, total_sum, aggregated positions, price_trend
 */
export const getOrderStatistics = async (params = {}) => {
  const response = await api.get('/orders/statistics/', { params });
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

// ==================== Tap Locations API ====================

/**
 * Получает список локаций.
 */
export const getLocations = async () => {
  const response = await api.get('/locations/');
  return response.data;
};

/**
 * Создает новую локацию.
 */
export const createLocation = async (name) => {
  const response = await api.post('/locations/', { name });
  return response.data;
};

/**
 * Получает локацию с кранами.
 */
export const getLocation = async (locationId) => {
  const response = await api.get(`/locations/${locationId}/`);
  return response.data;
};

/**
 * Удаляет локацию.
 */
export const deleteLocation = async (locationId) => {
  await api.delete(`/locations/${locationId}/`);
};

/**
 * Обновляет локацию.
 */
export const updateLocation = async (locationId, data) => {
  const response = await api.patch(`/locations/${locationId}/`, data);
  return response.data;
};

/**
 * Экспортирует краны локации в Excel.
 */
export const exportLocationTaps = async (locationId) => {
  const response = await api.get(`/locations/${locationId}/export/`, {
    responseType: 'blob',
  });
  
  // Извлекаем имя файла из заголовка Content-Disposition
  const contentDisposition = response.headers['content-disposition'];
  let filename = `краны-${locationId}.xlsx`;
  if (contentDisposition) {
    const matches = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(contentDisposition);
    if (matches != null && matches[1]) {
      filename = matches[1].replace(/['"]/g, '');
      // Декодируем если это URL-encoded строка
      try {
        filename = decodeURIComponent(filename);
      } catch (e) {
        // Если не удалось декодировать, оставляем как есть
      }
    }
  }
  
  // Создаем временную ссылку для скачивания
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

/**
 * Получает краны локации.
 */
export const getLocationTaps = async (locationId) => {
  const response = await api.get(`/locations/${locationId}/taps/`);
  return response.data;
};

/**
 * Добавляет кран в локацию.
 */
export const addTap = async (locationId, tapData) => {
  const response = await api.post(`/locations/${locationId}/taps/`, tapData);
  return response.data;
};

/**
 * Обновляет кран.
 */
export const updateTap = async (tapId, data) => {
  const response = await api.patch(`/taps/${tapId}/`, data);
  return response.data;
};

/**
 * Удаляет кран.
 */
export const deleteTap = async (tapId) => {
  await api.delete(`/taps/${tapId}/`);
};

/**
 * Добавляет позицию из парсера на кран.
 */
export const addFromParser = async (locationId, itemId, position = null) => {
  const response = await api.post(`/locations/${locationId}/add_from_parser/`, {
    item_id: itemId,
    position: position,
  });
  return response.data;
};

/**
 * Изменяет порядок кранов.
 */
export const reorderTaps = async (locationId, tapIds) => {
  const response = await api.post('/taps/reorder/', {
    location_id: locationId,
    tap_ids: tapIds,
  });
  return response.data;
};

// ==================== Available Beers API ====================

/**
 * Получает список доступного пива для локации.
 */
export const getAvailableBeers = async (locationId) => {
  const response = await api.get(`/available-beers/?location=${locationId}`);
  return response.data;
};

/**
 * Добавляет доступное пиво.
 */
export const addAvailableBeer = async (data) => {
  const response = await api.post('/available-beers/', data);
  return response.data;
};

/**
 * Удаляет доступное пиво.
 */
export const deleteAvailableBeer = async (beerId) => {
  await api.delete(`/available-beers/${beerId}/`);
};

/**
 * Массовое создание доступного пива.
 */
export const bulkCreateAvailableBeers = async (locationId, items) => {
  const response = await api.post('/available-beers/bulk_create/', {
    location_id: locationId,
    items: items,
  });
  return response.data;
};

export default api;

