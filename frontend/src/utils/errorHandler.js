/**
 * Утилиты для обработки ошибок с retry механизмом
 */

import toast from 'react-hot-toast';

/**
 * Выполняет функцию с повторными попытками при ошибке
 * @param {Function} fn - Функция для выполнения
 * @param {Object} options - Опции retry
 * @param {number} options.maxRetries - Максимальное количество попыток
 * @param {number} options.delay - Задержка между попытками (мс)
 * @param {Function} options.onRetry - Callback при повторной попытке
 */
export async function retry(fn, options = {}) {
  const {
    maxRetries = 3,
    delay = 1000,
    onRetry = null,
  } = options;

  let lastError;
  
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      
      if (attempt < maxRetries) {
        if (onRetry) {
          onRetry(attempt + 1, maxRetries, error);
        } else {
          toast.loading(
            `Повторная попытка ${attempt + 1}/${maxRetries}...`,
            { id: 'retry-toast' }
          );
        }
        
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }
  
  toast.dismiss('retry-toast');
  throw lastError;
}

/**
 * Обрабатывает ошибки API с понятными сообщениями
 */
export function handleApiError(error) {
  if (error.response) {
    // Сервер ответил с кодом ошибки
    const status = error.response.status;
    const message = error.response.data?.detail || error.response.data?.message || 'Ошибка сервера';
    
    switch (status) {
      case 400:
        toast.error(`Некорректный запрос: ${message}`);
        break;
      case 401:
        toast.error('Требуется авторизация');
        break;
      case 403:
        toast.error('Доступ запрещен');
        break;
      case 404:
        toast.error('Ресурс не найден');
        break;
      case 500:
        toast.error('Ошибка сервера. Попробуйте позже');
        break;
      default:
        toast.error(`Ошибка ${status}: ${message}`);
    }
  } else if (error.request) {
    // Запрос был отправлен, но ответа не получено
    toast.error('Нет соединения с сервером. Проверьте подключение к интернету');
  } else {
    // Ошибка при настройке запроса
    toast.error(`Ошибка: ${error.message}`);
  }
  
  return error;
}

