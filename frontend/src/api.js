/**
 * API клиент для взаимодействия с backend.
 */

import axios from 'axios';

/**
 * База API: локально — env или localhost; в проде — тот же origin + /api (rewrites в vercel.json → Render).
 * Прямой URL на onrender.com из браузера часто даёт ERR_NETWORK (блокировки, DNS, cold start).
 * Обход: REACT_APP_FORCE_API_URL=1 и REACT_APP_API_URL=https://.../api — только если осознанно нужен прямой вызов.
 */
function resolveApiBaseUrl() {
  const fromEnv = (process.env.REACT_APP_API_URL || '').trim().replace(/\/$/, '');
  const forceDirect =
    process.env.REACT_APP_FORCE_API_URL === '1' || process.env.REACT_APP_FORCE_API_URL === 'true';

  if (typeof window !== 'undefined') {
    const h = window.location.hostname;
    if (h === 'localhost' || h === '127.0.0.1') {
      return fromEnv || 'http://localhost:8000/api';
    }
    if (forceDirect && fromEnv) {
      return fromEnv;
    }
    return `${window.location.origin}/api`;
  }
  return fromEnv || 'http://localhost:8000/api';
}

/**
 * База только для POST multipart /upload/: обходит Vercel→Render, если задан REACT_APP_UPLOAD_API_URL.
 * Сессионные cookie с домена Vercel на onrender.com не уйдут — используйте только вместе с полным
 * REACT_APP_FORCE_API_URL (весь API на Render) или если backend принимает загрузку без той же сессии.
 */
function resolveUploadApiBaseUrl() {
  const uploadOnly = (process.env.REACT_APP_UPLOAD_API_URL || '').trim().replace(/\/$/, '');
  if (uploadOnly) {
    return uploadOnly;
  }
  return resolveApiBaseUrl();
}

const API_BASE_URL = resolveApiBaseUrl();
const UPLOAD_API_BASE_URL = resolveUploadApiBaseUrl();

const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Отдельный клиент для multipart-загрузки: у `api` дефолт application/json.
 * Иначе axios transformRequest при FormData превращает тело в JSON — DRF: «Неподдерживаемый тип… application/json».
 */
const uploadApi = axios.create({
  baseURL: UPLOAD_API_BASE_URL,
  withCredentials: true,
});

/** Длинный HTML вместо JSON — в UI показываем кратко. 502/504 чаще шлюз (Vercel→Render), не traceback Django. */
function humanizeIfHtmlErrorBody(str, status) {
  if (typeof str !== 'string') return str;
  const t = str.trim();
  if (!/^<!doctype html|^<html[\s>]/i.test(t)) return str;
  const code = status ?? 500;
  if (code === 502 || code === 503) {
    return (
      `Ошибка шлюза (${code}): ответ пришёл как HTML-заглушка прокси, а не JSON. ` +
      'Часто это лимит времени/тела запроса на цепочке Vercel → Render при большой загрузке (multipart) или тяжёлом ZIP. ' +
      'Повторите попытку; откройте вкладку «Позиции» после обновления страницы — файл мог уже сохраниться. ' +
      'Для больших файлов: задайте в Vercel REACT_APP_FORCE_API_URL=1 и REACT_APP_API_URL=https://<backend>/api ' +
      '(все запросы, включая вход, на тот же origin Render + CORS), либо REACT_APP_UPLOAD_API_URL на тот же backend при совместимой авторизации. ' +
      'Логи: Render → Logs.'
    );
  }
  if (code === 504) {
    return (
      `Таймаут шлюза (${code}): прокси не дождался ответа от backend. ` +
      'Данные на Render могут уже сохраниться — обновите страницу и проверьте «Позиции». ' +
      'При очень больших загрузках см. REACT_APP_FORCE_API_URL / REACT_APP_UPLOAD_API_URL в переменных окружения фронта. Логи: Render → Logs.'
    );
  }
  return (
    `Сервер вернул ошибку (${code}), тело ответа — HTML (часто страница ошибки Django), а не JSON. ` +
    'Откройте логи веб-сервиса на Render (Logs) — там traceback и причина.'
  );
}

/**
 * Любое поле ошибки API → строка для UI (React не может рендерить объект как текст; DRF/Vercel шлют { code, message }).
 */
function stringifyApiValue(value) {
  if (value == null || value === '') return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) {
    const parts = value.map(stringifyApiValue).filter(Boolean);
    return parts.length ? parts.join(' ') : '';
  }
  if (typeof value === 'object') {
    if (typeof value.message === 'string') {
      const code = typeof value.code === 'string' ? `${value.code}: ` : '';
      return code + value.message;
    }
    if (typeof value.string === 'string') return value.string;
    if (value.detail != null) return stringifyApiValue(value.detail);
    try {
      return JSON.stringify(value);
    } catch {
      return 'Ошибка сервера';
    }
  }
  return String(value);
}

/** Для форм/toast: любое значение из API → строка (не рендерить объект в React). */
export { stringifyApiValue as formatApiFieldForUi };

/** Сообщение об ошибке запроса — всегда строка (для toast, форм, error.message в axios). */
export function getApiErrorMessage(error) {
  const status = error.response?.status;
  const data = error.response?.data;

  // 502/503/504 без HTML-тела — всё равно типичный «шлюз», не тело DRF
  if (status === 502 || status === 503 || status === 504) {
    const raw = typeof data === 'string' ? data.trim() : '';
    const isHtml = /^<!doctype html|^<html/i.test(raw);
    if (!isHtml) {
      return status === 504
        ? `Таймаут шлюза (${status}): Vercel → Render не дождались ответа. Повторите или обновите страницу и вкладку «Позиции». Для тяжёлых загрузок: REACT_APP_FORCE_API_URL + REACT_APP_API_URL.`
        : `Ошибка шлюза (${status}): Vercel → Render (часто большой POST /upload/ или холодный старт). Повторите; обновите страницу; при больших файлах — прямой API: REACT_APP_FORCE_API_URL=1 и REACT_APP_API_URL. Render → Logs.`;
    }
  }

  if (typeof data === 'string') {
    return humanizeIfHtmlErrorBody(data, status);
  }

  if (data?.detail != null) {
    const s = stringifyApiValue(data.detail);
    if (s) return s;
  }

  if (data?.error != null) {
    const s = stringifyApiValue(data.error);
    if (s) return s;
  }

  if (data && typeof data === 'object') {
    const parts = Object.values(data)
      .flat(4)
      .map(stringifyApiValue)
      .filter(Boolean);
    if (parts.length) return parts.join(' ');
  }

  if (error.response?.status === 403) {
    return 'Нет прав на это действие. Проверьте роль пользователя или перезайдите в аккаунт.';
  }

  const fallback = stringifyApiValue(error.message) || 'Ошибка запроса';
  return humanizeIfHtmlErrorBody(fallback, status);
}

function getNetworkErrorHint() {
  const host = typeof window !== 'undefined' ? window.location.hostname : '';
  const isLocalPage = /^localhost$|^127\.0\.0\.1$/i.test(host);
  const apiPointsToLocal = /localhost|127\.0\.0\.1/.test(API_BASE_URL);
  if (!isLocalPage && apiPointsToLocal && !/\.vercel\.app$/i.test(host)) {
    return (
      'В продакшене не задан REACT_APP_API_URL: запросы уходят на localhost. ' +
      'В Vercel → Project → Settings → Environment Variables добавьте REACT_APP_API_URL=https://<ваш-backend>.onrender.com/api ' +
      '(Production + Preview при необходимости) и выполните Redeploy с очисткой кэша.'
    );
  }
  if (isLocalPage) {
    return (
      'Сервер недоступен. Локально: cd backend && source venv/bin/activate && python manage.py runserver ' +
      '(или задайте REACT_APP_API_URL в .env в корне репозитория).'
    );
  }
  const sameOrigin =
    typeof window !== 'undefined' && API_BASE_URL.startsWith(`${window.location.origin}/`);
  if (sameOrigin) {
    return (
      `Не удаётся связаться с API (${API_BASE_URL}). ` +
      'Запрос идёт через ваш домен (rewrite на Render): убедитесь, что backend на Render в состоянии Live, ' +
      'а destination в frontend/vercel.json совпадает с актуальным URL сервиса. ' +
      'Долгие загрузки multipart могут обрываться прокси — тогда REACT_APP_FORCE_API_URL + REACT_APP_API_URL на Render.'
    );
  }
  return `Не удаётся связаться с API (${API_BASE_URL}). Проверьте URL backend на Render и CORS (CORS_ALLOWED_ORIGINS).`;
}

function attachCommonResponseInterceptor(client) {
  client.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error.code === 'ERR_NETWORK' || error.message === 'Network Error') {
        error.message = getNetworkErrorHint();
      } else if (error.response) {
        error.message = getApiErrorMessage(error);
      }
      if (error.response?.status === 401) {
        window.dispatchEvent(new CustomEvent('api:unauthorized'));
      }
      return Promise.reject(error);
    }
  );
}

// Обработка ответов: 401 — не авторизован (приложение покажет форму входа)
attachCommonResponseInterceptor(api);
attachCommonResponseInterceptor(uploadApi);

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

  // Только uploadApi: без дефолтного JSON — браузер выставит multipart + boundary.
  // Таймаут клиента не продлевает лимит прокси Vercel→Render; для тяжёлых тел см. REACT_APP_UPLOAD_API_URL / FORCE.
  const response = await uploadApi.post('/upload/', formData, {
    timeout: 600000, // 10 мин — ожидание ответа после отправки тела
    maxContentLength: Infinity,
    maxBodyLength: Infinity,
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
  // POST /parse/ отдаёт 202 сразу, парсинг в фоне (иначе Vercel→Render обрывает долгий ответ 502/HTML).
  const response = await api.post(`/files/${fileId}/parse/`, data, {
    timeout: 120000,
    validateStatus: (s) => s === 200 || s === 202,
  });
  if (response.status === 202) {
    return { accepted: true, ...(response.data || {}) };
  }
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

