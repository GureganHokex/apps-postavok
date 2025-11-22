/**
 * Утилиты для обработки ошибок API
 */

import toast from 'react-hot-toast';

/**
 * Повторяет выполнение функции с задержкой при ошибке
 */
export async function retry(fn, options = {}) {
  const {
    maxRetries = 3,
    delay = 1000,
    onRetry = null,
  } = options;

  let lastError;
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      if (attempt < maxRetries) {
        if (onRetry) {
          onRetry(attempt, maxRetries);
        }
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }
  throw lastError;
}

/**
 * Обрабатывает ошибки API и показывает уведомления
 */
export function handleApiError(error) {
  let message = 'Произошла ошибка';
  
  if (error.response) {
    // Ошибка от сервера
    const status = error.response.status;
    const data = error.response.data;
    
    if (status === 400) {
      message = data?.detail || data?.message || 'Неверный запрос';
    } else if (status === 401) {
      message = 'Требуется авторизация';
    } else if (status === 403) {
      message = 'Доступ запрещен';
    } else if (status === 404) {
      message = 'Ресурс не найден';
    } else if (status === 500) {
      message = 'Ошибка сервера';
    } else {
      message = data?.detail || data?.message || `Ошибка ${status}`;
    }
  } else if (error.request) {
    // Запрос отправлен, но ответа нет
    message = 'Нет ответа от сервера. Проверьте подключение к интернету.';
  } else {
    // Ошибка при настройке запроса
    message = error.message || 'Ошибка при выполнении запроса';
  }
  
  toast.error(message);
  console.error('API Error:', error);
}
