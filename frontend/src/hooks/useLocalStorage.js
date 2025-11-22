/**
 * Хук для работы с localStorage
 */

import { useState } from 'react';

export function useLocalStorage(key, initialValue) {
  // Состояние для хранения значения
  const [storedValue, setStoredValue] = useState(() => {
    try {
      const item = window.localStorage.getItem(key);
      return item ? JSON.parse(item) : initialValue;
    } catch (error) {
      console.error(`Ошибка чтения localStorage ключа "${key}":`, error);
      return initialValue;
    }
  });

  // Функция для обновления значения
  const setValue = (value) => {
    try {
      // Разрешаем значение быть функцией, чтобы иметь тот же API, что и useState
      const valueToStore = value instanceof Function ? value(storedValue) : value;
      setStoredValue(valueToStore);
      window.localStorage.setItem(key, JSON.stringify(valueToStore));
    } catch (error) {
      console.error(`Ошибка записи в localStorage ключа "${key}":`, error);
    }
  };

  return [storedValue, setValue];
}

