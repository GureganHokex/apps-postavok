/**
 * Хук для глобальных горячих клавиш
 */

import { useEffect } from 'react';

export function useKeyboardShortcuts(shortcuts) {
  useEffect(() => {
    const handleKeyDown = (event) => {
      const key = event.key.toLowerCase();
      const ctrl = event.ctrlKey || event.metaKey;
      const shift = event.shiftKey;
      const alt = event.altKey;

      // Формируем комбинацию клавиш
      const combination = [
        ctrl && 'ctrl',
        shift && 'shift',
        alt && 'alt',
        key
      ].filter(Boolean).join('+');

      // Ищем подходящий обработчик
      const handler = shortcuts[combination];
      if (handler) {
        event.preventDefault();
        handler(event);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [shortcuts]);
}
